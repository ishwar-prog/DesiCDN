"""
Structured logging utility.

Instead of plain-text log lines like "Delhi served hello.json - HIT",
we write each request as a structured JSON object, one per line, to a
log file. This format is called "JSON Lines" (.jsonl / ndjson) - a
very common real-world convention: each line is a complete, independent
JSON object, so you can read the file one line at a time without
needing to parse the WHOLE file first (important once log files get
large - you don't want to load gigabytes into memory just to check
recent activity).

WHY STRUCTURED LOGS, NOT PLAIN TEXT:
Plain text is fine for a human glancing at a terminal. But you cannot
reliably compute "hit rate over the last hour" by regex-parsing English
sentences at scale - it's fragile and slow. A structured record like:
    {"timestamp": 1721990000.12, "pop_id": "delhi",
     "filename": "hello.json", "cache_status": "HIT",
     "response_time_ms": 2.4}
can be read, filtered, and aggregated trivially and reliably. This is
the real industry standard (structured/JSON logging) used by virtually
every serious backend system, precisely so tools can process logs
automatically instead of a human reading them one by one.
"""

import json
import os
import time


def log_request(pop_id: str, filename: str, cache_status: str, response_time_ms: float):
    """
    Append one structured request record to this PoP's log file.

    Creates a `logs/` directory (if missing) and a `logs/{pop_id}.log`
    file - one log file per PoP, so each server's history stays
    independently inspectable rather than mixed into one shared firehose.
    """
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_path = os.path.join(logs_dir, f"{pop_id}.log")

    record = {
        "timestamp": time.time(),
        "pop_id": pop_id,
        "filename": filename,
        "cache_status": cache_status,
        "response_time_ms": round(response_time_ms, 2),
    }

    # "a" = append mode - we NEVER want to overwrite previous history,
    # only add to it. Every request adds exactly one new line.
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_logs(pop_id: str) -> list[dict]:
    """
    Read back every logged record for a given PoP, as a list of dicts.
    Used by the /metrics endpoint to compute summaries.
    Returns an empty list if no log file exists yet (e.g. fresh start,
    no requests served yet) - this is a normal case, not an error.
    """
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    log_path = os.path.join(logs_dir, f"{pop_id}.log")

    if not os.path.isfile(log_path):
        return []

    records = []
    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records