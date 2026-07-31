# OurHike — Map Options (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Extends [SEGMENTS.md](SEGMENTS.md) (snap-to-trail boundaries), [TRIP_PLANNING.md](TRIP_PLANNING.md), [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md) (shares its data-driven rendering pattern), [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (shares its moderation-queue pattern), and [AUTHENTICATION.md](AUTHENTICATION.md) (closures need the same admin-role identity).

**Scope note, and it's a mixed one - five sub-features, not one uniform bucket:**
- **Map UI chrome** (legend, scale, locate-me, zoom) is a **detail spec against existing v1 MVP items** ("You are here" GPS, the waypoint icon spec, the outdoor usability pass) - same framing as TRAIL_BLAZE_COLORS.md, not new scope.
- **Reroutes/closures moved into v1 MVP 2026-07-28** - resolved the open question this doc originally raised (below), the same weight of argument that moved Elevation forward: storm damage and washouts are a real physical hazard, not a convenience feature. See "Reroutes / closures" below for the revised design, now backed by real Authentication + a moderation queue rather than a pipeline-fed stopgap.
- **Background tile options, roads/sidewalks, and snap-to-segment stay Post-MVP** - real designs to build from, not an argument to reprioritize v1.

---

## 1. Background tile options

### What's actually free, checked directly rather than assumed

