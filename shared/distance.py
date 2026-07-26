"""
Distance calculation utilities.

Contains the Haversine formula: computes the "great-circle" distance
between two points on Earth's surface, given their latitude/longitude.

WHY THIS APPROXIMATES NETWORK LATENCY (AND WHERE IT BREAKS DOWN):

Real CDNs care about latency (time for data to travel), not physical
distance. But physical distance is a reasonable FIRST-ORDER PROXY for
latency because:
  - Light in fiber optic cable travels at a fixed, finite speed
    (~200,000 km/s - about 2/3 the speed of light in vacuum)
  - Internet routes roughly follow geography - there's rarely a fast
    route that takes a huge geographic detour

This is why "route to the nearest PoP by distance" is a legitimate
starting strategy used in real systems, not just a toy simplification.

WHERE IT BREAKS DOWN in the real world (worth knowing for interviews):
  - Actual network routes depend on which internet backbones/exchange
    points exist between two points - two cities close in distance
    might be poorly "peered" (no good direct network route) and
    actually have higher latency than a farther, well-connected city
  - Physical obstacles (oceans, mountain ranges) affect where cables
    can actually be laid
  - Server LOAD matters too - the "nearest" server might be overloaded,
    making a farther-but-idle server the actually-faster choice

Real CDNs (Cloudflare, Akamai) use ACTIVE LATENCY MEASUREMENT (called
RTT - Round Trip Time - probing) combined with geography, not geography
alone. We're starting with geography only because it's simple to
understand and reason about; Phase 6 discusses adding real measured
latency on top of this.
"""

import math


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in kilometers between two points
    given as (lat1, lon1) and (lat2, lon2), in decimal degrees.
    """
    R = 6371.0  # Earth's radius in kilometers (mean radius)

    # Convert degrees to radians - math.sin/cos expect radians, not degrees
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # The Haversine formula itself - computes the central angle between
    # the two points, then multiplies by Earth's radius to get distance.
    # You don't need to derive this - it's standard, fixed spherical
    # trigonometry - just understand it outputs "angle between points"
    # converted into "distance along Earth's curved surface."
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c