"""
Router ("the CDN's brain") - WITH HEALTH CHECKS & FAILOVER
=============================================================

Given a client's location (lat/lon), decides which PoP is nearest AND
CURRENTLY ALIVE, tells the client where to go - it does NOT serve
content itself.

NEW IN THIS PHASE: before picking a PoP by distance, the router first
actively checks (via each PoP's own "/" health endpoint) which PoPs
are actually responding right now. Only ALIVE PoPs are eligible to be
picked - if the geographically nearest PoP is down, the router falls
back to the next-nearest ALIVE one instead. If every PoP is down, the
router says so honestly (HTTP 503) rather than pretending everything
is fine.

This mimics (in simplified form) what real CDN "smart DNS" does: when
your computer resolves a CDN's domain name, the DNS response ITSELF
is location-aware - you get back a different IP depending on where
you're asking from, and the "routing decision" already happened before
your actual HTTP request is even sent.

We can't easily hijack real DNS resolution in a learning project, so
instead we simulate the SAME DECISION as a plain HTTP endpoint: the
client asks the router "given my location, which PoP should I use?",
gets an answer, then makes a SEPARATE request directly to that PoP.

Run with:
    uvicorn router.main:app --port 8000 --reload
"""

import requests
from fastapi import FastAPI, HTTPException, Query
from shared.pop_config import POPS
from shared.distance import haversine_distance

app = FastAPI(title="DesiCDN - Router")

# How long to wait for a PoP to respond to a health check before giving
# up and treating it as unhealthy. Short on purpose: a PoP that's
# genuinely fine should answer almost instantly (it's just returning a
# small JSON object) - if it takes longer than this, something is
# wrong enough that we shouldn't route users there. Real systems face
# the exact same tuning decision: too generous a timeout means users
# wait behind a struggling server; too strict means occasional false
# alarms on momentary slowness.
HEALTH_CHECK_TIMEOUT_SECONDS = 2


def is_pop_healthy(pop_info: dict) -> bool:
    """
    Actively ask a PoP's own health-check endpoint "are you alive?"
    Returns True only if it responds with HTTP 200 within the timeout.
    ANY failure (connection refused, timeout, non-200 status) is
    treated as unhealthy - we'd rather be cautious and skip a PoP that
    might actually be fine than risk sending users to one that's
    genuinely struggling.
    """
    url = f"http://127.0.0.1:{pop_info['port']}/"
    try:
        response = requests.get(url, timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        # Covers connection refused (process not running), timeout
        # (hanging/overloaded), and any other network-level failure -
        # all treated identically: this PoP is not usable right now.
        return False


@app.get("/")
def health_check():
    return {"status": "ok", "service": "router"}


@app.get("/route")
def route(
    lat: float = Query(..., description="Client's latitude"),
    lon: float = Query(..., description="Client's longitude"),
):
    """
    Given a client's lat/lon as query parameters:
      1. Check which PoPs are actually alive right now (health check).
      2. Among ONLY the alive ones, pick the nearest by distance.
      3. If literally none are alive, fail honestly with HTTP 503 -
         never silently return a dead PoP's address.

    Example:
        GET /route?lat=28.70&lon=77.10
        -> nearest ALIVE PoP is "delhi" (assuming delhi is up)
    """
    # ---- Step 1: filter to only healthy PoPs ----
    healthy_pops = {
        pop_id: info for pop_id, info in POPS.items() if is_pop_healthy(info)
    }

    if not healthy_pops:
        # Every single PoP failed its health check - the whole CDN is
        # effectively down. Say so clearly with 503 Service Unavailable
        # (the correct HTTP status for "the service exists but cannot
        # currently handle requests") rather than crashing or lying.
        raise HTTPException(
            status_code=503,
            detail="All PoPs are currently unreachable. No server available to route to.",
        )

    # ---- Step 2: among healthy PoPs only, pick nearest by distance ----
    distances = []
    for pop_id, info in healthy_pops.items():
        d = haversine_distance(lat, lon, info["lat"], info["lon"])
        distances.append((pop_id, info, d))

    nearest_pop_id, nearest_info, nearest_distance = min(distances, key=lambda entry: entry[2])

    unhealthy_pop_ids = [pop_id for pop_id in POPS if pop_id not in healthy_pops]

    return {
        "client_location": {"lat": lat, "lon": lon},
        "nearest_pop": nearest_pop_id,
        "pop_name": nearest_info["name"],
        "distance_km": round(nearest_distance, 2),
        "pop_url": f"http://127.0.0.1:{nearest_info['port']}",
        "all_distances_km": {
            pop_id: round(d, 2) for pop_id, _, d in distances
        },
        "unhealthy_pops_skipped": unhealthy_pop_ids,
    }