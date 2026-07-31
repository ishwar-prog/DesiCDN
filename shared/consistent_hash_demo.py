"""
Consistent Hashing - Demo & Proof Script
===========================================

Run this directly to see concrete evidence of WHY consistent hashing
is used over naive modulo (%) hashing in real distributed caches.

    python shared/consistent_hash_demo.py

This is a STANDALONE demonstration - it does not affect or get called
by the router/edge servers, which route by GEOGRAPHY, not by hash.
This script exists purely to prove understanding of a genuinely
important, commonly-interviewed distributed systems concept, and to
show real, self-generated evidence rather than just asserting a fact.

Three things are demonstrated:
  1. Deterministic correctness - the same key always maps to the
     same server, given the same ring.
  2. THE KEY BENEFIT - adding a server only reshuffles a SMALL
     fraction of keys with consistent hashing, vs. NEARLY ALL keys
     with naive modulo hashing.
  3. Virtual nodes actually produce more even distribution across
     servers than using just one point per server.
"""

import os
import sys
from collections import Counter

# Same fix as client/cli.py: running this file directly only puts
# shared/ itself on the import path, not the project root, so
# `from shared.consistent_hash import ...` would fail otherwise.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.consistent_hash import ConsistentHashRing

NUM_KEYS = 10_000


def demo_correctness():
    print("=" * 60)
    print("DEMO 1: Deterministic correctness")
    print("=" * 60)
    ring = ConsistentHashRing(servers=["cache-a", "cache-b", "cache-c"])

    for filename in ["file1.jpg", "file2.jpg", "file3.jpg"]:
        server = ring.get_server_for_key(filename)
        server_again = ring.get_server_for_key(filename)
        assert server == server_again
        print(f"  {filename:15s} -> {server}")
    print("  (same key always maps to the same server - confirmed)\n")


def demo_reshuffling_comparison():
    print("=" * 60)
    print("DEMO 2: Reshuffling when adding a server (the main point)")
    print("=" * 60)

    filenames = [f"file_{i}.jpg" for i in range(NUM_KEYS)]

    # ---- Consistent hashing ----
    ring = ConsistentHashRing(servers=["cache-a", "cache-b", "cache-c"])
    before = {f: ring.get_server_for_key(f) for f in filenames}
    ring.add_server("cache-d")
    after = {f: ring.get_server_for_key(f) for f in filenames}
    moved = sum(1 for f in filenames if before[f] != after[f])

    print(f"  Consistent hashing : {moved:5d} / {NUM_KEYS} keys moved "
          f"({moved / NUM_KEYS * 100:.1f}%) after adding a 4th server")
    print(f"                       (theoretical ideal for 3->4 servers: ~25%)")

    # ---- Naive modulo hashing, for contrast ----
    def naive_server(filename, num_servers):
        return hash(filename) % num_servers

    before_naive = {f: naive_server(f, 3) for f in filenames}
    after_naive = {f: naive_server(f, 4) for f in filenames}
    moved_naive = sum(1 for f in filenames if before_naive[f] != after_naive[f])

    print(f"  Naive modulo (%N)  : {moved_naive:5d} / {NUM_KEYS} keys moved "
          f"({moved_naive / NUM_KEYS * 100:.1f}%) after adding a 4th server")
    print()
    print(f"  --> Consistent hashing moved ~{moved / NUM_KEYS * 100:.0f}% of keys;")
    print(f"      naive modulo moved ~{moved_naive / NUM_KEYS * 100:.0f}% - "
          f"this is the whole reason consistent hashing exists.\n")


def demo_virtual_nodes():
    print("=" * 60)
    print("DEMO 3: Virtual nodes improve distribution evenness")
    print("=" * 60)

    filenames = [f"file_{i}.jpg" for i in range(NUM_KEYS)]

    ring_many_vnodes = ConsistentHashRing(
        servers=["cache-a", "cache-b", "cache-c"], virtual_nodes_per_server=100
    )
    dist_many = Counter(ring_many_vnodes.get_server_for_key(f) for f in filenames)

    ring_one_vnode = ConsistentHashRing(
        servers=["cache-a", "cache-b", "cache-c"], virtual_nodes_per_server=1
    )
    dist_one = Counter(ring_one_vnode.get_server_for_key(f) for f in filenames)

    print("  With 100 virtual nodes per server:")
    for server, count in sorted(dist_many.items()):
        print(f"    {server}: {count:5d} keys ({count / NUM_KEYS * 100:.1f}%)")

    print("  With only 1 virtual node per server (no averaging):")
    for server, count in sorted(dist_one.items()):
        print(f"    {server}: {count:5d} keys ({count / NUM_KEYS * 100:.1f}%)")

    print()
    print("  --> More virtual nodes per server = distribution closer to")
    print("      even (33%/33%/33%) across servers. This is why real")
    print("      systems (e.g. DynamoDB, Memcached/Ketama) use MANY")
    print("      virtual nodes per real server, not just one.\n")


if __name__ == "__main__":
    demo_correctness()
    demo_reshuffling_comparison()
    demo_virtual_nodes()