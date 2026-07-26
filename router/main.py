"""
Router ("the CDN's brain")
============================

Given a client's location (lat/lon), decides which PoP is nearest and
tells the client where to go - it does NOT serve content itself.

This mimics (in simplified form) what real CDN "smart DNS" does: when
your computer resolves a CDN's domain name, the DNS response ITSELF
is location-aware - you get back a different IP depending on where
you're asking from, and the "routing decision" already happened before
your actual HTTP request is even sent.

We can't easily hijack real DNS resolution in a learning project, so
instead we simulate the SAME DECISION as a plain HTTP endpoint: the
client asks the router "given my location, which PoP should I use?",
gets an answer, then makes a SEPARATE request directly to that PoP.

This is a real, meaningful architectural difference worth understanding:
  - DNS-based routing (real world): decision happens at name resolution,
    invisible to the application, cached by resolvers, very fast
  - HTTP-based routing (this project): decision is an explicit visible
    step, easier to observe/debug/learn from - which is exactly why
    we're doing it this way for a learning project

Run with:
    uvicorn router.main:app --port 8000 --reload
"""

from fastapi import FastAPI, Query
from shared.pop_config import POPS
from shared.distance import haversine_distance

app = FastAPI(title="DesiCDN - Router")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "router"}


@app.get("/route")
def route(
    lat: float = Query(..., description="Client's latitude"),
    lon: float = Query(..., description="Client's longitude"),
):
    """
    Given a client's lat/lon as query parameters, return the nearest
    PoP's identity, distance, and the URL the client should now call
    directly to actually fetch content.

    Example:
        GET /route?lat=28.70&lon=77.10
        -> nearest PoP is "delhi"
    """
    # Compute distance from the client to EVERY known PoP.
    # This is O(n) in number of PoPs - fine for 3, and still fine for
    # real CDNs which typically have dozens to low-hundreds of PoPs,
    # not millions - this brute-force approach is actually realistic.
    distances = []
    for pop_id, info in POPS.items():
        d = haversine_distance(lat, lon, info["lat"], info["lon"])
        distances.append((pop_id, info, d))

    # Pick the entry with the smallest distance - the "key=" tells min()
    # to compare using the 3rd element of each tuple (the distance),
    # not the tuples themselves.
    nearest_pop_id, nearest_info, nearest_distance = min(distances, key=lambda entry: entry[2])

    return {
        "client_location": {"lat": lat, "lon": lon},
        "nearest_pop": nearest_pop_id,
        "pop_name": nearest_info["name"],
        "distance_km": round(nearest_distance, 2),
        "pop_url": f"http://127.0.0.1:{nearest_info['port']}",
        "all_distances_km": {
            pop_id: round(d, 2) for pop_id, _, d in distances
        },
    }