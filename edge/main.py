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

app = FastAPI(title=f"DesiCDN - Edge Server ({POP_INFO['name']})")

# THE CACHE ITSELF.
# Structure: { filename: {"content": bytes, "media_type": str, "cached_at": float} }
# This is plain Python, living only in this process's memory - restart
# the server, the cache is gone. That's expected and realistic (see
# explanation given alongside this code).
cache = {}


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "edge",
        "pop_id": POP_ID,
        "pop_name": POP_INFO["name"],
        "lat": POP_INFO["lat"],
        "lon": POP_INFO["lon"],
        "cached_files": list(cache.keys()),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }


@app.get("/content/{filename}")
def get_content(filename: str):
    """
    Serve a file - from cache if we have a fresh copy, otherwise fetch
    from origin, cache it, then serve it.
    """
    now = time.time()

    # ---- Check for a CACHE HIT ----
    if filename in cache:
        entry = cache[filename]
        age = now - entry["cached_at"]

        if age < CACHE_TTL_SECONDS:
            # Fresh! Serve directly from memory - no origin involved.
            #
            # IMPORTANT BUG LESSON: headers must be set on the SAME
            # Response object we actually return. Earlier version of
            # this code set headers on the `response` object FastAPI
            # injects, but then returned a DIFFERENT, newly-created
            # Response object - which silently discarded those headers.
            # FastAPI only sends whichever Response object your function
            # actually returns; injected parameter objects are only
            # respected if you mutate THEM and return THEM (or don't
            # return a Response at all, and just return plain data).
            hit_response = Response(
                content=entry["content"],
                media_type=entry["media_type"],
            )
            hit_response.headers["X-Cache"] = "HIT"
            hit_response.headers["X-Cache-Age-Seconds"] = str(round(age, 1))
            hit_response.headers["X-Served-By"] = POP_INFO["name"]
            return hit_response
        # else: entry exists but is STALE (past TTL) - fall through to
        # miss handling below, exactly as if we never had it. This is
        # the TTL expiry behavior in action.

    # ---- CACHE MISS: fetch from origin ----
    try:
        origin_response = requests.get(f"{ORIGIN_URL}/content/{filename}", timeout=5)
    except requests.exceptions.ConnectionError:
        # Origin is unreachable entirely - a DIFFERENT failure mode
        # than "origin said 404." Worth telling apart: this means the
        # whole CDN is in trouble, not just that one file is missing.
        raise HTTPException(status_code=502, detail="Could not reach origin server")

    if origin_response.status_code == 404:
        # Origin explicitly doesn't have this file - don't cache a
        # "not found," just pass the 404 through honestly.
        raise HTTPException(status_code=404, detail=f"'{filename}' not found on origin")

    if origin_response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Origin returned unexpected status {origin_response.status_code}",
        )

    # Store in cache for next time.
    media_type = origin_response.headers.get("content-type", "application/octet-stream")
    cache[filename] = {
        "content": origin_response.content,
        "media_type": media_type,
        "cached_at": now,
    }

    miss_response = Response(content=origin_response.content, media_type=media_type)
    miss_response.headers["X-Cache"] = "MISS"
    miss_response.headers["X-Served-By"] = POP_INFO["name"]
    return miss_response