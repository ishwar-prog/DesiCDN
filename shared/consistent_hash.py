"""
Consistent Hashing Ring.

Solves a DIFFERENT problem than our geography-based router: given a
set of interchangeable cache servers (not geographically distinct
PoPs - just N servers sharing load), how do you decide which server
should hold which piece of content, in a way that DOESN'T fall apart
every time you add or remove a server?

THE NAIVE APPROACH AND WHY IT FAILS:
    server_index = hash(filename) % number_of_servers
This works fine... until number_of_servers changes. The moment you add
or remove even ONE server, % changes its output for almost EVERY
filename - meaning nearly all previously-cached content suddenly
"belongs" to a different server. Every cache in the whole system
effectively goes cold at once. In a real system, that's a massive,
sudden spike of cache misses hitting your origin all together -
exactly what caching was supposed to prevent.

THE CONSISTENT HASHING IDEA:
Picture a circle (a "ring") with positions numbered 0 up to some large
maximum. We hash each SERVER's name into a position on this ring.
We also hash each piece of CONTENT (e.g. a filename) into a position
on the same ring. To find which server owns a piece of content: start
at the content's position and walk clockwise until you hit a server.

Why this fixes the reshuffling problem: adding a new server only
"steals" the small arc of content between it and the PREVIOUS server
on the ring - everything else's clockwise walk still lands on exactly
the same server as before. Only a small fraction (roughly 1/N) of
content remaps, not nearly everything.

VIRTUAL NODES (a real refinement used in production systems):
If each real server only gets ONE point on the ring, the ring can be
unevenly spread by pure luck - two servers might land close together,
leaving one server responsible for a huge arc and another a tiny one.
The real fix (used by systems like Amazon DynamoDB and Memcached's
Ketama): hash each REAL server into MANY points on the ring ("virtual
nodes"), which averages out to a much more even distribution. We
implement this properly below, not as a toy simplification - this is
genuinely how it's done in production.
"""

import bisect
import hashlib


def _hash(key: str) -> int:
    """
    Turn an arbitrary string into a large, deterministic integer.
    Deterministic matters: the SAME string must hash to the SAME
    number every time, on every machine - otherwise different parts
    of a distributed system could disagree about who owns what data.

    We use MD5 here purely as a fast, well-distributed number
    generator - NOT for any security/cryptographic purpose. MD5 is
    considered broken for security use cases, but that property is
    irrelevant here; we only care that it spreads inputs evenly across
    a large number range, which it does well.
    """
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    return int(digest, 16)


class ConsistentHashRing:
    def __init__(self, servers: list[str], virtual_nodes_per_server: int = 100):
        """
        servers: list of server names/identifiers (e.g. ["cache-a", "cache-b"])
        virtual_nodes_per_server: how many points on the ring each real
            server gets. Higher = more even distribution, at the cost
            of more memory/computation. 100-200 is a common real-world
            default.
        """
        self.virtual_nodes_per_server = virtual_nodes_per_server
        self._ring_positions: list[int] = []          # sorted list of positions on the ring
        self._position_to_server: dict[int, str] = {}  # position -> which real server owns it

        for server in servers:
            self._add_server_to_ring(server)

    def _add_server_to_ring(self, server: str):
        """
        Place `virtual_nodes_per_server` points for this one real
        server onto the ring. Each virtual point is derived by hashing
        a slightly different string per virtual copy (server name +
        an index), so the same server still lands at many DIFFERENT
        positions, not the same position repeated.
        """
        for i in range(self.virtual_nodes_per_server):
            virtual_key = f"{server}#vn{i}"
            position = _hash(virtual_key)
            self._position_to_server[position] = server
            bisect.insort(self._ring_positions, position)

    def _remove_server_from_ring(self, server: str):
        """Remove ALL of this server's virtual points from the ring."""
        for i in range(self.virtual_nodes_per_server):
            virtual_key = f"{server}#vn{i}"
            position = _hash(virtual_key)
            if position in self._position_to_server:
                del self._position_to_server[position]
                index = bisect.bisect_left(self._ring_positions, position)
                if index < len(self._ring_positions) and self._ring_positions[index] == position:
                    self._ring_positions.pop(index)

    def add_server(self, server: str):
        self._add_server_to_ring(server)

    def remove_server(self, server: str):
        self._remove_server_from_ring(server)

    def get_server_for_key(self, key: str) -> str:
        """
        Given a content key (e.g. a filename), find which server owns
        it: hash the key to a position, then walk CLOCKWISE (i.e. find
        the next ring position that is >= our key's position) to find
        the owning server. If we've gone past the highest position on
        the ring, wrap around to the very first one (the ring is a
        circle, not a line).
        """
        if not self._ring_positions:
            raise ValueError("No servers in the ring.")

        key_position = _hash(key)

        # bisect_left finds where key_position WOULD be inserted to
        # keep the list sorted - which is exactly "the first ring
        # position >= key_position," i.e. walking clockwise from key.
        index = bisect.bisect_left(self._ring_positions, key_position)

        if index == len(self._ring_positions):
            # We walked past the end of the ring - wrap around to the start.
            index = 0

        owning_position = self._ring_positions[index]
        return self._position_to_server[owning_position]