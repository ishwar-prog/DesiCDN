"""
Client location presets.

These represent "where a simulated USER is standing" - conceptually
different from shared/pop_config.py, which represents "where our
SERVERS are." It's worth keeping these separate even though both are
just lat/lon: mixing up "server location" and "client location" data
is an easy, confusing mistake to make once a codebase grows.

Feel free to add more cities here - this is just a convenience so you
don't have to remember/type raw coordinates every time you use the CLI
client. Real coordinates for each city (not the same as the PoP
coordinates, on purpose - simulating a real user "near" but not
exactly AT a PoP).
"""

CLIENT_LOCATIONS = {
    "delhi": {"name": "Delhi", "lat": 28.7041, "lon": 77.1025},
    "noida": {"name": "Noida", "lat": 28.5355, "lon": 77.3910},
    "mumbai": {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    "pune": {"name": "Pune", "lat": 18.5204, "lon": 73.8567},
    "bangalore": {"name": "Bangalore", "lat": 12.9716, "lon": 77.5946},
    "mysore": {"name": "Mysore", "lat": 12.2958, "lon": 76.6394},
    "kolkata": {"name": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    "chennai": {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    "hyderabad": {"name": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
}