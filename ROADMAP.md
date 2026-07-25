# OurHike — Roadmap / Build Plan (Draft v1)

Companion to [OurHikeValues.md](OurHikeValues.md), [FEATURES.md](FEATURES.md), and [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md). Ordered, phased list of what needs to get built and how, from where we are now (decided architecture) to a shippable v1. Expect this to shift as decisions firm up — check items off as they're done, add detail as it emerges.

---

## Phase 1 — Data pipeline

- [x] **DuckDB spatial spike.** Prove the core operation works before building on top of it: buffer the AT centerline by 30 miles, clip real data against it, export the result. *(Done — see `pipeline/spike_corridor.py`. Buffered the full 3,025-segment centerline by 30mi, unioned into one valid corridor polygon (~81,138 sq mi), clipped real ATC campsite/shelter data against it — all 232 campsites and 280 shelters fell within the corridor, as expected for official on-trail sites. Used ATC data only, not OSM — see note below on rethinking OSM's role first. Hit and documented an `ST_Transform` axis-order gotcha in `pipeline/README.md`, worth knowing before anyone else touches that call.)*
- [ ] **Think through open-source trail data strategy more deliberately** before building more ingestion. Prompted by realizing the OSM pull was about to become "grab roads because the architecture doc says so" rather than solving a real hiker need — and by [USGS's National Digital Trails page](https://www.usgs.gov/national-digital-trails/seven-ways-access-or-view-usgs-trails-dataset) on the many ways to access their trails dataset. Worth deciding deliberately: what background/reference map layer to use (raster vs. vector, and from where — USGS, OSM, something else), and which specific gaps in ATC's own data (confirmed gap: no water-source or general resupply layer) get filled by which external source. Deserves real thought, not an MVP-speed decision.
- [ ] **Ingestion scripts** — pull raw extracts from ATC (POIs), USGS (elevation/topo), OSM (roads/land cover) into formats DuckDB reads directly (GeoJSON/Shapefile/GeoPackage/FlatGeobuf). *(ATC side started — see `pipeline/`: `discover_sources.py` finds layer URLs from ATC's public ArcGIS map, `fetch_all.py` pulls all 9 registered layers. USGS/OSM ingestion not started.)*
- [ ] **Corridor computation** — generate the 30-mile buffer once (`ST_Buffer` + `ST_Union` over the centerline + waypoints).
- [ ] **Clip & join** — intersect USGS/OSM against the corridor; join ATC POI layers into one schema.
- [ ] **Unified POI schema** — one schema for water/shelter/campsite/crossing/resupply, designed to not bake in AT-only or NYNJTC-only assumptions (value #7), even though only the AT is in scope for v1.
- [ ] **Export** — base map as PMTiles, POI layers as GeoJSON/FlatGeobuf. Check package sizes are reasonable for a phone download.
- [ ] **Publish** — push versioned packages to Cloudflare R2. Manual trigger is fine to start; automate later.
- [ ] **Reach out to opentrail.org's maintainer (GitHub: austinwritescode) to confirm data-reuse terms directly.** Their `/api/getData` endpoint (AT/PCT/CDT waypoints incl. resupply-relevant POIs) has no LICENSE file anywhere in the repo, so reuse rights aren't formally confirmed - the maintainer reportedly called it "open data" in a Reddit post ([r/Ultralight](https://www.reddit.com/r/Ultralight/comments/11gf2aw/announcing_a_free_guthookfarout_alternative/)), which is why we're proceeding with location/POI data only for now (deliberately excluding their user comments - those are personal contributions from named individuals, a separate consent concern from copyright), but this needs a real answer, not an informal comment-thread reference. Good opportunity for reciprocity too - OurHike intends to be open data itself (value #3, #6; see FEATURES.md "Data openness & portability"), so this can be a two-way conversation once there's something functional to show them.
- [ ] **Decide where/how the pipeline actually runs in production.** It should not run inside the client app or as an always-on service — source data (ATC/USGS/OSM) changes rarely, so this is a script run centrally on some slow cadence (manual trigger by a maintainer vs. a scheduled job like GitHub Actions cron are the two obvious options). Deserves more thought than v1 needs right now — revisit once the full pipeline (corridor/clip/export) exists and there's a real cadence to design around, rather than deciding upfront.

## Phase 2 — Client app (MVP)

- [ ] **Scaffold the PWA** — React + TypeScript, Vite, basic service worker + manifest.
- [ ] **Map rendering** — MapLibre GL JS reading PMTiles directly in-browser (via the `pmtiles` library's MapLibre protocol handler).
- [ ] **Offline download flow** — let a hiker pick a trail section to download before losing signal; store via Cache API/IndexedDB. This is the core "why would I use this instead of a browser tab" feature.
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
