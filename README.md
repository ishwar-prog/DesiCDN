# DesiCDN

A CDN (Content Delivery Network) simulator, built from scratch in Python/FastAPI,
to learn — in depth — how real CDNs (Cloudflare, Akamai, CloudFront) route users
to the nearest server and cache content at the edge.

This is a learning project built in explicit phases. Each phase is committed
separately so the git history itself tells the story of how the system was built.

## Status
🚧 Phase 0: Project scaffolding — in progress

## Architecture (evolving)

- `origin/` — the single source of truth server; owns all real content
- `edge/` — cache/"PoP" (Point of Presence) servers, one per simulated city
- `router/` — decides which edge server (PoP) is nearest to a given client
- `client/` — CLI tool to simulate a user requesting content from a location
- `shared/` — config/data shared across components (e.g. PoP coordinates)
- `content/` — static files owned by the origin

## Phases
- [ ] Phase 0 — Project scaffolding & repo hygiene
- [ ] Phase 1 — Origin server
- [ ] Phase 2 — Edge servers (no caching yet)
- [ ] Phase 3 — Geo-routing logic
- [ ] Phase 4 — Real caching (hit/miss, TTL, eviction)
- [ ] Phase 5 — Metrics & observability
- [ ] Phase 6 — Refinements (real multi-region deploy, failover, etc.)
- [ ] Phase 7 — Write-up: explain it at every level