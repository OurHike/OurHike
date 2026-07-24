# OurHike — Roadmap / Build Plan (Draft v1)

Companion to [OurHikeValues.md](OurHikeValues.md), [FEATURES.md](FEATURES.md), and [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md). Ordered, phased list of what needs to get built and how, from where we are now (decided architecture) to a shippable v1. Expect this to shift as decisions firm up — check items off as they're done, add detail as it emerges.

---

## Phase 0 — Groundwork

- [ ] **Confirm ATC data access & licensing.** Reach out to ATC about using their GIS data (centerline, shelters, campsites, water, crossings, resupply) in OurHike and what redistribution terms look like. FarOut's existing use of the same data is a useful precedent to point to. *(User offered to help make the connection.)*
- [ ] **Get a Mac for iOS builds.** Apple's toolchain requires macOS regardless of framework. *(User is handling this.)*
- [ ] **Register a domain** (e.g. ourhike.org).
- [ ] **Set up hosting accounts** — Cloudflare (Pages for the app, R2 for offline map data), free tier to start.
- [ ] **Set up the dev environment** — Python (DuckDB + spatial extension, GeoPandas) for the pipeline; Node/TypeScript toolchain for the client. Document setup steps as they're nailed down (feeds a future CONTRIBUTING.md — value #7, inheritability).

## Phase 1 — Data pipeline

- [ ] **DuckDB spatial spike.** Prove the core operation works before building on top of it: buffer the AT centerline by 30 miles, clip a real OSM/USGS extract against it, export the result. Can start against public AT centerline data even before ATC access is finalized, since this is validating the *method*, not the final dataset. *(Explicitly punted earlier — first real coding task when picked back up.)*
- [ ] **Ingestion scripts** — pull raw extracts from ATC (POIs), USGS (elevation/topo), OSM (roads/land cover) into formats DuckDB reads directly (GeoJSON/Shapefile/GeoPackage/FlatGeobuf). *(ATC side started — see `pipeline/`: `discover_sources.py` finds layer URLs from ATC's public ArcGIS map, `fetch_all.py` pulls all 9 registered layers. USGS/OSM ingestion not started.)*
- [ ] **Corridor computation** — generate the 30-mile buffer once (`ST_Buffer` + `ST_Union` over the centerline + waypoints).
- [ ] **Clip & join** — intersect USGS/OSM against the corridor; join ATC POI layers into one schema.
- [ ] **Unified POI schema** — one schema for water/shelter/campsite/crossing/resupply, designed to not bake in AT-only or NYNJTC-only assumptions (value #7), even though only the AT is in scope for v1.
- [ ] **Export** — base map as PMTiles, POI layers as GeoJSON/FlatGeobuf. Check package sizes are reasonable for a phone download.
- [ ] **Publish** — push versioned packages to Cloudflare R2. Manual trigger is fine to start; automate later.
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
