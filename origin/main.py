"""
Origin Server
=============

This is the "source of truth" server in our CDN simulation.
It owns every real file in `content/` and is the ONLY component in the
whole system that reads from the actual filesystem for content.

Everything else (Edge/PoP servers, later) will ask THIS server for a file
the first time they need it, then keep their own cached copy.

Run this with:
    uvicorn origin.main:app --port 9000 --reload

Why port 9000: no special reason other than keeping it clearly separate
from the edge server ports we'll pick in Phase 2 (8001, 8002, 8003...).
Real CDNs don't expose their origin on a "well-known" port either -
it's usually hidden behind the CDN entirely, and only the CDN's edge
servers are allowed to talk to it. We're not enforcing that restriction
yet (Phase 6 territory), but keep it in mind.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI(title="DesiCDN - Origin Server")

# Absolute path to the content/ folder, computed relative to this file
# (NOT relative to "wherever you happened to run the command from").
# This matters: if you ran uvicorn from a different working directory,
# a relative path like "content/" could silently point at the wrong place.
CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content")


@app.get("/")
def health_check():
    """
    A basic health/status endpoint.

    Real-world relevance: production services almost always expose
    something like this so load balancers, monitoring tools, or humans
    can quickly check "is this thing alive?" without hitting real
    business logic. We'll reuse this exact pattern for edge servers
    in Phase 2, and it becomes genuinely important in Phase 6 when we
    talk about failover (routing around a dead server).
    """
    return {"status": "ok", "service": "origin"}


@app.get("/content/{filename}")
def get_content(filename: str):
    """
    Serve a file by name from the content/ directory.

    filename comes straight from the URL - e.g. a request to
    /content/hello.json arrives here with filename="hello.json".
    """
    file_path = os.path.join(CONTENT_DIR, filename)

    # Guard clause: if the file doesn't exist, fail loudly and correctly
    # with a proper HTTP 404 - NOT a Python crash (500 error).
    # This distinction matters a lot later: our edge/router logic will
    # need to tell apart "origin said the file doesn't exist" (404)
    # from "origin is unreachable" (connection error) - very different
    # problems in a real CDN.
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"'{filename}' not found on origin")

    return FileResponse(file_path)