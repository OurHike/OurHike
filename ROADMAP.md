# OurHike — Roadmap

Companion to [OurHikeValues.md](OurHikeValues.md), [FEATURES.md](FEATURES.md), and [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md).

**This document describes the phases and what each one means. It does not track open work.** Open work lives in [Issues](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues), because a task with a state and an owner belongs somewhere that state changes when a pull request merges, rather than somewhere someone has to remember to tick a box. See [CONTRIBUTING.md](CONTRIBUTING.md#where-things-are-written-down) for the split between the two.

The checklists this file used to carry are gone, for a reason worth recording: by the end of July 2026 this roadmap still showed the entire client and backend as unbuilt, while both were built, tested and passing CI. It also carried an index that omitted four feature docs and listed a fifth twice, and pointed at a resolved question as still open. Nothing was wrong with the plan — the plan just was never the thing being updated.

**Where the project actually is:** pipeline, backend and client are all built and green, and every data artifact has been built locally. Nothing is published anywhere yet, and the remaining work to change that is mostly accounts and credentials rather than code. If you want a working map, [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) is the document to read — it is the ordered runbook, and it is current.

| Where to look | For |
|---|---|
| [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) | The ordered steps to get v1 deployed |
| [`v1-mvp`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/v1-mvp) | What still blocks launch |
| [`post-mvp`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/post-mvp) | Designed, deliberately not started |
| [`good first issue`](https://github.com/jaimito-asuntos-gringuenos/OurHike/labels/good%20first%20issue) | Somewhere to start |
| [FEATURES.md](FEATURES.md) + [features/](features/) | Everything else, as design rather than as tasks |

---

## Feature design docs

Twenty-two docs in [features/](features/) — twenty-one features and one consolidated reference. Design is written before code here; that convention is the reason most issues can link to a doc instead of restating it.

A cross-feature alignment review on 2026-07-28 moved **Authentication**, **Report a Problem**, Map Options' **closures**, and Hiker Safety's **warnings and wrong-way alert** into the v1 MVP — see TECHNICAL_ARCHITECTURE.md's revised Backend section. The scope column reflects that revision, not the scope each doc originally launched with.

| Doc | Scope |
|---|---|
| [AUTHENTICATION.md](features/AUTHENTICATION.md) | **v1 MVP.** Google/Apple/email sign-in, verification, optional MFA. Browsing the map still needs no account — this exists so a reporter or moderator can be identified. Foundational for Segments, Volunteering and Report a Problem. |
| [REPORT_A_PROBLEM.md](features/REPORT_A_PROBLEM.md) | **v1 MVP.** Hiker-submitted condition reports, with "bad hikers" routed internal-only. Closures and safety warnings reuse this exact moderation mechanism. |
| [SAYING_THANKS.md](features/SAYING_THANKS.md) | **v1 MVP.** A thanks is a comment about a specific place — a report type sharing every field, diverging in visibility and in skipping the moderation queue. Resolved WIREFRAMES.md's Known Deviations #2. |
| [TRAIL_BLAZE_COLORS.md](features/TRAIL_BLAZE_COLORS.md) | **v1 MVP.** Render the trail in its real painted blaze colour, neutral fallback when unknown. A correctness detail, not a flourish. |
| [HIKER_SAFETY.md](features/HIKER_SAFETY.md) | **Split.** Warning pins and the wrong-way alert are v1 MVP; the anonymity window and the NWS weather relay are Post-MVP. |
| [MAP_OPTIONS.md](features/MAP_OPTIONS.md) | **Split.** Trail closures and the map-chrome spec (legend/scale/locate/zoom) are v1 MVP. Background tile options were Post-MVP but shipped early 2026-08-03 — the downloaded raster was bad in ways no pipeline work fixes, so the live vector topo sheet went in instead. Roads/sidewalks and snap-to-segment stay Post-MVP. |
| [ONBOARDING.md](features/ONBOARDING.md) | **Split.** The minimal first-run flow is v1 MVP; trail names, settings mention and tips wait on Authentication and UX Customization. |
| [UX_CUSTOMIZATION.md](features/UX_CUSTOMIZATION.md) | **Split.** Most is MVP detail or light settings polish; auto-rotate is real Post-MVP work given the platform constraints. |
| [ELEVATION_PROFILE.md](features/ELEVATION_PROFILE.md) | **v1 MVP.** The phone's elevation ribbon and waypoint lanes: the ten-mile window, why it is asymmetric, and what counts as the climb ahead. Was missing from this table until 2026-08-05 — it shipped without ever being indexed here. |
| [SPUR_TRAILS.md](features/SPUR_TRAILS.md) | **Scope call.** The rendering half already ships; linking a spur to its destination is a contained pipeline addition — [#111](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/111). |
| [IDENTITY_AND_PRIVACY.md](features/IDENTITY_AND_PRIVACY.md) | **Reference, not a feature.** Ties together identity/privacy design scattered across five docs, and replaces five small settings models with one canonical `UserPreferences`. |
| [FEATURE_GATING.md](features/FEATURE_GATING.md) | **Post-MVP, recommended first.** Per-chapter flags and experiments via self-hosted GrowthBook, always evaluated locally so the app never depends on the flag service being reachable. |
| [LAND_OWNERSHIP.md](features/LAND_OWNERSHIP.md) | Post-MVP (a scope call). What kind of land surrounds the corridor, so that stepping off protected land is a visible act rather than an accident. |
| [PERSONALIZED_PACE.md](features/PERSONALIZED_PACE.md) | Post-MVP (a scope call). Naismith answers how long a stretch takes *a* hiker; this answers how long it takes *you*, today, with this pack. |
| [SEGMENTS.md](features/SEGMENTS.md) | Post-MVP. Hierarchical Hike → Segment tree for thru-, section- and day-hikes. |
| [TRIP_PLANNING.md](features/TRIP_PLANNING.md) | Post-MVP. Builds on Segments: waypoint planning, bulk date shifts, POI-aware assistance. |
| [HIKE_PLANNING.md](features/HIKE_PLANNING.md) | **v2, first feature — a spike, not yet a build.** The route builder, multi-day plans, the day/section/trail roll-up, zero days and resupply, the timeline and its food carry, the auto-generated plan, and what happens to the rest of the plan when today changes. Draws Segments and Trip Planning together rather than restating either. |
| [VOLUNTEERING.md](features/VOLUNTEERING.md) | **v2, second feature.** The Volunteer tab: contributing conditions, a fourteen-day map of work projects with in-app signup, Ridge Runner At-Large, logged hours, and a private impact record. Club work-project management is now the last of six pieces rather than the whole doc. |
| [SOURCE_REGISTRY.md](features/SOURCE_REGISTRY.md) | Post-MVP. How an outside organization registers its own map layers and a contact to notify. Registration is a form; the build input stays a reviewed file, so nothing self-service can change a hiker's map without a merge. |
| [DATA_NUDGES.md](features/DATA_NUDGES.md) | Post-MVP. Non-gamified prompts to keep POI data fresh — no notifications, just map prominence for stale data, self-limiting the moment anyone contributes. |
| [COMMUNITY_BUILDING.md](features/COMMUNITY_BUILDING.md) | Post-MVP. Tramily formation, check-ins, mentions. The project's sharpest privacy-vs-connection tension, resolved as a scoped exception rather than a loosened stance. |
| [PRICING_MODEL.md](features/PRICING_MODEL.md) | Post-MVP, timing deliberately undecided. Thru-hike pass, regional pass, volunteer exemption, annual ceiling. |

Plus [WEBSITE.md](WEBSITE.md) at the repository root — not a feature but the plan for the web surface itself, added 2026-08-03. See Phase 4.

---

## Phase 1 — Data pipeline

**Built.** DuckDB spatial work proven on the real 3,025-segment centerline, unioned into one ~81,138 sq mi corridor polygon. The raster side validated at full scale across 1,654 US Topo quads, each reprojected from its native UTM zone before merging, with corrupt USGS-hosted quads skipped rather than crashing the run. ATC, opentrail and USGS ingestion are all change-aware, checking a cheap upstream signal and skipping the expensive pull when nothing moved. Elevation sampled densely along real centerline geometry rather than at the sparse half-mile markers. Export to PMTiles and GeoJSON/FlatGeobuf with per-artifact content hashes and blaze-colour normalisation. Three background detail tiers built (z11 ~64 MB, z12 ~314 MB, z13 ~1.18 GB). Publishing runs as a CI workflow.

*Corrected 2026-08-06 (#196): this paragraph used to end "plus the Protomaps-derived extended-context basemap for panning beyond the corridor." That extract was measured, never built — no script produced it, `publish.py` never listed it, and no client source read it. Panning beyond the corridor offline is now answered inside every package instead ([pipeline/BASEMAP.md](pipeline/BASEMAP.md), decided with #189): `extract_package.py` keeps the whole build's footprint through z9, so the context travels with the sheet rather than as a second artifact.*

*Grown 2026-08-04, deliberately (#184):* the offline-map program added a second, vector-first half to this phase — a self-built OpenMapTiles basemap and a corridor DEM archive, so the hiking sheet the app draws is also the sheet that works offline — and the same day's scope call widened v1 coverage from the AT corridor to corridor plus all of New York state. Both are recorded as v1 cost in [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)'s risks; the program's design and measured numbers live in [pipeline/BASEMAP.md](pipeline/BASEMAP.md). First archives published 2026-08-06.

The design and the findings behind all of it live in [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)'s Data pipeline section and [pipeline/README.md](pipeline/README.md). The release process this grew into is specified in [pipeline/DATA_RELEASES.md](pipeline/DATA_RELEASES.md), which supersedes the original change-aware publish plan.

**Still open:** [#96](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/96) nothing runs the freshness check on a schedule · [#97](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/97) NHD stream-crossings as a water source · [#98](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/98) opentrail.org licensing · [#99](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/99) POI schema beyond its first slice · [#100](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/100) the dbt transform layer · [#111](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/111) spur destinations.

## Phase 2 — Client app & backend

**Built.** Every MVP screen was wireframed in [WIREFRAMES.md](WIREFRAMES.md) and then built: the map with offline PMTiles, blaze-coloured trail line and map chrome; the resumable whole-corridor download with its Light/Standard/Fine detail choice; POI search; the elevation ribbon with Naismith estimates; onboarding; reporting with its offline outbox; closures and serious-warning pins, drawn from the backend's own reads ([#286](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/286), [#232](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/232)); settings. The wrong-way cue is built and tested but deliberately not yet mounted: its detection thresholds are wireframe placeholders pending field testing ([#93](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/93)), and false alarms from placeholder numbers would spend the trust budget the feature is designed around. The backend covers reports, closures, moderation, hikes, preferences, wrong-way and profiles on FastAPI + SQLAlchemy with Supabase JWT auth.

Browsing stays account-free. Only the contribution paths need a live backend — see TECHNICAL_ARCHITECTURE.md's Backend section for why the line falls where it does.

**Still open:** [#89](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/89) photo picker discards photos · [#90](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/90) POIs are never drawn on the map · [#91](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/91) cumulative ascent over-counts · [#93](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/93) wrong-way thresholds are placeholders · [#105](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/105) outdoor usability pass. Verification gaps: [#92](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/92) real OAuth · [#94](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/94) end-to-end against published artifacts · [#95](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/95) real Postgres.

Feature gating was listed in this phase originally; it is Post-MVP — [#110](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/110).

## Phase 3 — App store packaging

**Not started.** The PWA is the product; these wrap the same build rather than reimplementing it.

[#101](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/101) Capacitor · [#102](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/102) iOS and TestFlight · [#103](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/103) Android · [#104](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/104) listing assets and privacy policy.

## Phase 4 — Launch readiness

**Not started**, and largely gated on there being something published to test against.

[#106](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/106) real-trail field testing, which several other issues wait behind · [#107](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/107) web-only payments · [#108](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/108) the inheritance guide for the next club · [#109](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/109) soft launch with NYNJTC.

**The web surface, planned 2026-08-03 in [WEBSITE.md](WEBSITE.md).** `site/index.html` is the app's Downloads screen restyled at phone width, and the client has no `@media` rule anywhere — so FEATURES.md's MVP promise of the "same core experience on phone and web" is not met today. Two tracks that do not block each other: [#116](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/116) builds the site, [#117](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/117) gives the app a desktop layout. Photography sourcing starts before either, having the longest lead time. Payments depend on this too — checkout has exactly one place it is allowed to live, and the site as shipped has no page for it.

## Phase 5+ — after launch

Less a phase than a set of designs waiting for evidence. Two have a reason to be built early:

- **Feature gating** ([#110](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/110)) — recommended first, because every feature built afterwards gets real evidence instead of a guess.
- **The dbt transform layer** ([#100](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/100)) — timing-driven rather than sequence-driven. NYNJTC's own non-AT network is expected on a near-term timeline, and this is what makes onboarding it "new rows and new staging models" rather than a second parallel pipeline. Distinct from the soft launch in Phase 4, which is NYNJTC members using the AT app. [SOURCE_REGISTRY.md](features/SOURCE_REGISTRY.md) is where the rows come from once the organization supplying them isn't ATC.

Everything else — trail magic, multi-club tooling, weather, segments, trip planning, community building, data nudges, water reliability prediction, land ownership, personalised pace, data portability — stays described in [FEATURES.md](FEATURES.md) and [features/](features/) rather than filed as tasks. It is intended state, not open work, and filing thirty vague epics would leave the tracker exactly as trustworthy as the checklists this document used to carry.

---

## v2 — planning a hike

**Named here for the first time, 2026-08-05.** Everything above is v1: getting a trustworthy offline map of the Appalachian Trail into a hiker's hand and launched. v1 answers *where am I, what is around me, and can I believe it.*

**v2 is the first release where OurHike does something with the trail rather than only showing it**, and its first feature is planning a hike — a route laid out on the map, broken into days, rolled up into sections and a whole thru-hike, with the distance, climb, time and food each of those needs.

That is a larger step than any single v1 screen was, so it starts as a spike rather than as a build: [features/HIKE_PLANNING.md](features/HIKE_PLANNING.md), with [pipeline/spike_day_planner.py](pipeline/spike_day_planner.py) as its runnable half. The doc names what is already answerable from data this repository holds, what has to be measured against real ATC data before anything is built, and a five-phase build order where each phase is useful on its own.

Two things it turned up that are worth knowing even if the feature never gets built:

- **This repository measures "a mile" two different ways** — `client/src/lib/trailPosition.ts` and `pipeline/export_elevation.py` — and the elevation ribbon already compares them as though they were one measurement. Harmless over a ten-mile window, not harmless summed across a 2,190-mile plan. Fixing it is Phase A, and it is worth doing whether or not Phase B follows.
- **The auto-planner needs no backend.** Choosing day boundaries out of 512 shelters and campsites is a shortest path over roughly 3,000 edges — less arithmetic than one frame of the map — so the only architectural question it could have raised is answered before it is asked.

v2's shape beyond this feature is deliberately not sketched here. One feature designed properly is worth more than a list, and this one is big enough to teach us what the rest should be.

## v2 — volunteering

**Scoped 2026-08-06 as v2's second feature: [features/VOLUNTEERING.md](features/VOLUNTEERING.md).** Where planning a hike is the app doing something *with* the trail, this is the app doing something *for* it — the gap between hiking a trail and maintaining one, which is the reason this project exists at all rather than a feature it happens to want.

Six pieces behind a third tab: opting in to contribute conditions, a fourteen-day map of work projects a hiker can sign up for, the Ridge Runner At-Large commitment, logged hours, a private record of what someone has contributed, and the club-side module that confirms it. The doc argues the tab name rather than assuming it, and lands on `Volunteer`.

Three things it settled that reach beyond it:

- **The anti-gamification guardrail now has a stated boundary.** Four docs had said "no per-hiker contribution counts shown anywhere" and a personal impact record is, on its face, exactly that. The resolution — the guardrail targets *comparison and pressure*, not *memory* — is written down with the four rules that keep it honest, so the next feature to hit this does not have to relitigate it.
- **[PRICING_MODEL.md](features/PRICING_MODEL.md)'s volunteer exemption is unblocked**, and now has a named phase to wait for rather than an open dependency on a design that did not exist.
- **[DATA_NUDGES.md](features/DATA_NUDGES.md), designed in July and never built, is Phase A.** It is the piece that touches every hiker rather than the few who attend a workday, and it is worth building whether or not the rest follows.