| Source | Live tile API? | Real cost/terms | Verdict |
|---|---|---|---|
| **USGS Topo / USGS Imagery Topo** (`basemap.nationalmap.gov/arcgis/rest/services/USGSTopo` and `.../USGSImageryTopo`, also available as WMTS) | Yes | Free, no API key, public-domain government data - the same **USGS Topo** source already trusted enough to be OurHike's offline background | **Recommended default "live" option** |
| Standard `tile.openstreetmap.org` (raw OSM tiles) | Yes, technically | [OSMF's own tile usage policy](https://operations.osmfoundation.org/policies/tiles/) explicitly warns "commercial services, or those that seek donations, should be especially aware that access may be withdrawn at any point," requires a valid HTTP User-Agent and visible attribution, and has no SLA | **Not viable as a production data source** - this is exactly why the project already chose self-hosted Protomaps extracts over a live OSM tile server for the basemap, and that reasoning holds here too |
| Esri World Imagery / other Esri basemaps | Yes | Checked directly: **restricted to ArcGIS Online/Enterprise-licensed apps**, and explicitly **prohibited for commercial use** in third-party libraries like MapLibre - the tile endpoint being reachable doesn't mean it's licensed for this | **Ruled out** - not actually free for a non-ArcGIS app despite appearances |
| Stadia Maps (OSM-styled, MapLibre-native) | Yes | Free tier exists but is **explicitly non-commercial/evaluation-only** per their terms | **Possible, not default** - same kind of open question as ATC's and opentrail.org's unconfirmed redistribution terms elsewhere in this project: worth a direct conversation with Stadia about whether a nonprofit-funding, donation-soliciting app qualifies, not an assumption either way |

**Bottom line on "a list of options that would be free":** USGS's own live tile service is the one clean, unambiguous, free-with-no-caveats option - and it's the same vendor/visual style hikers already trust from the offline corridor download. Anything OSM-styled and free-tier-hosted (Stadia, similar commercial providers) needs a real terms conversation before shipping, the same category of open question as the ATC/opentrail.org data-reuse terms already tracked in ROADMAP.md. Raw OSM and Esri are both effectively off the table for different reasons (ToS risk vs. licensing cost).

### "Ideally a live tile API for the web" - implications, researched as asked

- **Cost:** $0 for USGS; $0-tier-with-caveats for a commercial OSM-styled option; genuinely paid for Esri.
- **Legal/ToS:** government public-domain data (USGS) carries no attribution requirement beyond good practice; OSM-derived sources (raw OSM tiles, or Stadia's OSM-styled tiles) carry the "© OpenStreetMap contributors" attribution requirement already planned for the Protomaps basemap extract in ROADMAP.md - one attribution line covers both if both end up in use.
- **Reliability:** a live third-party API has no uptime guarantee OurHike controls (osm.org's policy says this outright: "no SLA or guarantee"). The existing offline PMTiles corridor archive doesn't have this problem - it's a file, not a service.
- **The real architectural tension, worth naming plainly:** FEATURES.md chose PMTiles specifically to avoid "a tile server to run or pay for," and the whole reason the MVP works offline is that hikers download the corridor once. A live tile API only works when actually online - which is exactly the condition a hiker mid-trail often doesn't have. **Resolution: this stays additive, not a replacement.** The downloaded PMTiles corridor archive remains the default and the only thing guaranteed to work offline; a live background option (USGS, and later maybe a commercial OSM style) is an **opt-in extra**, most genuinely useful in the **web trip-planning context** (at home, real connectivity, wanting to see terrain/imagery beyond the 30-mile corridor) rather than the in-the-woods mobile use case. This is consistent with FEATURES.md already treating phone and web as the same core app with different real-world usage patterns.
- **A lower-risk alternative to a genuinely live third-party API, worth considering before committing to one:** since the "beyond the 30-mile corridor" need already has a real answer (the Protomaps basemap extract, ROADMAP.md, 57MB at zoom 9 for wide context around the whole corridor, self-hosted on the same R2 bucket, no new vendor), extending *that* - more zoom levels, or a second wider extract - avoids taking on a new live-API dependency, cost, and ToS conversation at all. Worth weighing against a true live API rather than assuming "live" is the only way to get more background choice.

### What shows where there is no tile at all - the black-map problem, fixed 2026-07-31

Separate from *which* tiles to offer: until now, **anywhere the map had no tile it rendered black**. The MapLibre style had no `background` layer, so the gaps drew nothing and composited straight through to the black behind the canvas. That is not a rare edge - the corridor archive is a 30-mile strip, so it happens whenever a hiker pans off the corridor, zooms out below the archive's own minzoom, opens the app before the download finishes, or simply moves faster than tiles decode.

**Implemented, in two layers, deliberately unequal in weight:**

1. **A `background` layer at the bottom of the style, filled with `--paper-100`.** Source-free and camera-independent, so no combination of pan, zoom, missing archive or lost GPU context can produce a black screen - the guarantee holds even with the archive absent entirely. Paper rather than any other colour because it is the tone of USGS topo's own paper, so the edge of coverage reads as the map running out of ink rather than as the app dying.
2. **A faint 45° hatch on that same background layer.** Paper alone solves black but introduces a smaller lie: a blank paper field looks like a *finished map of an empty place*, when the honest claim is "no data here." Same distinction value #4 already forces for water sources and for undecoded blazes, so it gets the same treatment. **No coverage maths is needed to place it** - the background layer sits under the opaque topo raster, so the hatch shows exactly where a tile is missing and is hidden everywhere one rendered. The map describes its own coverage for free.

The split matters for failure behaviour: the paper is in `buildMapStyle` and cannot fail; the hatch needs an image registered on a loaded style, so it is applied best-effort and a failure costs texture, never the guarantee.

**Deliberately not done here, and each is a real option rather than an oversight:**
- **Tethering the camera** (`maxBounds` around the archive footprint) so the hiker cannot pan into blank space at all. Rejected as the primary answer because it fights the web trip-planning case in the section above, which legitimately wants to look beyond the corridor - and because a hard wall is a worse explanation of "no data here" than a texture that lets you see it.
- **Filling the blank with real data** - a wide-zoom Protomaps extract underneath, or live USGS tiles when there is signal. Both are already on this page as background-source options; the backdrop above is what shows when neither is present, which on a ridge with no signal is the normal case. They stack rather than compete.
- **A chrome banner naming the state** ("outside downloaded area"). Worth having, needs the archive's real footprint read out of the PMTiles header, and belongs with the legend work in §5 rather than in the style.

### Client setting

`background_source` - a client-side, per-device preference (same no-account storage model as Segments): `usgs_topo_offline` (the existing default corridor download), `usgs_topo_live`, and later, pending the terms conversation above, an OSM-styled live option. Lives alongside the already-planned "max zoom 11/12/13" setting in ROADMAP.md Phase 2 - same settings screen, same client-side storage, not a separate mechanism.

## 2. Roads & sidewalk-based walkability

**Depends on OSM road ingestion, which ROADMAP.md already lists as not yet started** - this section is a design to build against once that lands, not something buildable today.

### The real tagging scheme (checked against the OSM wiki, not assumed)

OSM tags sidewalks two ways: directly on the road way (`sidewalk=both/left/right/no/yes/separate`, or the more precise `sidewalk:left=*`/`sidewalk:right=*` pair), or as an entirely separate way (`highway=footway` + `footway=sidewalk`) referenced back from the road via `sidewalk=separate`. Both forms are real and in active use.

**The honest problem, worth naming the same way this project already named it for water sources:** ROADMAP.md already found that OSM's point-tagging near the AT specifically undershoots real coverage (178-326 water sources found vs. FarOut's 1,100+) - crowdsourced tagging is real but incomplete, especially in rural areas. There's no reason to expect sidewalk tagging near trail-to-town road walks is any more complete. **An untagged road is not the same as a confirmed-no-sidewalk road** - collapsing those into one signal would be confidently wrong exactly where value #4 says that's worse than an honest "unknown."

### Design

**1. Normalize a `walkability` attribute per road segment during ingestion**, the same normalize-once pattern TRAIL_BLAZE_COLORS.md already established for `blaze_color`:
- `confirmed_sidewalk` - a real `sidewalk=yes/both/left/right/separate` tag present.
- `no_sidewalk_low_traffic` - `sidewalk=no` (or absent) on a `highway=residential/unclassified/service/living_street` way - still probably fine to walk, just not sidewalked.
- `no_sidewalk_high_speed` - `sidewalk=no` (or absent) on a `highway=trunk/primary/secondary` way (optionally refined by a `maxspeed` tag where present) - flagged prominently, this is the genuinely dangerous case (no shoulder, higher-speed traffic).
- `unknown` - no usable tag combination - the honest fallback, not defaulted to either "safe" or "unsafe."

Sidewalk presence alone doesn't capture road-walk safety (a quiet residential street with no sidewalk is fine; a 55mph highway shoulder is not) - road classification has to factor in too, the same lesson TRIP_PLANNING.md already learned the hard way from the `Surface` field not fully capturing trail-construction difficulty on its own.

**2. Rendering reuses the same data-driven MapLibre `match`-expression pattern** TRAIL_BLAZE_COLORS.md already designed - one style rule keyed on the normalized `walkability` value, not a new rendering mechanism.

### Client setting

`show_roads` (off by default - keeps the base map at the same deliberately-minimal MVP visual density when not needed) - a simple overlay toggle, same settings surface as background source above.

## 3. Snap-to-segment

### DuckDB's real spatial-snap capability, checked against the actual extension (not assumed)

DuckDB's spatial extension does **not** have one function called `ST_Snap`, but it composes cleanly from two real, currently-documented functions:
- **`ST_LineLocatePoint(line, point)`** - returns where along the line (as a 0-1 fraction of total length) the closest point to a given tap actually falls.
- **`ST_LineInterpolatePoint(line, fraction)`** - the inverse: turns that fraction back into a real coordinate, sitting exactly on the line.

Together: `ST_LineInterpolatePoint(centerline, ST_LineLocatePoint(centerline, tapped_point))` snaps any tapped point onto the nearest spot on real trail geometry - exactly the "snap to grid" behavior asked for, where "grid" is the actual trail line rather than a literal map grid.

**One honest caveat worth flagging before this gets built, not glossed over:** DuckDB's own docs page currently lists both functions as shipped, but there's a still-open GitHub issue (`duckdb/duckdb-spatial#711`, filed 2025-11-14, open as of this writing) titled "Feature request: ST_LineLocatePoint." Documented and open aren't necessarily contradictory (the issue may cover a narrower follow-on ask), but this is exactly the kind of "verify against the real installed version, don't trust this doc alone" situation AUTHENTICATION.md already flagged for Supabase pricing - confirm directly against the actual bundled extension version at implementation time.

### Design

Extends, rather than replaces, [SEGMENTS.md](SEGMENTS.md)'s existing boundary design: a Segment boundary today is "one of these [mile-markers/POIs] - or, if nothing fits, a point the user drops on the map." **This feature upgrades the dropped-pin case**: instead of storing the raw, possibly slightly-off tap coordinate, snap it onto the nearest point on real trail geometry before storing it - so every Segment boundary ends up precisely on-trail, tap precision no longer matters, and "completed" keeps meaning something concrete (the same trustworthiness reasoning SEGMENTS.md already gives for preferring real geographic references).

**"Prefer the current through-hike route" - a real disambiguation rule, not a vague preference:** near a junction (e.g. a shelter spur meeting the main trail), both `centerline` and `side_trails` may be within snapping distance of one tap. Rather than always picking whichever line is geometrically closest, **use the Hike's existing `type` field** (already in SEGMENTS.md's data model: thru | section | day) to break the tie - a thru/section-hike snaps onto `centerline` by default, since through-hikers are describing progress along the main trail; a day-hike snaps onto whichever line is actually closest, since a day-hike legitimately might be planning a spur to a shelter or viewpoint. No new field needed - this reuses a decision Segments already has to make anyway.

## 4. Reroutes / closures - moved into v1 MVP 2026-07-28

### Checked against the real ATC data: this is genuinely new, not a decode job

Unlike Trail Blaze Colors (where a real `Blaze` coded domain already existed in `side_trails` and just needed decoding), **none of the 12 already-registered ATC layers** (`sources.json`: centerline, side_trails, campsites, shelters, parking, viewpoints, communities, half-mile points, bridges, privies, trail club sections, treadway) **has anything resembling a closure or status field.** This has to be modeled from scratch, not extracted from data that already exists.

### Design

**Data model:**

```
Closure
  id
  trail reference + location (a stretch along the centerline - start/end mile-marker
                                or point references, same anchoring pattern as
                                Segments' boundaries and Volunteering's WorkProject
                                location, not a new geometry scheme)
  reason (storm damage, flooding, maintenance, relocation, other - free text
          alongside a type, matching Report a Problem's type + note shape)
  status: open | closed | reroute-available
  reported_by, reported_at
  verified_by (club admin/maintainer), verified_at
```

**Who can mark a closure - reuses the identity/role work already designed, doesn't invent a new one.** This is the same permission tier as Volunteering's club-admin access and Report a Problem's maintainer-verification workflow, both of which already point at [AUTHENTICATION.md](AUTHENTICATION.md) as the identity layer to build on. **Update 2026-07-28:** since Authentication and Report a Problem's real moderation queue are both MVP now, closures go through that real workflow directly from day one - the "hand-maintained file, fed through the pipeline" stopgap originally proposed here (mirroring Volunteering's own admin gap) is no longer needed, since the real thing exists at the same time.

**Display:** a closure covers a *stretch* of trail, not a point - so unlike most map features here, this renders as a distinct line treatment directly on the trail geometry itself (e.g. a dashed red overlay along the closed stretch), tappable for the reason/status/dates, rather than a pin. **This is deliberately not a routing/reroute-computation engine** - showing "this stretch is closed" is what's designed here; actually computing and suggesting a road-walk detour around it is a real, much bigger feature (needs an actual road-routing graph), flagged as a possible future extension and not designed here, the same way TRIP_PLANNING.md flagged structural bulk-editing without designing it.

**The real safety tension, worth naming plainly rather than glossing over:** closures are exactly the kind of information that goes stale in a downloaded-once offline package - a hiker relying on a week-old download might walk into a closure marked *after* they downloaded. Not solved here, but worth flagging two honest partial answers: show a visible "data last synced [date]" indicator rather than hiding the staleness (same honesty principle as the existing "reported 3 days ago vs. confirmed today" idea in FEATURES.md's water-reliability section), and consider a lightweight "check for critical safety updates" ping when brief signal is available even in otherwise-offline use - a real design problem, flagged for later rather than solved here.

**Resolved 2026-07-28:** this raised, and now answers, the exact "does this deserve the same MVP-promotion conversation Elevation got" question - it does, and closures are v1 MVP as of this revision.

### Client setting

`show_closures` - unlike the other overlays in this doc, **this probably shouldn't be a hideable layer at all.** Letting a hiker turn off known-closure warnings conflicts directly with value #4 (trustworthy above all) - suppressing safety information isn't the same kind of preference as picking a background tile style. Flagged here as a recommendation, not force-decided.

## 5. Map UI chrome: legend, scale, locate-me, zoom

### What MapLibre already provides for free (checked against the real API, not assumed)

- **`NavigationControl`** - zoom in/out buttons plus a compass, built in, one line to add (`map.addControl(new maplibregl.NavigationControl())`).
- **`GeolocateControl`** - wraps the browser Geolocation API already planned for "You are here" in ROADMAP.md Phase 2; supports a `trackUserLocation` mode for continuous tracking vs. a single locate-me tap. This is the real control to hang the existing GPS MVP item on, not a separate build.
- **`ScaleControl`** - a real scale bar, configurable units, also one line to add.

**No built-in legend control exists** - this one has to be hand-built, same "small custom piece, not a framework" precedent as `lib/tiling.py`/`lib/arcgis.py`. It should **read from the schemes already normalized elsewhere** (the waypoint icon spec's ~8 POI categories, Trail Blaze Colors' `blaze_color` values, and this doc's own `walkability` tiers) rather than inventing a separate legend taxonomy - the legend is a view onto categories that already exist, not a new one.

### Web vs. mobile - a real, concrete difference, not just "responsive"

- **Mobile (the Capacitor-wrapped shell):** touch-first, larger touch targets, controls anchored within thumb reach (bottom-anchored, not top-corner), pinch-to-zoom as the primary zoom interaction with the buttons as a fallback/accessibility path. Directly connects to the outdoor-usability pass ROADMAP.md already plans (glare, gloved-hand use) - a legend or scale control that's fussy to tap with gloves on fails the same test the map itself has to pass.
- **Web:** mouse/keyboard/scroll-wheel zoom as primary, hover states become available, and the extra screen real estate means the legend can be a persistent expandable panel rather than a modal that has to be dismissed to see the map underneath it.

This section is a detail spec, not new scope - it's fleshing out controls for MVP items (GPS positioning, the waypoint icon spec, the outdoor usability pass) that are already committed, the same relationship TRAIL_BLAZE_COLORS.md has to the MVP trail-line item.

**Extended by [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md):** the compass in `NavigationControl` above gets a real reset-to-north behavior once auto-rotate exists, and the legend's job grows to also reflect that doc's `layer_detail_level` and `waypoint_types_shown` settings - same legend, same "read from schemes that already exist" principle, not a second one.

## Data model sketch (settings, client-side)

**Update 2026-07-28: consolidated into [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md)'s `UserPreferences`**, alongside UX Customization's, Onboarding's, and Hiker Safety's settings, rather than five separate small models. This doc still owns *why* each of these settings exists (the reasoning above doesn't move) - only the data model shape now lives in one canonical place: `background_source`, `max_background_zoom`, `show_roads` (all designed here). `show_closures` deliberately isn't in that model at all - it's always-on, not user-hideable (see "Reroutes / closures" above), a fixed display rule rather than a preference.

## Open questions (for you, not decided here)

- **Stadia Maps' (or a similar provider's) actual commercial-use terms for a nonprofit-funding, donation-soliciting app** - a real conversation to have directly with them, the same category of open question as ATC's and opentrail.org's unconfirmed redistribution terms.
- **Whether extending the existing Protomaps self-hosted extract (more zooms, a wider region) is a better answer than any live third-party API** for "see more background than the downloaded corridor" - raised above, worth deciding once there's a real map in front of you rather than from this doc alone.
- **Exact `no_sidewalk_high_speed` threshold** (which `highway=*` values, whether to also read `maxspeed` where tagged) - a real tuning decision once there's real OSM road data pulled for the corridor, not a question this doc can answer without it.
- **Closure geometry precision** - whether a closure needs to reference exact start/end points along the centerline (precise, more data-entry effort for a volunteer) or a looser "this general stretch" description (faster to report, less precise) - worth deciding based on what club volunteers will actually have time to enter in the field.

## Related: reused elsewhere

[HIKER_SAFETY.md](HIKER_SAFETY.md)'s wrong-way/off-trail alert runs this doc's snap-to-segment distance math continuously against live GPS instead of once against a single tap - same `ST_LineLocatePoint`-based computation, not a second implementation.

[DATA_NUDGES.md](DATA_NUDGES.md) reuses this doc's normalize-then-`match` rendering pattern a third time (after blaze colors and walkability) to highlight POIs whose data has gone stale, and feeds the same legend this doc already designs.

[ONBOARDING.md](ONBOARDING.md) points at this doc's waypoint icon spec / legend for its one piece of "helpful info," and treats the background zoom/size choice above as the first real onboarding moment rather than a separate settings-screen-only decision.
