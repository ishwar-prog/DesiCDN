"""
Edge Server (PoP - Point of Presence) - WITH CACHING
======================================================

Same identity system as Phase 2 (POP_ID env var), now with an actual
in-memory cache added.

Flow for every content request:
  1. Is this file in our cache AND still "fresh" (within TTL)?
       YES -> serve it immediately from memory. This is a CACHE HIT.
       NO  -> go to step 2. This is a CACHE MISS.
  2. Ask the origin server for the file over HTTP.
  3. Store the file + the current time in our cache.
  4. Serve the file to the client.

Every response includes an "X-Cache" header set to either "HIT" or
"MISS" - a transparent, inspectable signal of what actually happened,
exactly like real CDNs (Cloudflare's CF-Cache-Status, Akamai's
X-Cache, CloudFront's X-Cache) do.

Run with (same as Phase 2, plus ORIGIN_URL):
    POP_ID=delhi uvicorn edge.main:app --port 8001 --reload

ORIGIN_URL defaults to http://127.0.0.1:9000 (see below) so you don't
need to set it unless your origin runs somewhere else.
"""

import os
import time
import requests
from fastapi import FastAPI, HTTPException, Response
from shared.pop_config import POPS
from shared.logging_utils import log_request, read_logs
from shared.lru_cache import LRUCache

POP_ID = os.environ.get("POP_ID", "delhi")

if POP_ID not in POPS:
    raise ValueError(f"Unknown POP_ID '{POP_ID}'. Must be one of: {list(POPS.keys())}")

POP_INFO = POPS[POP_ID]

# Where this edge server should fetch content from on a cache miss.
# Configurable via env var for the same reason POP_ID is - so the
# exact same code works whether origin is on localhost (our setup)
# or a real remote server (Phase 6 territory).
ORIGIN_URL = os.environ.get("ORIGIN_URL", "http://127.0.0.1:9000")

# How long (in seconds) a cached file stays "fresh" before we treat it
# as a miss again and re-fetch from origin. 60 seconds is deliberately
# SHORT here so you can actually observe expiry happening in a normal
# testing session, without waiting minutes. Real CDNs set this per
# content type - e.g. a company logo image might get a TTL of days,
# while a news homepage might get seconds.
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "60"))

# Maximum number of DISTINCT files this PoP will hold in cache at once.
# Deliberately small (3) by default so you can actually TRIGGER and
# OBSERVE eviction in a normal testing session without needing
# thousands of unique files. Real edge caches size this based on
# available RAM/disk - could be millions of objects in production.
MAX_CACHE_SIZE = int(os.environ.get("MAX_CACHE_SIZE", "3"))

app = FastAPI(title=f"DesiCDN - Edge Server ({POP_INFO['name']})")

# THE CACHE ITSELF - now an LRUCache instead of a plain dict, so it has
# a maximum size and a real eviction policy once full. See
# shared/lru_cache.py for the full explanation of how/why this works.
# Structure per entry: {"content": bytes, "media_type": str, "cached_at": float}
cache = LRUCache(max_size=MAX_CACHE_SIZE)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "edge",
        "pop_id": POP_ID,
        "pop_name": POP_INFO["name"],
        "lat": POP_INFO["lat"],
        "lon": POP_INFO["lon"],
        "cached_files": cache.keys(),
        "cache_size": len(cache),
        "max_cache_size": MAX_CACHE_SIZE,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


