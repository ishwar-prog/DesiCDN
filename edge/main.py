"""
Edge Server (PoP - Point of Presence)
======================================

This file is run MULTIPLE TIMES SIMULTANEOUSLY - once per simulated city -
as separate processes on separate ports. Every running copy uses this
exact same code. What makes one copy "Delhi" and another "Mumbai" is
purely the POP_ID environment variable set at launch time.

Run one instance like this:
    POP_ID=delhi uvicorn edge.main:app --port 8001 --reload

Run another instance (in a DIFFERENT terminal tab) like this:
    POP_ID=mumbai uvicorn edge.main:app --port 8002 --reload

And a third:
    POP_ID=bangalore uvicorn edge.main:app --port 8003 --reload

Windows PowerShell syntax is different (see instructions given separately) -
PowerShell doesn't support `VAR=value command` on one line the way
Linux/Mac shells do.

Phase 2 scope: NO caching yet. Each edge server just proves it:
  1. Knows its own identity (which PoP it is)
  2. Can report that identity back over HTTP
  3. Can independently be reached on its own port

Caching (talking to the origin, storing files locally) comes in Phase 4.
"""

import os
from fastapi import FastAPI
from shared.pop_config import POPS

# Read which PoP this particular running instance represents.
# Defaults to "delhi" only so the server doesn't crash if you forget
# to set it - but in real use, you should always set POP_ID explicitly.
POP_ID = os.environ.get("POP_ID", "delhi")

# Look up this PoP's metadata (name, coordinates, expected port) from
# the shared config. If someone sets POP_ID to something not in
# pop_config.py, fail loudly at startup rather than limping along
# with unknown identity - a server that doesn't know where it is
# shouldn't silently pretend everything's fine.
if POP_ID not in POPS:
    raise ValueError(
        f"Unknown POP_ID '{POP_ID}'. Must be one of: {list(POPS.keys())}"
    )

POP_INFO = POPS[POP_ID]

app = FastAPI(title=f"DesiCDN - Edge Server ({POP_INFO['name']})")


@app.get("/")
def health_check():
    """
    Same health-check pattern as the origin server (Phase 1) - every
    component in this system exposes this so we can always ask
    "are you alive, and who are you?" This becomes essential in
    Phase 6 (failover): the router will need to skip PoPs that don't
    answer this endpoint.
    """
    return {
        "status": "ok",
        "service": "edge",
        "pop_id": POP_ID,
        "pop_name": POP_INFO["name"],
        "lat": POP_INFO["lat"],
        "lon": POP_INFO["lon"],
    }