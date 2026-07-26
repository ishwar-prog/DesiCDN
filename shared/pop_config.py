"""
Shared PoP (Point of Presence) configuration.

This is the SINGLE SOURCE OF TRUTH for "which simulated cities exist,
and where are they." Both edge servers and the router (Phase 3) import
from here - if you ever need to add a new city or fix a coordinate,
you change it in exactly one place, and every component picks it up.

Coordinates are real latitude/longitude for each city (used later in
Phase 3 for distance calculations - not needed yet in Phase 2, but
defined here now since this IS the "location" data for each PoP).
"""

POPS = {
    "delhi": {
        "name": "Delhi",
        "lat": 28.6139,
        "lon": 77.2090,
        "port": 8001,
    },
    "mumbai": {
        "name": "Mumbai",
        "lat": 19.0760,
        "lon": 72.8777,
        "port": 8002,
    },
    "bangalore": {
        "name": "Bangalore",
        "lat": 12.9716,
        "lon": 77.5946,
        "port": 8003,
    },
}