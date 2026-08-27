# OurHike — Roadmap

Companion to [OurHikeValues.md](OurHikeValues.md), [FEATURES.md](FEATURES.md), and [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md).

**This document describes the phases and what each one means. It does not track open work.** Open work lives in [Issues](https://github.com/OurHike/OurHike/issues), because a task with a state and an owner belongs somewhere that state changes when a pull request merges, rather than somewhere someone has to remember to tick a box. See [CONTRIBUTING.md](CONTRIBUTING.md#where-things-are-written-down) for the split between the two.

The checklists this file used to carry are gone, for a reason worth recording: by the end of July 2026 this roadmap still showed the entire client and backend as unbuilt, while both were built, tested and passing CI. It also carried an index that omitted four feature docs and listed a fifth twice, and pointed at a resolved question as still open. Nothing was wrong with the plan — the plan just was never the thing being updated.

**Where the project actually is (updated 2026-08-17, #661 — the previous version of this sentence said nothing was published, for weeks after the bucket went live):** v1.0.0 shipped 2026-08-16. The data publishes to R2 as a CI workflow, the app is live at ourhike.org, and the work is v2 — [V2_PLAN.md](V2_PLAN.md) is the document to read. What is *not* real yet: the backend is not hosted anywhere (#600 — so reporting still has nowhere to send), real OAuth is unexercised end to end (#92), and the migration has never been applied to Supabase's Postgres. [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) remains the runbook of record for how v1 got out, and for the ops steps still open.

| Where to look | For |
|---|---|
| [V2_PLAN.md](V2_PLAN.md) | Every open issue, grouped into bodies of work a session can pick up |
| [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) | The ordered steps that got v1 deployed — now a runbook of record |
| [`v2`](https://github.com/OurHike/OurHike/labels/v2) | Every open issue — the current work is all v2 |
| [`good first issue`](https://github.com/OurHike/OurHike/labels/good%20first%20issue) | Somewhere to start |
| [FEATURES.md](FEATURES.md) + [features/](features/) | Everything else, as design rather than as tasks |

*Two label rows used to sit in that table and both stopped being true (#601): `v1-mvp` said "what still blocks launch" after v1 had launched, and `post-mvp` had come to sit only on issues that were all also `v2`, so it was removed from every open issue on 2026-08-17. Both labels survive on closed issues as history.*

---

## Feature design docs

Thirty-five docs in [features/](features/) — thirty-three features and two consolidated references. Design is written before code here; that convention is the reason most issues can link to a doc instead of restating it. The table below is six rows short of the directory: CONDITIONS_DELIVERY.md, CORRIDOR_VIEW.md, MAP_STYLE_SPEC.md, POI_PHOTOS.md, POI_SITES.md and POI_VISIBILITY.md are written and unlisted — a count this paragraph had let drift to "three" while three more docs landed unindexed, corrected 2026-08-13 in the change that added a row. ATC_TRAIL_UPDATES.md was the fourth until 2026-08-12, and it is worth naming what that cost: the feature carried `v1-mvp` labels on three issues while neither of the two documents a person reads to learn what v1 *is* mentioned it at all. ELEVATION_PROFILE.md below records the same gap ending the same way, which is twice.

A cross-feature alignment review on 2026-07-28 moved **Authentication**, **Report a Problem**, Map Options' **closures**, and Hiker Safety's **warnings and wrong-way alert** into the v1 MVP — see TECHNICAL_ARCHITECTURE.md's revised Backend section. The scope column reflects that revision, not the scope each doc originally launched with.

| Doc | Scope |
|---|---|
| [AUTHENTICATION.md](features/AUTHENTICATION.md) | **v1 MVP.** Google/Apple/email sign-in, verification, optional MFA. Browsing the map still needs no account — this exists so a reporter or moderator can be identified. Foundational for Segments, Volunteering and Report a Problem. |
| [REPORT_A_PROBLEM.md](features/REPORT_A_PROBLEM.md) | **v1 MVP.** Hiker-submitted condition reports, with "bad hikers" routed internal-only. Closures and safety warnings reuse this exact moderation mechanism. |
| [SAYING_THANKS.md](features/SAYING_THANKS.md) | **v1 MVP.** A thanks is a comment about a specific place — a report type sharing every field, diverging in visibility and in skipping the moderation queue. Resolved WIREFRAMES.md's Known Deviations #2. |
| [TRAIL_BLAZE_COLORS.md](features/TRAIL_BLAZE_COLORS.md) | **v1 MVP.** Render the trail in its real painted blaze colour, neutral fallback when unknown. A correctness detail, not a flourish. |
| [HIKER_SAFETY.md](features/HIKER_SAFETY.md) | **Split.** Warning pins and the wrong-way alert are v1 MVP; the anonymity window and the NWS weather relay are Post-MVP. |
| [MAP_OPTIONS.md](features/MAP_OPTIONS.md) | **Split.** Trail closures and the map-chrome spec (legend/scale/locate/zoom) are v1 MVP. Background tile options were Post-MVP but shipped early 2026-08-03 — the downloaded raster was bad in ways no pipeline work fixes, so the live vector topo sheet went in instead. Roads/sidewalks and snap-to-segment stay Post-MVP. |
| [ATC_TRAIL_UPDATES.md](features/ATC_TRAIL_UPDATES.md) | **v1 MVP.** The ATC publishes closures, detours and hazards on their website in NOBO miles from Springer — the same number `start_mile_marker` already is — so placing one is a join against data the build already holds, not a geocoding problem. Shipped as the ATC's own word rather than OurHike's: their name on the claim, their date, and a link to their page. The registration, the bake and the rendering are built; the rows are a reviewed file a person fills in, because a regex deciding what a safety surface says is the one thing this design refuses. |
| [ONBOARDING.md](features/ONBOARDING.md) | **Split.** The minimal first-run flow is v1 MVP; trail names, settings mention and tips wait on Authentication and UX Customization. |
| [UX_CUSTOMIZATION.md](features/UX_CUSTOMIZATION.md) | **Split.** Most is MVP detail or light settings polish; auto-rotate is real Post-MVP work given the platform constraints. |
| [ELEVATION_PROFILE.md](features/ELEVATION_PROFILE.md) | **v1 MVP.** The phone's elevation ribbon and waypoint lanes: the ten-mile window, why it is asymmetric, and what counts as the climb ahead. Was missing from this table until 2026-08-05 — it shipped without ever being indexed here. |
| [SPUR_TRAILS.md](features/SPUR_TRAILS.md) | **Scope call.** The rendering half already ships; linking a spur to its destination is a contained pipeline addition — [#111](https://github.com/OurHike/OurHike/issues/111). |
| [IDENTITY_AND_PRIVACY.md](features/IDENTITY_AND_PRIVACY.md) | **Reference, not a feature.** Ties together identity/privacy design scattered across five docs, and replaces five small settings models with one canonical `UserPreferences`. |
| [FEATURE_GATING.md](features/FEATURE_GATING.md) | **Post-MVP, recommended first.** Per-chapter flags and experiments via self-hosted GrowthBook, always evaluated locally so the app never depends on the flag service being reachable. |
| [EVENTING.md](features/EVENTING.md) | **v2. Reference, not a feature.** How OurHike measures itself: DAU/WAU/MAU with no identifier of any kind, task outcomes rather than engagement counts, and experiments measured from aggregates. Owns the event taxonomy FEATURE_GATING.md sketched and deferred. |
| [LAND_OWNERSHIP.md](features/LAND_OWNERSHIP.md) | Post-MVP (a scope call). What kind of land surrounds the corridor, so that stepping off protected land is a visible act rather than an accident. |
| [PERSONALIZED_PACE.md](features/PERSONALIZED_PACE.md) | Post-MVP (a scope call). Naismith answers how long a stretch takes *a* hiker; this answers how long it takes *you*, today, with this pack. |
| [SEGMENTS.md](features/SEGMENTS.md) | Post-MVP. Hierarchical Hike → Segment tree for thru-, section- and day-hikes. |
| [TRIP_PLANNING.md](features/TRIP_PLANNING.md) | Post-MVP. Builds on Segments: waypoint planning, bulk date shifts, POI-aware assistance. |
| [HIKE_PLANNING.md](features/HIKE_PLANNING.md) | **v2, first feature — a spike, not yet a build.** The route builder, multi-day plans, the day/section/trail roll-up, zero days and resupply, the timeline and its food carry, the auto-generated plan, and what happens to the rest of the plan when today changes. Draws Segments and Trip Planning together rather than restating either. |
| [VOLUNTEERING.md](features/VOLUNTEERING.md) | **v2, second feature.** The Volunteer tab: contributing conditions, a fourteen-day map of work projects with in-app signup, Ridge Runner At-Large, logged hours, and a private impact record. Club work-project management is now the last of six pieces rather than the whole doc. |
| [FIELD_NOTES.md](features/FIELD_NOTES.md) | **v2, third feature.** What the app does when upstream data and the field disagree: upstream owns identity, the field owns condition, and the two layer rather than merge so nobody has to adjudicate. Dated observations on a POI, the roll-up that gives the staleness tiers a producer at last, and a disputed pin that files the correction upstream instead of forking ATC's data. |
| [PHOTO_DOWNLOADS.md](features/PHOTO_DOWNLOADS.md) | **v2, fourth feature — a spike, not yet a build.** Getting a hike's photos onto the phone before the hike starts: download and update as the two real verbs, one mile-range scope mechanism serving a day, a section, a hike or the whole trail, and an automatic fetch capped by bytes rather than by a wifi test the PWA cannot perform. Measures the corpus and finds it far smaller than POI_PHOTOS.md's size budget assumed. |
| [DATA_ENVIRONMENTS.md](features/DATA_ENVIRONMENTS.md) | **v2, fifth feature — built.** Somewhere for UA to be wrong that is not what hikers download. Every published source reviewed for whether sharing it is safe, an environment made into a bucket prefix with production staying at the root, and `publish.py` refusing to run until it is told which environment it is writing to. |
| [POI_IDENTITY.md](features/POI_IDENTITY.md) | **v2, sixth feature — platform, not a screen.** A POI's published id is minted at first sight and owned for life: upstream keys become matching evidence rather than identity, a checked-in ledger reconciles the ATC's annual refresh — by key where keys survive, by evidence where they don't, by retiring into a tombstone where the place is gone — and a human reviews the ledger's diff on the release PR, never every point. What keeps photos, comments and saved plans anchored across the years. |
| [POI_DEDUPLICATION.md](features/POI_DEDUPLICATION.md) | **v2, seventh feature — platform, not a screen.** What happens when two sources describe one place: proximity proposes and evidence decides, precedence runs per field rather than per record so a merge combines instead of discarding, the decision is written as a `superseded_by` edge in POI_IDENTITY.md's ledger rather than a second one, and the duplicate check runs at submission time where the hiker who is standing there can answer it. Measured: 48 same-type pairs sit within 25 m of each other on the corridor and 35 of them are two real places, so the radius proposes and the name decides. |
| [ACCOUNT_SYNC.md](features/ACCOUNT_SYNC.md) | **v2, ninth feature — designed, not started.** A hiker's own content follows their account between the web and their phone: what syncs and at what grain, why the device holds the truth while it is offline, why a conflict keeps both plans rather than picking one, and why sharing a photo and syncing one must never become the same act. Measured: 23 device storage keys sorted into the hiker's and the device's, and two finished endpoints nothing has ever called. |
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

**Still open** (reconciled against the tracker 2026-08-17, #601 — the freshness schedule #96 and spur destinations #111 on the previous version of this list are done): [#97](https://github.com/OurHike/OurHike/issues/97) NHD stream-crossings as a water source · [#98](https://github.com/OurHike/OurHike/issues/98) opentrail.org licensing · [#99](https://github.com/OurHike/OurHike/issues/99) POI schema beyond its first slice · [#100](https://github.com/OurHike/OurHike/issues/100) the dbt transform layer.

## Phase 2 — Client app & backend

**Built.** Every MVP screen was wireframed in [WIREFRAMES.md](WIREFRAMES.md) and then built: the map with offline PMTiles, blaze-coloured trail line and map chrome; the resumable whole-corridor download with its Light/Standard/Fine detail choice; POI search; the elevation ribbon with Naismith estimates; onboarding; reporting with its offline outbox; closures as barrier tape along the closed miles, with a header banner for the one being walked into; serious-warning pins, with a count of those on the route; settings. The backend covers reports, closures, moderation, hikes, preferences, wrong-way and profiles on FastAPI + SQLAlchemy with Supabase JWT auth.

This line used to include **the wrong-way cue**, and it was wrong to. Every component in the list existed, which is presumably how it came to be written ([#232](https://github.com/OurHike/OurHike/issues/232)) — but a hiker on trail saw no closure, no warning pin and no wrong-way cue, because nothing mounted any of them and nothing fetched the data behind two of the three. The closures and the warning pins are real now. The wrong-way cue is still built and unmounted, deliberately: its thresholds are placeholders ([#93](https://github.com/OurHike/OurHike/issues/93)), and it is the only notification this app sends, so false alarms would spend the trust budget that single alert was designed around. The detail sheets came right too, each by a decision per field rather than a sync: the closure sheet's fields got real columns a maintainer can set (#245, closed 2026-08-08), and the serious-warning sheet was cut down to say only what the backend can stand behind (#292, closed 2026-08-13).

Browsing stays account-free. Only the contribution paths need a live backend — see TECHNICAL_ARCHITECTURE.md's Backend section for why the line falls where it does.

**Still open** (reconciled against the tracker 2026-08-17, #601 — the photo picker #89, unmapped POIs #90, ascent over-count #91 and published-artifact smoke test #94 on the previous version of this list are all done; #91's remaining half, validating the ascent threshold against published section figures, lives in [#133](https://github.com/OurHike/OurHike/issues/133)): [#93](https://github.com/OurHike/OurHike/issues/93) wrong-way thresholds are placeholders · [#105](https://github.com/OurHike/OurHike/issues/105) outdoor usability pass · [#133](https://github.com/OurHike/OurHike/issues/133) validate the ascent threshold. Verification gaps: [#92](https://github.com/OurHike/OurHike/issues/92) real OAuth · [#95](https://github.com/OurHike/OurHike/issues/95) real Postgres outside CI.

Feature gating was listed in this phase originally; it is Post-MVP — [#110](https://github.com/OurHike/OurHike/issues/110).

## Phase 3 — App store packaging

**Not started.** The PWA is the product; these wrap the same build rather than reimplementing it.

[#101](https://github.com/OurHike/OurHike/issues/101) Capacitor · [#102](https://github.com/OurHike/OurHike/issues/102) iOS and TestFlight · [#103](https://github.com/OurHike/OurHike/issues/103) Android · [#104](https://github.com/OurHike/OurHike/issues/104) listing assets and privacy policy.

## Phase 4 — Launch readiness

**Not started**, and largely gated on there being something published to test against.

[#106](https://github.com/OurHike/OurHike/issues/106) real-trail field testing, which several other issues wait behind · [#107](https://github.com/OurHike/OurHike/issues/107) web-only payments · [#108](https://github.com/OurHike/OurHike/issues/108) the inheritance guide for the next club · [#109](https://github.com/OurHike/OurHike/issues/109) soft launch with NYNJTC.

**The web surface, planned 2026-08-03 in [WEBSITE.md](WEBSITE.md).** Of its two tracks, one is done: [#117](https://github.com/OurHike/OurHike/issues/117) gave the app a desktop layout (closed 2026-08-03 — `client/src/desktop.css`, with tests; this paragraph used to say the client had no `@media` rule anywhere, which stopped being true the same week it was written). [#116](https://github.com/OurHike/OurHike/issues/116) — the real website — is still open: `site/index.html` remains the app's Downloads screen restyled, and photography sourcing has the longest lead time of anything in that plan. Payments depend on this too — checkout has exactly one place it is allowed to live, and the site as shipped has no page for it.

## Phase 5+ — after launch

Less a phase than a set of designs waiting for evidence. Two have a reason to be built early:

- **Feature gating** ([#110](https://github.com/OurHike/OurHike/issues/110)) — recommended first, because every feature built afterwards gets real evidence instead of a guess.
- **The dbt transform layer** ([#100](https://github.com/OurHike/OurHike/issues/100)) — timing-driven rather than sequence-driven. NYNJTC's own non-AT network is expected on a near-term timeline, and this is what makes onboarding it "new rows and new staging models" rather than a second parallel pipeline. Distinct from the soft launch in Phase 4, which is NYNJTC members using the AT app. [SOURCE_REGISTRY.md](features/SOURCE_REGISTRY.md) is where the rows come from once the organization supplying them isn't ATC.

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

## v2 — field notes

**Scoped 2026-08-09 as v2's third feature: [features/FIELD_NOTES.md](features/FIELD_NOTES.md).** Volunteering asks a hiker to contribute; this is what the app does with what they contribute, once it disagrees with what ATC published. Upstream is authoritative about what exists and where, and structurally silent about what a place is like today — its edit dates are the ceiling on its freshness, and trail data ships a few times a year. The field runs on the other clock entirely.

The design refuses the obvious move. Merging the two into one current-truth record needs an adjudicator, and that is a standing job nobody will hold — so the two layer instead: upstream owns identity, the field owns condition, and a hiker reads both with their dates attached. Nothing overwrites anything, so nothing needs adjudicating.

Three things it settled that reach beyond it:

- **[#256](https://github.com/OurHike/OurHike/issues/256) finally has an answer.** `client/src/lib/staleness.ts` has shipped the tiers since spring with, in that issue's words, "no consumer… no producer." The roll-up over field notes is the producer, and it is the first honest freshness signal the map has ever had.
- **A correction goes upstream rather than into a private layer.** A disputed POI routes to [SOURCE_REGISTRY.md](features/SOURCE_REGISTRY.md)'s steward for that source, so the fix lands in ATC's own data where every other consumer gets it too. The app becomes ATC's field reporting channel instead of a fork of ATC's data — which is what keeps the correction layer from becoming a maintenance burden that outlives whoever started it.
- **The unmoderated-contribution question is settled once, for two features.** Publishing first and removing on flags is what [SAYING_THANKS.md](features/SAYING_THANKS.md) needed and deferred, and the flag-and-hide path answers both rather than being built twice.

## v2 — photos for the hike

**Scoped 2026-08-09 as v2's fourth feature: [features/PHOTO_DOWNLOADS.md](features/PHOTO_DOWNLOADS.md), with [pipeline/spike_photo_scope.py](pipeline/spike_photo_scope.py) as its runnable half.** A photo fetched on a ridge is a photo that does not arrive, and [POI_PHOTOS.md](features/POI_PHOTOS.md) left offline delivery as its one open decision — the card fetches a URL when it renders and falls down the ladder with no signal. This is that decision, taken.

It is a smaller feature than the three above and it starts as a spike for a different reason: not because the shape is risky, but because two of the things asked for turned out to be conditions the app cannot currently evaluate, and one of them is measuring the wrong quantity.

Four findings worth surfacing here:

- **The corpus is far smaller than this repository believed.** POI_PHOTOS.md's size budget put offline photos at ~137 MB over 3,000 POIs and concluded that bundling everything was out. Measured, **489 POIs have a photo and the whole trail is ~71 MB** — about an eighth of the terrain package the app already ships. The estimate was wrong in both of its factors and they did not cancel. That doc's size budget is corrected in the same change.
- **The PWA cannot tell wifi from cellular, and on iOS it cannot tell anything** — `navigator.connection` is undefined in Safari, which `client/src/lib/dataSaver.ts` already documents. So "download on wifi" becomes **cap the bytes, not the link type**, which protects the same data plan on every platform today and improves rather than changes when [#101](https://github.com/OurHike/OurHike/issues/101) wires up Capacitor.
- **Content-addressing had already done most of the work.** `photos/<digest>.jpg` is the sha256 of the image, so a stored photo cannot go stale, verification needs no manifest, and the three verbs asked for collapse into two plus a local integrity check.
- **It wants the same prerequisite the planner does.** Every scope here — a day, a section, a hike, "near me" — is a mile range, which needs `mile` published on every POI. That is [HIKE_PLANNING.md](features/HIKE_PLANNING.md)'s Phase A, already the first thing that feature asks for and already worth doing on its own.

## v2 — somewhere to be wrong first

**Scoped 2026-08-13 as v2's fifth feature: [features/DATA_ENVIRONMENTS.md](features/DATA_ENVIRONMENTS.md).** The four features above all publish data a hiker reads, and none of them has anywhere to rehearse that. [RELEASING.md](RELEASING.md) built UA — its own origin, its own Supabase project, its own backend, deliberately no path to production's — and then left the bucket as the one thing both environments share. So UA and production read the same `trails.geojson`, the same POIs, the same daily-rewritten closures, and the only way to test a change to the publishing path was to run it over what hikers download.

It is the least visible thing in v2 and the one that makes the rest of v2 testable, which is the whole argument for doing it before them rather than after.

Two findings from reviewing every source rather than only the obvious one:

- **The backend already had this right, and the bucket was the exception.** `UA_API_BASE_URL` has deliberately no fallback to `API_BASE_URL`, because a UA build able to send would file test reports into a queue a club works from. That is the same argument one layer down, and R2 had been outside it since the first publish.
- **The source nobody would have listed is the one most worth splitting.** Photos are content-addressed, so a shared prefix can never serve wrong bytes — which is exactly why it reads as safe. It is the only hiker-facing prefix objects are *deleted* from, and a withdrawal is a promise made to whoever shared the photograph. Rehearsing that promise is what UA is for, and against a shared prefix the rehearsal would have taken the picture out of production.

The mechanism is one prefix per environment, with production staying at the bucket root because a published key can never be renamed — and `publish.py`, the only thing in the project that writes to the bucket, refusing to run until it is told which environment it is writing to. [RELEASING.md](RELEASING.md) §14.2 asked bucket-or-prefix and answered prefix; this is that answer built, plus the half it had not considered.

## v2 — identity that survives the years

**Scoped 2026-08-13 as v2's sixth feature: [features/POI_IDENTITY.md](features/POI_IDENTITY.md), tracked as [#666](https://github.com/OurHike/OurHike/issues/666) — *A POI's identity is its upstream key, so one ATC annual refresh can orphan every photo and comment*.** Every v2 feature above attaches something of a hiker's to a place — a plan's day boundaries, a field note, a photo, a gallery — and every one of those anchors is a POI id that today lives and dies with the upstream key it was composed from. The ATC refreshes its GIS data about once a year: names change, locations move by a few feet, POIs are added, removed and heavily edited, and distances are re-measured. If a refresh re-mints its keys — which an ArcGIS republish does wholesale, even for features that did not change — every stored reference dangles, and nothing today would notice.

The design moves identity from the key to a checked-in ledger: an id is minted at first sight and owned thereafter. A refresh is reconciled against the ledger — carried by key where keys survived, by evidence (distance, position along the trail, normalised name, ATC's own inventory fingerprint) where they did not, and retired into a tombstone where the place is genuinely gone, which keeps photos and comments recoverable instead of guessed onto the wrong place. The human reviews the reconciliation's diff on the release PR that is already every release's gate — never every point.

Three things it settles that reach beyond it:

- **[FIELD_NOTES.md](features/FIELD_NOTES.md) §7's orphan check becomes a backstop rather than the mechanism.** That section named the two break modes and could only report the damage after the fact; the ledger removes the causes, and the check stays to prove it.
- **Miles are a projection, not an anchor.** Closures store only mile markers, and a re-measure moves every mile a little. Closure endpoints gain geometry captured at authoring time, and the mile becomes a per-release display of it — [CONTRIBUTING.md](CONTRIBUTING.md)'s store-canonical-convert-at-display rule, applied to position.
- **A better source stops costing the history.** The day [#529](https://github.com/OurHike/OurHike/issues/529) (*97% of shelters have no water source within 250 m, and the trail is not like that*) lands a real water layer, evidence matching carries each spring's id — and every note anchored to it — across the source swap, instead of orphaning them as a side effect of an improvement.

## v2 — one place, one pin

**Scoped 2026-08-13 as v2's seventh feature: [features/POI_DEDUPLICATION.md](features/POI_DEDUPLICATION.md), tracked as [#696](https://github.com/OurHike/OurHike/issues/696) — *Nothing stops two sources publishing the same place twice, and the one rule that does is a 25 m constant for a single source pair*.** The feature above keeps a place's identity across time. This one keeps it across sources, and it is the other half of the same problem: every POI shipping today comes from a source that is ~1:1 with a `poi_type`, so two records for one place has been impossible by construction. Registered clubs, a second water layer and community submissions all end that at once, and each currently arrives with its own merge rule in whichever export function admitted it.

The measurement is what shaped the design, and it inverted the obvious rule. Across all 2,837 published points there are 48 same-type pairs within 25 m of each other — and **35 of them are two real places**, distinguished by a sibling number (`"Tumbling Run Shelter 1"` / `"... 2"`), a direction (`"The Horn (S)"` / `"(N)"`) or an outright different name. A blind radius rule deletes the Horns Pond lean-tos, The Birches lean-tos and both Grafton Notch privies, all of which this repository had already identified as genuinely two things. So proximity proposes and the *name* decides. What that leaves is small and real: 11 places holding 23 records, almost all of them ATC's viewpoint layer carrying one overlook twice, usually with a trailing "Vista" on one of them.

Three things it settles:

- **Precedence runs per field, not per record.** ATC owns where a shelter is and what it is called; it does not own a description it never wrote. A merge that keeps only the winner's row discards the tags, sentences and photos that were the point of having a second source — and it drops the losing source's licence obligations with them, which is a breach rather than an oversight.
- **The decision is a `superseded_by` edge in the identity ledger, not a second ledger.** The resolver, the tombstone, the CI regeneration check and the release-PR review all already exist there; this adds the rules for drawing the edge and nothing else.
- **The check belongs in the submission.** A hiker adding a spring already on the map can be asked *"there's already a spring 18 m from here — is this it?"* against data the phone already holds, before they type anything. *Yes* becomes a field-note confirmation, which is the better contribution anyway; *no* is testimony from someone standing at the place, which outranks any matcher and is recorded rather than merely used.

## v2 — trails within reach of NYC

**Scoped 2026-08-18 as v2's eighth feature, by a maintainer scope call rather than a doc:
[#768](https://github.com/OurHike/OurHike/issues/768) — *v2: trails within reach of NYC — the
AT stops being the only trail on the map*.** The target is the Hudson Highlands core plus the
Catskills plus everything NYNJTC maintains, and it answers the question V2_PLAN.md had been
carrying as unanswerable from inside a session — NYNJTC's non-AT network *is* coming, as part
of something larger.

What made it real is that the data turned out to already exist in the open: NYS OPRHP runs a
public ArcGIS org (`nysparks.maps.arcgis.com`) whose hosted services are the data plane of the
State's own Parks Explorer app — 16,641 trail segments with names, blazes, surfaces and
per-use permissions, plus a live closure layer, measured 2026-08-18 and updated upstream four
days earlier. The basemap has covered all of New York state since #184's scope call; trail and
POI data was the gap, and this is that gap's program.

Like planning a hike, it starts as research rather than a build: register the org, survey the
ring (the Catskills are NYS DEC land — a source this project does not have), spike Harriman's
~40 crossing trails against the app's one-linear-trail assumptions, then write the design.
The display decisions were taken the same day, against the spike's measurements and a
canvas of drawn alternatives, and **[features/NEARBY_TRAILS.md](features/NEARBY_TRAILS.md)
now holds all of them** ([#772](https://github.com/OurHike/OurHike/issues/772)'s
deliverable): the chosen-trail centerline with the others ghosted, a view-only sheet on
tap (switching stays in the picker), safety POIs that ignore the choice, the closure
treatment reused for long-term-closed trails, the route owner's line wherever two orgs
draw the same trail, and a governed extension of the blaze palette (the Long Path's aqua
is real paint). What "the org" means on a jointly-owned route is
[#780](https://github.com/OurHike/OurHike/issues/780)'s research.

**Where the licence posture actually stands, 2026-08-25** — the sentence here used to say
"fetch-and-review only, nothing publishes to hikers", and that stopped being true on
2026-08-24. OPRHP's terms turned out to be stated all along (a truncated read had hidden
them); NYNJTC's, Mohonk Preserve's and now NYS DEC's are genuinely unstated, and those
three ship on the maintainer's authorisation recorded in `sources.json` — the same footing
ATC's own data uses. Every ask is still open, and DEC's is the live one
([#1019](https://github.com/OurHike/OurHike/issues/1019)).

**And there is no ring.** The survey drew one as a proposal with two edges left to the
maintainer; the maintainer removed the whole thing on 2026-08-25 — *"Include all of DEC,
NYNJTC & NYSP. Don't limit data from orgs based on geography"* — so what ships is every
line those organizations publish, statewide, and DEC (the Catskills, and the Adirondacks
with them) is registered rather than absent. The map went from 4,002 trail lines to 21,805
that day.

## v2 — the same account on two devices

**Scoped 2026-08-20 as v2's ninth feature, by a maintainer ask rather than a doc:
[features/ACCOUNT_SYNC.md](features/ACCOUNT_SYNC.md), tracked as
[#890](https://github.com/OurHike/OurHike/issues/890) — *v2: the same account on two devices
— a hiker's plans and photos follow them between the web and their phone*.** Plan on the
laptop, walk with the phone, and look back at the photos on a big screen — three journeys
that today share one failure, which is that everything a hiker makes in OurHike exists on
exactly the device that made it.

[SEGMENTS.md](features/SEGMENTS.md) named this in v1 and declined it deliberately — *"'plan
on my phone, check on my laptop' isn't included unless that tradeoff gets revisited"* —
because it needed accounts, which did not exist yet. They shipped in v1. This is the
revisit.

Two things make it smaller than it sounds and one makes it larger. Smaller: **half the
server side already exists and has never been called** — `GET`/`PUT /preferences/me` are
finished, validated and tested with zero client callers, and `/hikes` is complete CRUD that
`plannedHike.ts` deliberately left unwired pending *"which device wins"*. Larger: **there is
no way to delete an OurHike account**, which costs nothing today because uninstalling is
deletion, and stops being true the moment a hiker's trips and photos live on a server.

The design's one load-bearing rule is that **the device holds the truth while it is
offline**, from which the rest follows: no write waits on the network, a delete travels only
as the hiker's own delete, and two devices that disagree about a plan keep both rather than
letting the later write silently eat a fortnight of planning. Private photo sync is opt-in
and never touches the store shared photos live in — sharing grants a licence that cannot be
taken back, and syncing grants nothing.

## v2 — knowing whether any of it works

**Scoped 2026-08-09: [features/EVENTING.md](features/EVENTING.md).** Not a fifth feature — the thing the other four are measured with. v1 records nothing at all, which was the right call for a launch and is not a position that survives a second release: four v2 features are about to be built against guesses, and [FEATURE_GATING.md](features/FEATURE_GATING.md) has been recommended as the first post-launch work precisely so that stops being true.

The ask was DAU/WAU/MAU at minimum, evidence about which features work, something A/B tests can be measured against, collection client-side because an offline-first app is invisible from the server — and none of it at the hiker's expense.

Three things it settled that reach beyond it:

- **Unique-user counts need no identifier.** The reflex is that DAU/WAU/MAU require a stable id so the server can tell two phones apart. The device already knows its own history, so it sends the *answer* — three booleans on a dateless-but-dated heartbeat — and the server counts those. Exact numbers, no sketching, and nothing in the payload that differs between two hikers active on the same day.
- **The taxonomy already written down re-created the leak [#252](https://github.com/OurHike/OurHike/issues/252) closed.** FEATURE_GATING.md §6 proposed events carrying `user_id` alongside `segment_id` and a timestamp — a stable identifier next to a trail position and a time, which is the pair that was removed from the public report API three days earlier. Every question that taxonomy wanted answered is answerable without it.
- **A/B tests at club scale can find big effects and cannot find small ones** — ~260 devices per arm to detect 20%→30%, ~25,600 to detect a 5% relative lift. So staged rollout watched against guardrails is the default and experiments are for genuine disagreements, and the aggregate shape that follows leaves GrowthBook's *analysis* half unused while its flagging half stands.

It also states the thing this project has to keep saying to itself: an app committed to being used *less* cannot treat engagement as a goal, so every engagement number is read next to a task-success number or not at all.