@app.get("/content/{filename}")
def get_content(filename: str):
    """
    Serve a file - from cache if we have a fresh copy, otherwise fetch
    from origin, cache it, then serve it.

    Every outcome (hit, miss, 404, origin-down) is timed and logged as
    a structured record - this is what /metrics later reads and
    summarizes into a hit rate.
    """
    start_time = time.time()  # start the stopwatch for THIS request

    # ---- Check for a CACHE HIT ----
    entry = cache.get(filename)
    if entry is not None:
        age = start_time - entry["cached_at"]

        if age < CACHE_TTL_SECONDS:
            # Fresh! Serve directly from memory - no origin involved.
            hit_response = Response(
                content=entry["content"],
                media_type=entry["media_type"],
            )
            hit_response.headers["X-Cache"] = "HIT"
            hit_response.headers["X-Cache-Age-Seconds"] = str(round(age, 1))
            hit_response.headers["X-Served-By"] = POP_INFO["name"]

            elapsed_ms = (time.time() - start_time) * 1000
            log_request(POP_ID, filename, "HIT", elapsed_ms)

            return hit_response
        # else: entry exists but is STALE (past TTL) - fall through to
        # miss handling below, exactly as if we never had it.

    # ---- CACHE MISS: fetch from origin ----
    try:
        origin_response = requests.get(f"{ORIGIN_URL}/content/{filename}", timeout=5)
    except requests.exceptions.ConnectionError:
        elapsed_ms = (time.time() - start_time) * 1000
        log_request(POP_ID, filename, "ORIGIN_DOWN", elapsed_ms)
        raise HTTPException(status_code=502, detail="Could not reach origin server")

    if origin_response.status_code == 404:
        elapsed_ms = (time.time() - start_time) * 1000
        log_request(POP_ID, filename, "NOT_FOUND", elapsed_ms)
        raise HTTPException(status_code=404, detail=f"'{filename}' not found on origin")

    if origin_response.status_code != 200:
        elapsed_ms = (time.time() - start_time) * 1000
        log_request(POP_ID, filename, "ORIGIN_ERROR", elapsed_ms)
        raise HTTPException(
            status_code=502,
            detail=f"Origin returned unexpected status {origin_response.status_code}",
        )

    # Store in cache for next time. If the cache is already at
    # MAX_CACHE_SIZE and this is a new filename, put() will evict the
    # least-recently-used entry to make room - we log that eviction so
    # it's visible in the structured logs, not a silent side effect.
    media_type = origin_response.headers.get("content-type", "application/octet-stream")
    evicted_filename = cache.put(filename, {
        "content": origin_response.content,
        "media_type": media_type,
        "cached_at": start_time,
    })

    if evicted_filename is not None:
        log_request(POP_ID, evicted_filename, "EVICTED", 0.0)

    miss_response = Response(content=origin_response.content, media_type=media_type)
    miss_response.headers["X-Cache"] = "MISS"
    miss_response.headers["X-Served-By"] = POP_INFO["name"]

    elapsed_ms = (time.time() - start_time) * 1000
    log_request(POP_ID, filename, "MISS", elapsed_ms)

    return miss_response


@app.get("/metrics")
def metrics():
    """
    Read back this PoP's own log history and summarize it into
    meaningful numbers - this is the "aggregation" step: turning many
    individual log records into a hit rate.

    This is a tiny hand-built version of what real observability tools
    (Prometheus is the industry-standard one) do at massive scale:
    collect structured events, then expose summarized numbers.
    """
    records = read_logs(POP_ID)

    if not records:
        return {
            "pop_id": POP_ID,
            "total_requests": 0,
            "message": "No requests logged yet - try requesting /content/hello.json first.",
        }

    total = len(records)
    hits = sum(1 for r in records if r["cache_status"] == "HIT")
    misses = sum(1 for r in records if r["cache_status"] == "MISS")
    not_found = sum(1 for r in records if r["cache_status"] == "NOT_FOUND")
    origin_down = sum(1 for r in records if r["cache_status"] == "ORIGIN_DOWN")

    # Average response time, split by hit vs miss - this is the number
    # that actually PROVES caching helps, using YOUR OWN measured data
    # rather than just claiming "caching is faster."
    hit_times = [r["response_time_ms"] for r in records if r["cache_status"] == "HIT"]
    miss_times = [r["response_time_ms"] for r in records if r["cache_status"] == "MISS"]

    avg_hit_ms = round(sum(hit_times) / len(hit_times), 2) if hit_times else None
    avg_miss_ms = round(sum(miss_times) / len(miss_times), 2) if miss_times else None

    # Count requests per filename - shows which content is most popular,
    # a real thing CDN operators look at (e.g. to decide what to
    # pre-warm/pre-cache before it's even requested).
    requests_per_file = {}
    for r in records:
        requests_per_file[r["filename"]] = requests_per_file.get(r["filename"], 0) + 1

    return {
        "pop_id": POP_ID,
        "total_requests": total,
        "hits": hits,
        "misses": misses,
        "not_found": not_found,
        "origin_down": origin_down,
        "hit_rate_percent": round((hits / total) * 100, 1) if total else 0,
        "avg_response_time_ms": {
            "hit": avg_hit_ms,
            "miss": avg_miss_ms,
        },
        "requests_per_file": requests_per_file,
    }