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

Nineteen docs in [features/](features/) — eighteen features and one consolidated reference. Design is written before code here; that convention is the reason most issues can link to a doc instead of restating it.

A cross-feature alignment review on 2026-07-28 moved **Authentication**, **Report a Problem**, Map Options' **closures**, and Hiker Safety's **warnings and wrong-way alert** into the v1 MVP — see TECHNICAL_ARCHITECTURE.md's revised Backend section. The scope column reflects that revision, not the scope each doc originally launched with.

| Doc | Scope |
|---|---|
| [AUTHENTICATION.md](features/AUTHENTICATION.md) | **v1 MVP.** Google/Apple/email sign-in, verification, optional MFA. Browsing the map still needs no account — this exists so a reporter or moderator can be identified. Foundational for Segments, Volunteering and Report a Problem. |
| [REPORT_A_PROBLEM.md](features/REPORT_A_PROBLEM.md) | **v1 MVP.** Hiker-submitted condition reports, with "bad hikers" routed internal-only. Closures and safety warnings reuse this exact moderation mechanism. |
| [SAYING_THANKS.md](features/SAYING_THANKS.md) | **v1 MVP.** A thanks is a comment about a specific place — a report type sharing every field, diverging in visibility and in skipping the moderation queue. Resolved WIREFRAMES.md's Known Deviations #2. |
| [TRAIL_BLAZE_COLORS.md](features/TRAIL_BLAZE_COLORS.md) | **v1 MVP.** Render the trail in its real painted blaze colour, neutral fallback when unknown. A correctness detail, not a flourish. |
| [HIKER_SAFETY.md](features/HIKER_SAFETY.md) | **Split.** Warning pins and the wrong-way alert are v1 MVP; the anonymity window and the NWS weather relay are Post-MVP. |
| [MAP_OPTIONS.md](features/MAP_OPTIONS.md) | **Split.** Trail closures and the map-chrome spec (legend/scale/locate/zoom) are v1 MVP; background tile options, roads/sidewalks and snap-to-segment are Post-MVP. |
| [ONBOARDING.md](features/ONBOARDING.md) | **Split.** The minimal first-run flow is v1 MVP; trail names, settings mention and tips wait on Authentication and UX Customization. |
| [UX_CUSTOMIZATION.md](features/UX_CUSTOMIZATION.md) | **Split.** Most is MVP detail or light settings polish; auto-rotate is real Post-MVP work given the platform constraints. |
| [SPUR_TRAILS.md](features/SPUR_TRAILS.md) | **Scope call.** The rendering half already ships; linking a spur to its destination is a contained pipeline addition — [#111](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/111). |
| [IDENTITY_AND_PRIVACY.md](features/IDENTITY_AND_PRIVACY.md) | **Reference, not a feature.** Ties together identity/privacy design scattered across five docs, and replaces five small settings models with one canonical `UserPreferences`. |
| [FEATURE_GATING.md](features/FEATURE_GATING.md) | **Post-MVP, recommended first.** Per-chapter flags and experiments via self-hosted GrowthBook, always evaluated locally so the app never depends on the flag service being reachable. |
| [LAND_OWNERSHIP.md](features/LAND_OWNERSHIP.md) | Post-MVP (a scope call). What kind of land surrounds the corridor, so that stepping off protected land is a visible act rather than an accident. |
| [PERSONALIZED_PACE.md](features/PERSONALIZED_PACE.md) | Post-MVP (a scope call). Naismith answers how long a stretch takes *a* hiker; this answers how long it takes *you*, today, with this pack. |
| [SEGMENTS.md](features/SEGMENTS.md) | Post-MVP. Hierarchical Hike → Segment tree for thru-, section- and day-hikes. |
| [TRIP_PLANNING.md](features/TRIP_PLANNING.md) | Post-MVP. Builds on Segments: waypoint planning, bulk date shifts, POI-aware assistance. |
| [VOLUNTEERING.md](features/VOLUNTEERING.md) | Post-MVP. Club work-project management, with upcoming projects shown on the map. |
| [DATA_NUDGES.md](features/DATA_NUDGES.md) | Post-MVP. Non-gamified prompts to keep POI data fresh — no notifications, just map prominence for stale data, self-limiting the moment anyone contributes. |
| [COMMUNITY_BUILDING.md](features/COMMUNITY_BUILDING.md) | Post-MVP. Tramily formation, check-ins, mentions. The project's sharpest privacy-vs-connection tension, resolved as a scoped exception rather than a loosened stance. |
| [PRICING_MODEL.md](features/PRICING_MODEL.md) | Post-MVP, timing deliberately undecided. Thru-hike pass, regional pass, volunteer exemption, annual ceiling. |

Plus [WEBSITE.md](WEBSITE.md) at the repository root — not a feature but the plan for the web surface itself, added 2026-08-03. See Phase 4.

---

## Phase 1 — Data pipeline

**Built.** DuckDB spatial work proven on the real 3,025-segment centerline, unioned into one ~81,138 sq mi corridor polygon. The raster side validated at full scale across 1,654 US Topo quads, each reprojected from its native UTM zone before merging, with corrupt USGS-hosted quads skipped rather than crashing the run. ATC, opentrail and USGS ingestion are all change-aware, checking a cheap upstream signal and skipping the expensive pull when nothing moved. Elevation sampled densely along real centerline geometry rather than at the sparse half-mile markers. Export to PMTiles and GeoJSON/FlatGeobuf with per-artifact content hashes and blaze-colour normalisation. Three background detail tiers built (z11 ~64 MB, z12 ~314 MB, z13 ~1.18 GB), plus the Protomaps-derived extended-context basemap for panning beyond the corridor. Publishing runs as a CI workflow.

The design and the findings behind all of it live in [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)'s Data pipeline section and [pipeline/README.md](pipeline/README.md). The release process this grew into is specified in [pipeline/DATA_RELEASES.md](pipeline/DATA_RELEASES.md), which supersedes the original change-aware publish plan.

**Still open:** [#96](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/96) nothing runs the freshness check on a schedule · [#97](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/97) NHD stream-crossings as a water source · [#98](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/98) opentrail.org licensing · [#99](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/99) POI schema beyond its first slice · [#100](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/100) the dbt transform layer · [#111](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/111) spur destinations.

## Phase 2 — Client app & backend

**Built.** Every MVP screen was wireframed in [WIREFRAMES.md](WIREFRAMES.md) and then built: the map with offline PMTiles, blaze-coloured trail line and map chrome; the resumable whole-corridor download with its Light/Standard/Fine detail choice; POI search; the elevation ribbon with Naismith estimates; onboarding; reporting with its offline outbox; closures; serious-warning pins; the wrong-way cue; settings. The backend covers reports, closures, moderation, hikes, preferences, wrong-way and profiles on FastAPI + SQLAlchemy with Supabase JWT auth.

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
- **The dbt transform layer** ([#100](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/100)) — timing-driven rather than sequence-driven. NYNJTC's own non-AT network is expected on a near-term timeline, and this is what makes onboarding it "new rows and new staging models" rather than a second parallel pipeline. Distinct from the soft launch in Phase 4, which is NYNJTC members using the AT app.

Everything else — trail magic, multi-club tooling, weather, segments, trip planning, community building, data nudges, water reliability prediction, land ownership, personalised pace, data portability — stays described in [FEATURES.md](FEATURES.md) and [features/](features/) rather than filed as tasks. It is intended state, not open work, and filing thirty vague epics would leave the tracker exactly as trustworthy as the checklists this document used to carry.
