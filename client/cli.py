"""
DesiCDN CLI Client
====================

Ties together the two-step process a real CDN user goes through
(1. get routed to the nearest server, 2. fetch content from it) into
ONE command - hiding that two-step complexity behind a simple
interface, exactly like a real browser hides DNS resolution from you.

USAGE EXAMPLES:

    Fetch a file, simulating a user in Mumbai:
        python client/cli.py --city mumbai --file hello.json

    Fetch a file from an arbitrary raw location (not a preset city):
        python client/cli.py --lat 22.5726 --lon 88.3639 --file hello.json

    List available city presets:
        python client/cli.py --list-cities

Run this from the project ROOT (not from inside client/), so Python
can find the shared/ package correctly:
    python client/cli.py --city delhi --file hello.json
"""

import argparse
import os
import sys
import time

import requests

# When this file is run directly (e.g. `python client/cli.py`), Python
# only puts the client/ folder itself on the import search path - NOT
# the project root - so `from shared...` would fail with
# "ModuleNotFoundError: No module named 'shared'". This line explicitly
# adds the project root (one level up from this file) to the search
# path, so the import works regardless of how the script is invoked.
# (Running it as `python -m client.cli` from the project root instead
# would also work without this - but this makes the more common,
# simpler invocation just work too.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.client_locations import CLIENT_LOCATIONS

ROUTER_URL = "http://127.0.0.1:8000"


def fetch_content(city: str | None, lat: float | None, lon: float | None, filename: str):
    """
    The actual two-step flow, as one function:
      1. Ask the router for the nearest healthy PoP given a location.
      2. Fetch the requested file directly from that PoP.
      3. Print a clean, human-readable summary of what happened.
    """
    # ---- Resolve the client's location ----
    if city is not None:
        if city not in CLIENT_LOCATIONS:
            print(f"Unknown city '{city}'. Run with --list-cities to see options.")
            sys.exit(1)
        location = CLIENT_LOCATIONS[city]
        lat, lon = location["lat"], location["lon"]
        location_label = location["name"]
    else:
        # Raw --lat/--lon were provided instead of a preset city name.
        location_label = f"({lat}, {lon})"

    print(f"Simulating a user in: {location_label}")

    # ---- Step 1: ask the router for the nearest healthy PoP ----
    overall_start = time.time()
    try:
        route_response = requests.get(
            f"{ROUTER_URL}/route", params={"lat": lat, "lon": lon}, timeout=5
        )
    except requests.exceptions.ConnectionError:
        print(f"ERROR: could not reach the router at {ROUTER_URL}.")
        print("Is it running? (uvicorn router.main:app --port 8000)")
        sys.exit(1)

    if route_response.status_code == 503:
        # Every PoP is down - the router told us so honestly (Phase 6b).
        print("ERROR: the router reports ALL PoPs are currently unreachable.")
        print(route_response.json().get("detail", ""))
        sys.exit(1)

    if route_response.status_code != 200:
        print(f"ERROR: router returned unexpected status {route_response.status_code}")
        sys.exit(1)

    route_info = route_response.json()
    pop_name = route_info["pop_name"]
    pop_url = route_info["pop_url"]
    distance_km = route_info["distance_km"]
    unhealthy = route_info.get("unhealthy_pops_skipped", [])

    print(f"Router picked: {pop_name} ({distance_km} km away)")
    if unhealthy:
        print(f"(Note: skipped unhealthy PoPs: {', '.join(unhealthy)})")

    # ---- Step 2: fetch the actual content from that PoP ----
    try:
        content_response = requests.get(f"{pop_url}/content/{filename}", timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: could not reach {pop_name} at {pop_url}.")
        sys.exit(1)

    overall_elapsed_ms = (time.time() - overall_start) * 1000

    if content_response.status_code == 404:
        print(f"'{filename}' was not found (404).")
        sys.exit(1)

    if content_response.status_code != 200:
        print(f"ERROR: {pop_name} returned unexpected status {content_response.status_code}")
        sys.exit(1)

    cache_status = content_response.headers.get("x-cache", "UNKNOWN")

    print(f"Cache status: {cache_status}")
    print(f"Total round-trip time: {round(overall_elapsed_ms, 1)} ms")
    print()
    print("--- Content ---")
    print(content_response.text)


def main():
    parser = argparse.ArgumentParser(
        description="DesiCDN CLI - simulate a user requesting content from the nearest PoP."
    )
    parser.add_argument(
        "--city",
        choices=list(CLIENT_LOCATIONS.keys()),
        help="Simulate a user in this preset Indian city.",
    )
    parser.add_argument("--lat", type=float, help="Raw latitude (used instead of --city).")
    parser.add_argument("--lon", type=float, help="Raw longitude (used instead of --city).")
    parser.add_argument(
        "--file", dest="filename", help="Filename to request, e.g. hello.json"
    )
    parser.add_argument(
        "--list-cities", action="store_true", help="List available --city presets and exit."
    )

    args = parser.parse_args()

    if args.list_cities:
        print("Available --city presets:")
        for key, info in CLIENT_LOCATIONS.items():
            print(f"  {key:12s} -> {info['name']} ({info['lat']}, {info['lon']})")
        sys.exit(0)

    # Validate: need EITHER --city, OR both --lat and --lon, not neither/mixed incorrectly.
    if args.city is None and (args.lat is None or args.lon is None):
        parser.error("Provide either --city NAME, or both --lat and --lon.")

    if args.filename is None:
        parser.error("Provide --file FILENAME (the file to request).")

    fetch_content(args.city, args.lat, args.lon, args.filename)


if __name__ == "__main__":
    main()
