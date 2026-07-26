# OurHike — Roadmap / Build Plan (Draft v1)

Companion to [OurHikeValues.md](OurHikeValues.md), [FEATURES.md](FEATURES.md), and [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md). Ordered, phased list of what needs to get built and how, from where we are now (decided architecture) to a shippable v1. Expect this to shift as decisions firm up — check items off as they're done, add detail as it emerges.

---

## Phase 1 — Data pipeline

- [x] **DuckDB spatial spike.** Prove the core operation works before building on top of it: buffer the AT centerline by 30 miles, clip real data against it, export the result. *(Done — see `pipeline/spike_corridor.py`. Buffered the full 3,025-segment centerline by 30mi, unioned into one valid corridor polygon (~81,138 sq mi), clipped real ATC campsite/shelter data against it — all 232 campsites and 280 shelters fell within the corridor, as expected for official on-trail sites. Used ATC data only, not OSM — see note below on rethinking OSM's role first. Hit and documented an `ST_Transform` axis-order gotcha in `pipeline/README.md`, worth knowing before anyone else touches that call.)*
- [ ] **Think through open-source trail data strategy more deliberately** before building more ingestion. Prompted by realizing the OSM pull was about to become "grab roads because the architecture doc says so" rather than solving a real hiker need — and by [USGS's National Digital Trails page](https://www.usgs.gov/national-digital-trails/seven-ways-access-or-view-usgs-trails-dataset) on the many ways to access their trails dataset. Worth deciding deliberately: what background/reference map layer to use (raster vs. vector, and from where — USGS, OSM, something else), and which specific gaps in ATC's own data (confirmed gap: no water-source or general resupply layer) get filled by which external source. Deserves real thought, not an MVP-speed decision.
- [ ] **Ingestion scripts** — pull raw extracts from ATC (POIs), USGS (elevation/topo), OSM (roads/land cover) into formats DuckDB reads directly (GeoJSON/Shapefile/GeoPackage/FlatGeobuf). *(ATC side started — see `pipeline/`: `discover_sources.py` finds layer URLs from ATC's public ArcGIS map, `fetch_all.py` pulls all 9 registered layers. USGS/OSM ingestion not started.)*
- [x] **Corridor computation** — generate the 30-mile buffer once (`ST_Buffer` + `ST_Union` over the centerline + waypoints). *(Done — see `pipeline/spike_corridor.py`.)*
- [x] **Clip & join, raster side proven at real scale (2026-07-25)** — see `pipeline/spike_raster_mosaic.py`: mosaics the real 1,654 downloaded US Topo quads (14GB) per corridor-intersecting grid cell, reprojecting each from its native (varying) UTM zone via a lazy `WarpedVRT`, then clips to the actual corridor polygon. POI-side join (ATC + OSM/opentrail + NHD into one schema) still open — see Unified POI schema below.
- [ ] **Unified POI schema** — one schema for water/shelter/campsite/crossing/resupply, designed to not bake in AT-only or NYNJTC-only assumptions (value #7), even though only the AT is in scope for v1.
- [ ] **Export** — base map as PMTiles, POI layers as GeoJSON/FlatGeobuf. Check package sizes are reasonable for a phone download. Each output artifact gets its own content hash (SHA256) — see Publish below for why (per-artifact, not one hash for everything).
- [ ] **Publish, change-aware plan decided 2026-07-25** — push versioned packages to Cloudflare R2, but only the artifacts that actually changed, and never publish a new version if nothing did. Full plan in TECHNICAL_ARCHITECTURE.md's "Data pipeline" section. **Blocked on one decision that needs to happen once, not twice:** hiker download chunking granularity (per-state? per section? one corridor-wide package?) — this determines the hashing/versioning granularity too, and is the same open question as "Offline download flow" below. Decide there first, then implement here.
- [ ] **Reach out to opentrail.org's maintainer (GitHub: austinwritescode) to confirm data-reuse terms directly.** Their `/api/getData` endpoint (AT/PCT/CDT waypoints incl. resupply-relevant POIs) has no LICENSE file anywhere in the repo, so reuse rights aren't formally confirmed - the maintainer reportedly called it "open data" in a Reddit post ([r/Ultralight](https://www.reddit.com/r/Ultralight/comments/11gf2aw/announcing_a_free_guthookfarout_alternative/)), which is why we're proceeding with location/POI data only for now (deliberately excluding their user comments - those are personal contributions from named individuals, a separate consent concern from copyright), but this needs a real answer, not an informal comment-thread reference. Good opportunity for reciprocity too - OurHike intends to be open data itself (value #3, #6; see FEATURES.md "Data openness & portability"), so this can be a two-way conversation once there's something functional to show them.
- [ ] **Investigate NHD flowline stream-crossings as a water-source candidate list, visually + against verifiable sources.** Goal: OSM water tagging tops out around 178-326 near the trail (tested 100m-800m) - nowhere close to FarOut/the AT Guide's 1,100+. Researched whether USGS NHD (hydrography, already in the pipeline for the base map) could close that gap by algorithmically finding stream crossings instead of relying on point tagging. Findings so far (2026-07-25):
  - NHD's "Spring" point layer specifically is sparse near the AT (only 99 within 5mi of centerline) - not a useful source on its own.
  - NHD flowline (stream/river) data crossing the trail is much richer. Buffer/proximity-based counting (nearby streams within some radius) produces numbers 2-5x *larger* than the 1,100 target depending on radius (2,500-5,900 "crossing events" after declustering) - real, but includes a lot of minor/unnamed streams a guidebook wouldn't bother listing, so it overshoots rather than undershoots.
  - **True geometric intersections** (where the trail's line literally crosses a stream's line, no buffer/clustering judgment call) is the cleanest cut: **841 total crossings, 568 perennial, 201 intermittent, 72 other.** Notably below 1,100, but a solid, unambiguous starting number - no arbitrary radius to defend.
  - Next steps before this becomes a real pipeline source: (1) visually inspect a sample of the 841 crossings on a map to sanity-check they're real/sensible, not an artifact of positional misalignment between ATC's centerline and NHD's flowlines; (2) cross-reference against a verifiable source (e.g. the AT Guide's ~989 water-tagged mile-table entries, kept in `personal_reference/` - see that folder's README for why it's not in the pipeline) to see how much real overlap vs. gap there is, rather than just comparing raw counts.
- [x] **Update cadence + change detection, decided 2026-07-25: check weekly, only actually re-fetch what changed.** Each fetch script now checks a cheap upstream signal before doing the real (slower/larger) data pull, and skips entirely if nothing changed:
  - `fetch_all.py` (ATC ArcGIS layers) — checks each layer's `editingInfo.dataLastEditDate` (a lightweight metadata-only request) against the value recorded in `data/raw/manifest.json` from the last run; skips the full paginated feature fetch if unchanged. Verified: second consecutive run correctly skipped all 12 sources.
  - `fetch_opentrail.py` — uses real HTTP conditional requests (`If-None-Match` / `ETag`, which the API's own README documents support) rather than reimplementing change detection - a 304 response means skip. Verified working.
  - `fetch_topo_quads.py` already had this per-quad via S3 `Last-Modified` headers against its own manifest (built in from the start, no change needed).
  - Still open: *where* this actually gets triggered weekly (manual run by a maintainer vs. a scheduled job e.g. GitHub Actions cron) - the cadence and "don't do unnecessary work" logic are now real, but nothing calls these scripts on a schedule yet.

## Phase 2 — Client app (MVP)

- [ ] **Scaffold the PWA** — React + TypeScript, Vite, basic service worker + manifest.
- [ ] **Map rendering** — MapLibre GL JS reading PMTiles directly in-browser (via the `pmtiles` library's MapLibre protocol handler).
- [ ] **Offline download flow** — let a hiker pick a trail section to download before losing signal; store via Cache API/IndexedDB. This is the core "why would I use this instead of a browser tab" feature. **Decide chunking granularity here first** (per-state? per section? one corridor-wide package?) — Phase 1's change-aware Publish step needs this same answer for its hashing/versioning granularity, so this is a decide-once, not decide-twice situation.
- [ ] **"You are here"** — GPS via the browser Geolocation API, shown live on the offline map.
- [ ] **POI browsing/search** — filter/list water sources, shelters, campsites, resupply points, crossings over the GeoJSON layer.
- [ ] **Outdoor usability pass** — test readability in sunlight glare, one-handed/gloved use. Ties directly to value #4 (trustworthy above all) — a map that's unreadable at a junction fails at its one job.

## Phase 3 — App store packaging

- [ ] **Wrap with Capacitor** — generate iOS + Android shells from the PWA build (`npx cap add ios` / `android`).
- [ ] **iOS build & TestFlight** — build via Xcode on the Mac; beta test through TestFlight before public submission. Apple Developer account ($99/yr — check nonprofit fee waiver eligibility first).
- [ ] **Android build & internal testing** — build via Android Studio/Gradle; Google Play Developer account ($25 one-time).
- [ ] **Store listing assets** — screenshots, description, and a privacy policy (required by both stores, and necessary anyway since the app uses location — keep it plain and honest, per value #4).

## Phase 4 — Launch readiness

- [ ] **Real-trail field testing** — offline mode, GPS accuracy, battery drain, tested on an actual section of trail, ideally by NYNJTC or ATC volunteers.
- [ ] **Web-only donation/payment flow** — basic Stripe (or similar) checkout on the web version only, nothing equivalent in the wrapped app.
- [ ] **Inheritability docs** — keep FEATURES.md/TECHNICAL_ARCHITECTURE.md current, add a CONTRIBUTING.md / setup guide aimed at "the next club," not just this one.
- [ ] **Soft launch with NYNJTC** — first real users, gather feedback, iterate before wider release.

## Deferred (Phase 5+, post-MVP — see FEATURES.md)

- Community condition reporting & maintainer verification
- Trail magic features
- Multi-club admin/config tooling
- Weather integration

---

## Immediate next step

Phase 0 is mostly "make some calls / sign up for accounts" — the first *coding* task, whenever you're ready to pick it back up, is the **DuckDB spatial spike** at the top of Phase 1.
