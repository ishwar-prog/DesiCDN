"""
LRU (Least Recently Used) Cache.

A cache with a MAXIMUM SIZE. Once full, adding a new item evicts
whichever existing item has gone the LONGEST without being accessed -
not the oldest by insertion time, but the least RECENTLY touched.

WHY THIS MATTERS:
Real servers have finite memory. An unbounded cache (what we had in
Phases 4-5) will eventually consume all available RAM if enough
distinct files get requested. Every real cache needs an eviction
policy - a rule for "what do we throw out when we're full?"

WHY LRU SPECIFICALLY:
The core assumption: "recently accessed" is a decent predictor of
"will be accessed again soon." This holds well for a lot of real
traffic patterns (a viral image gets requested repeatedly for a
while, then interest fades) - though it's not universal (see the
limitation noted below).

HOW THIS IS IMPLEMENTED:
Python's OrderedDict remembers insertion order AND lets us cheaply
move an existing item to the end via move_to_end(). The trick:
  - Every time an item is touched (read OR freshly added), move it
    to the end - "most recently used" always lives at the end.
  - The front of the dict naturally becomes whatever hasn't been
    touched in the longest time - exactly what we want to evict.
  - When adding a new item while already at capacity, pop from the
    front (oldest-by-recency) before inserting the new one.

REAL-WORLD HONESTY: production systems (Redis, Memcached, real CDN
edge caches) implement the same LRU IDEA but with far more optimized
underlying data structures for massive scale and concurrent access.
The concept here is identical to production systems; the raw
performance characteristics are not (this is fine for a learning
project serving a handful of requests per second on one machine).
"""

from collections import OrderedDict


class LRUCache:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._store = OrderedDict()

    def get(self, key):
        """
        Return the cached value for `key`, or None if not present.
        Accessing an item counts as "using" it - move it to the end
        so it's treated as most-recently-used and won't be an early
        eviction candidate.
        """
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, key, value):
        """
        Store `value` under `key`. If the cache is already at capacity
        AND this is a genuinely new key, evict the least-recently-used
        item first (the one at the front of the ordered dict), THEN
        insert the new item.

        Returns the evicted key if an eviction happened, else None -
        useful for logging what got kicked out and why.
        """
        if key in self._store:
            # Already present - update value, and mark as freshly used.
            self._store[key] = value
            self._store.move_to_end(key)
            return None

        evicted_key = None
        if len(self._store) >= self.max_size:
            # Cache is full and this is a NEW key - evict LRU item
            # (from the FRONT - the least-recently-touched entry)
            # before inserting the new one.
            evicted_key, _ = self._store.popitem(last=False)

        self._store[key] = value
        return evicted_key

    def __contains__(self, key):
        return key in self._store

    def keys(self):
        return list(self._store.keys())

    def __len__(self):
        return len(self._store)