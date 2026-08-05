# OurHike — Map Options (Feature Design Draft v1)

Companion to [FEATURES.md](../FEATURES.md), [TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md), and [OurHikeValues.md](../OurHikeValues.md). Extends [SEGMENTS.md](SEGMENTS.md) (snap-to-trail boundaries), [TRIP_PLANNING.md](TRIP_PLANNING.md), [TRAIL_BLAZE_COLORS.md](TRAIL_BLAZE_COLORS.md) (shares its data-driven rendering pattern), [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) (shares its moderation-queue pattern), and [AUTHENTICATION.md](AUTHENTICATION.md) (closures need the same admin-role identity).

**Scope note, and it's a mixed one - five sub-features, not one uniform bucket:**
- **Map UI chrome** (legend, scale, locate-me, zoom) is a **detail spec against existing v1 MVP items** ("You are here" GPS, the waypoint icon spec, the outdoor usability pass) - same framing as TRAIL_BLAZE_COLORS.md, not new scope.
- **Reroutes/closures moved into v1 MVP 2026-07-28** - resolved the open question this doc originally raised (below), the same weight of argument that moved Elevation forward: storm damage and washouts are a real physical hazard, not a convenience feature. See "Reroutes / closures" below for the revised design, now backed by real Authentication + a moderation queue rather than a pipeline-fed stopgap.
- **Background tile options, roads/sidewalks, and snap-to-segment stay Post-MVP** - real designs to build from, not an argument to reprioritize v1.

---

## 1. Background tile options

### Built 2026-08-03 - the live topographic sheet, and why the raster answer below was the wrong one

**What prompted this: "the background map is really bad."** That is a fair reading of what shipped, and the cause is structural rather than a bug in `spike_raster_mosaic.py`. The corridor archive is a *picture of a map*: US Topo quads are pre-rendered at 1:24,000 in per-quad UTM zones with their labels baked into the pixels, so mosaicking them means reprojecting and resampling ink drawn for one scale, and reading them at any other zoom means looking at that ink stretched or crushed. Seams between quads of different vintages, type that cannot reflow, contours that cannot be recoloured, and nothing at all outside the 30-mile strip are not defects in the pipeline - **they are what a raster mosaic is.** No amount of pipeline work fixes them, which is why the answer is a different kind of background rather than a better-tuned version of this one.

**That also invalidates this section's original recommendation.** The table below picked USGS's live tile service as the default live option, on the grounds that it is unambiguously free and already the trusted visual style. Both facts still hold - but a live *raster* service inherits every one of the problems above (it is the same pre-rendered ink, just fetched instead of downloaded) and, critically, **cannot be stylized at all.** "Free" was the only question that table asked. It should have asked "free *and* vector."

**What shipped instead - three free, no-key sources composed into one sheet we style ourselves:**

| Layer | Source | Terms, checked | Why this one |
|---|---|---|---|
| Vector base (water, woodland, protected land, roads, tracks, OSM paths, place and summit labels) | **OpenFreeMap** public instance, `https://tiles.openfreemap.org/planet`, unmodified OpenMapTiles schema | No API key, no registration, **no request cap**, explicitly free for commercial use with attribution; MIT-licensed project, donation-funded | The only OSM vector host that is free at production volume without a terms conversation - which is exactly what Stadia (below) would have needed |
| Shaded relief + **contour lines** | **AWS Terrain Tiles** (`elevation-tiles-prod`), AWS Open Data registry, terrarium encoding | Open Data, no key, plain S3; attribution required per tilezen/joerd | Over the A.T. it is derived from **USGS 3DEP** - the same survey the elevation profile already credits. Contours are generated in the client from these tiles by `maplibre-contour`, so the interval follows the zoom and the reader's units instead of being baked at one scale |
| Downloaded corridor | The existing PMTiles archive, unchanged | - | Still in the style, underneath. See the stacking note below |

**Contours are the reason this counts as "quality over prettiness."** A hiking basemap without them is not a topographic map, and losing them is the one way this change could have been a downgrade. Generating them client-side from the same DEM the hillshade already fetches costs no extra storage, no extra download, and no pipeline run - and it means the interval can be 40ft/200ft where a USGS 7.5-minute quad uses it and coarsen as you zoom out, which a pre-rendered contour layer can never do.

**The stacking decision, which is what makes this safe to default to.** The live layers are drawn **over** the corridor archive rather than in place of it, so there is no online/offline branch anywhere in the client:

- **Signal, nothing downloaded** (every first run): a real topo map, worldwide. Previously: blank hatched paper.
- **Signal, downloaded**: the vector sheet covers the corridor and keeps going past its edge.
- **No signal, downloaded**: the live layers draw nothing, the archive shows through exactly as before, and the flat paper backdrop still marks where the download does not reach (the 45° hatch that used to mark this too was removed 2026-08-04 - see below).
- **No signal, nothing downloaded**: unchanged.

Every state is at least as good as it was, and none of them has to be detected. That is why `background_source` now **defaults to the live sheet** rather than making it opt-in as this doc originally proposed - the offline premise costs nothing to keep, so the "additive, not a replacement" resolution below is honoured by the layer order rather than by a setting someone has to find.

**Two caveats recorded honestly rather than buried:**

- **OpenFreeMap is donation-funded and carries no SLA**, the same category of risk this doc already named for any live API. The mitigation is structural: it is one constant (`OPENFREEMAP_TILEJSON` in `client/src/map/liveTopo.ts`), the schema is standard OpenMapTiles, and the "self-host an extract on the R2 bucket we already publish to" answer below remains available with no cartography changes. **This is now the answer to that open question** - not "extend the Protomaps extract *instead* of a live API", but "ship the live API, keep the self-hosted extract as the drop-in replacement."
- **The tile endpoint could not be reached from the build environment** (its network policy blocks the host), so it was confirmed from two independently published npm packages that embed it, plus OpenFreeMap's own documented quick-start. The AWS DEM endpoint *was* reached directly and returns real tiles. Worth one look at a real map before trusting the vector half completely.

  Observed again 2026-08-05 from a different agent sandbox, and recorded because it is easy to misread as evidence: `tiles.openfreemap.org` returns a **403 at the proxy's CONNECT step** while `s3.amazonaws.com/elevation-tiles-prod` returns 200 and real bytes through *the same* proxy. That asymmetry says the sandbox blocks one host and not the other. **Nothing follows from it about OpenFreeMap's production reachability**, and it is not the explanation for any hiker's blank map. The "one look at a real map" above is still outstanding.

### What's actually free, checked directly rather than assumed (original 2026-07 survey, superseded above)

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

### What shows where there is no tile - the black-map problem, 2026-07-31

Separate from *which* tiles to offer: **"I just see a black background."** Worth recording because the one symptom had two independent causes, and fixing either alone leaves black on the screen.

**Cause 1, in the pipeline (fixed in "Make ground outside the corridor transparent, not black").** The corridor is a ribbon and every tile is a square, so `mosaic_one_cell()`'s `nodata=0` filled most of most tiles - measured at 99% of a real z6 tile - and written as RGB those pixels *are* the colour black, not an absence. Tiles are RGBA now, so that ground is see-through. See that commit for the full reasoning and its honest limitation.

**Cause 2, in the style: transparent is not a colour either.** Once nodata became see-through, whatever is behind the raster is what shows - and a MapLibre style with no `background` layer draws nothing there, which composites straight down to the black behind the canvas. Same outcome, different mechanism. The paper background layer landed with the pipeline fix; the rest below builds on it.

**Where the style now stands, in two layers, deliberately unequal in weight:**

1. **A `background` layer at the bottom of the style, `--paper-100`.** Source-free and camera-independent, so the guarantee does not depend on the pipeline fix holding, on the archive existing, or on the camera being anywhere in particular: no combination of pan, zoom, missing download or lost GPU context can put black on the screen. Paper because it is USGS topo's own paper tone, so uncovered ground belongs to the same map as the covered parts. `.map-view` carries the same colour in CSS for the one window the style cannot cover - before WebGL paints a first frame, and if the context is lost or never obtained at all.
2. **A faint 45° hatch on that same background layer.** Paper alone solves black but introduces a smaller lie: a blank paper field looks like a *finished map of an empty place*, when the honest claim is "no data here." Same distinction value #4 already forces for water sources and for undecoded blazes, so it gets the same treatment. **No coverage maths is needed to place it** - the background sits under the raster, so the hatch shows exactly where there is no topo ink and is hidden everywhere there is. That covers both shapes of "no ink" without telling them apart: no tile at all, and the transparent nodata ground *inside* a tile. The map describes its own coverage for free.

The split matters for failure behaviour: the paper is in `buildMapStyle` and cannot fail; the hatch needs an image registered on a loaded style, so it is applied best-effort and a failure costs texture, never the guarantee.

**Deliberately not done here, and each is a real option rather than an oversight:**
- **Tethering the camera** (`maxBounds` around the archive footprint) so the hiker cannot pan into blank space at all. Rejected as the primary answer because it fights the web trip-planning case in the section above, which legitimately wants to look beyond the corridor - and because a hard wall is a worse explanation of "no data here" than a texture that lets you see it.
- **Filling the blank with real data** - a wide-zoom Protomaps extract underneath, or live USGS tiles when there is signal. Both are already on this page as background-source options; the backdrop above is what shows when neither is present, which on a ridge with no signal is the normal case. They stack rather than compete.

### Removed 2026-08-04 - the hatch read as distracting diagonal stripes, not as "no data here"

The 45° hatch above (`client/src/map/backdrop.ts`, now deleted) was reported as visually distracting on screen - a field of diagonal strips, not a subtle "unmapped" cue. The texture-vs-warning-stripe contrast test it shipped with was tuned against a still swatch, not against a hiker's eye scanning a moving map, and in practice it read as noise rather than information.

**What ships now:** layer 1 alone - the flat `--paper-100` `background` layer in `buildMapStyle` (`style.ts`'s `BACKDROP_LAYER_ID`). It still cannot fail, still needs no coverage maths, and still keeps the one guarantee that actually matters: no combination of pan, zoom, missing download, or lost GPU context can put black on the screen. What it gives up is the second-order distinction between "no data here" and "a finished map of an empty place" - a real cost, but a smaller one than it was when this was written, because the live topographic sheet (built 2026-08-03, above) now covers the flat-paper case with a real map everywhere there is signal. The plain-paper fallback is left for the case that remains: no signal *and* off the downloaded corridor, which on a ridge is exactly when a hiker has bigger problems than a texture.
- **A chrome banner naming the state** ("outside downloaded area"). Worth having, needs the archive's real footprint read out of the PMTiles header, and belongs with the legend work in §5 rather than in the style. **Half-built 2026-08-05:** the states the client can already tell without reading the archive - the live sheet never loaded, Data Saver is overriding the background - are now flags on `StatusStrip` (see below). The footprint half still needs the PMTiles header and still belongs with §5.

### Fixed 2026-08-04 - the opening view had no background on it at all

**What was reported: "the map no longer displays a background map on initial load."** That claim above - *"signal, nothing downloaded (every first run): a real topo map, worldwide"* - was not true of the view a first run actually opens on, and the reason is a gap between two decisions neither of which is wrong on its own.

The app opens on the **whole trail**: `App.tsx` frames `CORRIDOR_BOUNDS`, Georgia to Maine, which lands near **z4**. Every layer in the sheet that describes terrain is keyed to **hiking** zooms - the contours interpolate to zero opacity below z9, their labels start at 12, summits at 10, tracks at 11, paths and minor roads at 12 - and OpenMapTiles itself carries no woodland below roughly z7, so the landcover fills have nothing to draw either. What is left at z4 is water, boundaries, major roads, city labels, and relief shading. Only the last of those covers the corridor, and it was drawn at `hillshade-exaggeration: 0.35` - a weight chosen for z13, where the contours carry the terrain and the shading only gives it body. Stretched across a thousand kilometres of DEM, 0.35 is invisible. The opening screen was blank paper with a scale bar on it.

The hatch removal above is why this reads as a regression rather than as something that was always so: the same empty view previously carried a visible texture, so "nothing here yet" at least looked deliberate.

**What ships:** the relief shading is a zoom ramp instead of one number (`HILLSHADE_EXAGGERATION_EXPRESSION` in `client/src/map/liveTopo.ts`) - full strength at and below z9, easing back to the same 0.35 by z12. Those two zooms are the contour ramps' own, not new ones: the shading is turned up over exactly the window where nothing else is drawing terrain, and hands back as the contours fade in. At hiking zooms the map is pixel-for-pixel what it was.

Three properties worth recording, because they are what makes this the right size of fix:

- **It costs no bytes.** The DEM tiles behind the hillshade are already fetched at every zoom - this only decides how much of what they contain reaches the screen. Data Saver's override is untouched and still subtracts the whole live sheet.
- **It does not move the camera.** Opening on the whole trail is a deliberate choice and the fix does not quietly narrow it to a zoom where the sheet happens to look better.
- **It changes nothing offline.** With no signal there is still no DEM, and the opening view is still the paper backdrop - the honest state, and the one the section above already accepts.

### Fixed 2026-08-05 - the blank screen said nothing about why it was blank

**What was reported: "if a user has not downloaded a map it should default to the live web version - all I see is an empty background."** The default was already right (`hiking_topo_live`, above), so the report is not about the preference. It is about the four states in the stacking table having no fifth row for *the live sheet was asked for and did not arrive*.

The 2026-08-04 fix above settled whether there is ink at the opening camera. It did not settle what happens when the one layer carrying that ink never loads - and at z4 the corridor is covered by relief shading alone, so a single unreachable host is the difference between a topographic map and flat cream paper. Three things produce that screen, and until now the client said nothing about any of them:

- **The sources are unreachable.** A captive portal, a filtered or corporate network, or an outage at a host with no SLA. MapLibre knows and says so - `vector_tile_source.ts` marks a failed source loaded on purpose so the style ignores it rather than stalling, and fires an error - but nothing in this client listened, so the failure reached the console and never the hiker.
- **The background resolved to `usgs_topo_offline` with nothing downloaded.** Either the hiker picked "downloaded only" or Data Saver forced it. Both produce a style whose archive source resolves to nothing and whose live layers were never added: flat paper, plus the trail line, permanently. **This is what the reporter was actually looking at** - their screenshot's attribution corner read the bare `USGS US Topo · © OpenStreetMap contributors` rather than the live sheet's three-part credit, which `attributionFor()` only returns for the offline background.
- **The style dropped the sheet itself** - the latent defect below.

**The first of those is now fixed at the root rather than merely announced.** `effectiveBackground()` takes a third input - whether a finished archive exists - and the offline background is honoured only once there is something offline to honour it with. Until then the live sheet is drawn, whichever way the preference and Data Saver point. Once the download lands, both take effect exactly as before and the rule never fires again. See the amendment under §1's Data Saver notes for what that costs and why it is the better failure.

**What ships is a statement, not a branch.** `client/src/map/liveSourceHealth.ts` watches the two background sources and reports one as unreachable only when it has errored *and* nothing from it has ever drawn; `StatusStrip` gains two flags, "No live map" and the Data Saver override. The no-online/offline-branch rule at the top of this section is untouched and deliberately so: nothing observed at runtime reaches `buildMapStyle`, which stays a pure function of the preference, Data Saver, and whether a DEM could be built. No source is swapped, no style rebuilt, no request retried. This is §5's "chrome banner naming the state" placed where that bullet already said it belonged - in the chrome - and it is the shape `lib/useOnline.ts` already established: connectivity drives what the strip **says**, never what the machinery does.

**No fallback tile provider was added,** and that is a decision rather than an omission. Provider-A-fails-so-try-provider-B is exactly the branch this section forbids, it reopens a terms question closed below (raw OSM is not viable as a production source, Esri is prohibited for commercial use with MapLibre, Stadia's free tier is non-commercial), and it would make the app lie better rather than worse: a hiker would not know which map they were reading. The documented mitigation stands - repoint one constant at a self-hosted extract.

**A separate, latent defect, fixed here because it has the same symptom.** `style.ts` folded "the hiker asked for the live sheet" and "`registerTerrain()` returned URLs" into one boolean, so a missing elevation model dropped **all** of the sheet - the landcover, parks, water, the path and road network, summits, every place name and the glyphs endpoint - when exactly one of its twenty-one layers reads the DEM and three read the contours. That contradicted `terrain.ts` ("every failure path here is a missing layer, never a broken map") and `MapView.tsx` ("a failure here costs terrain and nothing else") in their own words. Elevation is now one input to the sheet rather than the sheet itself.

**And the trail itself now loads without the archive.** Reported in the same breath once the background came back: *"there is a centerline, but only after the data is downloaded — I think the trail vectors should always load."* They should. `trails.geojson`, the POIs, the spurs and the elevation profile are a few megabytes against the corridor archive's 314 MB — the download flow already treats them that way, fetching them first as the canary that decides whether the archive is worth starting — but nothing fetched them until someone tapped **Download the map**. Until then the app opened on a background with no trail on it, nothing to search, no POIs and no elevation ribbon, which is most of the app waiting on a decision about something else entirely.

`App.tsx` now fetches them on first run when a data source is configured and the phone is online, quietly: a failure leaves exactly the empty map it would have had, and the download window still reports errors for the download a hiker actually asks for. Reading what is already stored stays unconditional and independent of that fetch — an unconfigured build and a phone with no signal both still have last time's download, and gating the *read* on connectivity would leave a hiker on a ridge looking at a map with no trail. The corridor archive is untouched and stays behind its button; it is hundreds of megabytes of someone's data allowance and that remains their call.

Worth being plain about: **the terrain decoupling on its own is the fifth row the table never had, not a fix that puts a map on the reporter's screen.** In the state the decoupling repairs, terrain is by definition still missing, so what draws at the opening camera is water, boundaries, major roads and city labels - which this document already calls blank paper with a scale bar on it. The durable answers to *that* are [#187](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/187), [#188](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/188) and [#189](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/189) - terrain, glyphs and vector tiles from the download - after which the opening view stops depending on a network host at all.

### Client setting

`background_source` - a client-side, per-device preference (same no-account storage model as Segments). Lives alongside the already-planned "max zoom 11/12/13" setting in ROADMAP.md Phase 2 - same settings screen, same client-side storage, not a separate mechanism.

**As built 2026-08-03, this is two values rather than the three sketched here, and both are implemented:**

- `hiking_topo_live` **(default)** - the live topographic sheet, drawn over the archive. See the build note at the top of this section for why defaulting to it costs the offline premise nothing.
- `usgs_topo_offline` - the downloaded corridor alone, and **no background request at all**. The honest choice for someone metering data or deliberately dark, which is a real reason to keep it and the only reason it is still a setting.

**Data Saver overrides the choice, and says so (2026-08-03, [#122](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/122)).** Making the live sheet the default meant every hiker with signal started pulling tiles they had not asked for - roughly 2 MB for a fresh view, measured over the AT (DEM tiles run 110-130 KB each at z11-13). That is small against the 314 MB corridor download and it costs the project nothing, since OpenFreeMap is uncapped and the AWS DEM is Open Data with sponsored egress. It is a **consent** problem rather than a cost one: the archive is a size on a button someone taps, and this was a default they inherited.

So `navigator.connection.saveData` now decides the background that is actually drawn (`client/src/lib/dataSaver.ts`). Data Saver is a preference the hiker set deliberately at the OS level, which is a better signal about their plan than our default could be, so it **wins** rather than merely nudging.

Two things make that defensible rather than presumptuous, and neither ships without the other:

- **It only ever subtracts.** The override can turn the live sheet off; nothing can turn background requests on for someone who chose the download. **Amended 2026-08-05:** it subtracts only once there is a download to subtract *to*. With no archive on the phone, `usgs_topo_offline` draws no corridor and fetches nothing, so subtracting the live sheet leaves the paper backdrop and nothing else - which is not a cheaper map, it is no map, and nobody chose it. Both overrides now wait for a finished archive. Where the rule still protects something - a phone with the corridor on it - it is unchanged and nothing can turn requests back on.
- **The app says it plainly**, and only when the two actually disagree. Overriding a preference is fine; overriding one while the screen still claims otherwise is the exact quiet mismatch value #4 exists to prevent. Since 2026-08-05 it says *which* override, because the two are opposite in kind: Data Saver withholds the live sheet, an undownloaded archive supplies it. Telling a hiker their data was being saved while the app fetched tiles would be the same mismatch one word further along.

  **Where the choice lives, amended 2026-08-05.** It was a `select` in Settings, and that was the wrong home: the background is the largest thing on the screen, and the moment someone wants to change it is the moment the map is not showing what they expected - the worst moment to send them through a settings screen. It is now a segmented radio pair at the top of the **legend** (`client/src/chrome/BackgroundPicker.tsx`), one tap from the map, in the panel that already answers "what am I looking at". Settings renders the same component rather than its own control, so the two cannot drift apart. The picker always shows the **choice**, never the drawn outcome - one that snapped to "downloaded" because Data Saver was on could never be used to change anything - and the override note sits directly beneath it, where the choice is made.

  **And choosing "Downloaded" with an empty phone now opens the download (2026-08-05).** The Downloads tab was removed the same day (WIREFRAMES.md §4), on the grounds that one whole-corridor package does not need a permanent target in the thumb zone — so the picker had to stop being a control that only *describes* a download nobody can reach. Picking the offline background with no archive on the phone opens the download window, rather than writing the preference and leaving the hiker with the note above explaining there is no map to honour it with. **The preference is still written either way**, which matters here: the rule above says the offline background waits for an archive to exist, so a choice made in advance costs nothing and takes effect the moment one lands. An override that also refused to record the choice would be a second, quieter override on top of the one this section is about.

  The link for every *other* moment — change the detail level, delete, watch a transfer — is deliberately **not** on this control. It was, briefly, and that put a once-a-season errand directly under the first thing in the legend. It is at the foot of the panel now, and at the foot of Settings, from one component (`client/src/chrome/DownloadsLink.tsx`). The rule above is what makes that affordable: nobody has to find the link to get a map onto a phone that has none.

**Known limits, both real:**

- **iOS gets nothing from this.** Safari implements no part of the Network Information API, so `saveData` is always undefined there and the honest description is that this improves Android and does nothing for iPhone. `@capacitor/network`'s `connectionType` would close the gap, blocked on [#101](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/101).
- **Someone who leaves Data Saver on permanently cannot get the live sheet** without turning it off, because nothing stored distinguishes "chose the live sheet" from "never touched the default". Giving those two different answers needs a real "this was chosen" flag on the synced preferences - there is precedent in `download_choice_made` - and that is a contract change worth deciding rather than assuming. Flagged in #122, not decided here.

  **The map screen now says so too (2026-08-05).** Settings being the only place that named the override was defensible while the override merely changed how the map looked; it is not when the hiker has downloaded nothing, because then the override subtracts the entire background and the screen someone is staring at is blank paper. The flag states it where the blankness is. What it does **not** do is decide the question above - Data Saver still wins, and someone who wants the live sheet still has to turn it off.

The two names originally sketched here, `usgs_topo_live` and `osm_styled_live`, were **removed rather than kept as placeholders.** Neither was ever built, and a value nothing can render is a settings row nobody can honour and a preference the backend would happily store and sync back as a map with no background on it. A phone that saved one before this change drops it on read and falls back to the default (`client/src/lib/preferences.ts`), which is the mirror image of the merge-over-defaults rule that file already had for *missing* keys: a key holding a value this build no longer knows is not fixed by merging, because the key is present.

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

- ~~**Stadia Maps' (or a similar provider's) actual commercial-use terms for a nonprofit-funding, donation-soliciting app.**~~ **Closed 2026-08-03 - the conversation is not needed.** OpenFreeMap is free for commercial use with attribution and no cap, stated up front, so there is no terms question to open with anyone. Worth reopening only if OpenFreeMap becomes unavailable *and* self-hosting is somehow ruled out.
- ~~**Whether extending the existing Protomaps self-hosted extract is a better answer than any live third-party API.**~~ **Closed 2026-08-03, and the answer was "not either/or."** The live API ships now because it needs no pipeline work and covers the world; the self-hosted extract stays the drop-in replacement behind one constant. Deciding between them up front would have delayed a fix for a background that was already bad.
- **Whether the vector sheet actually reads well on the trail** - the one thing no test here can answer. The style validates and every layer is asserted, but "does this look like a map you would navigate by, at arm's length, in glare, with the trail line still the most legible thing on it" needs a real screen. The palette, the contour intervals and the label density are the knobs, all in `client/src/map/liveTopo.ts`.
- **Exact `no_sidewalk_high_speed` threshold** (which `highway=*` values, whether to also read `maxspeed` where tagged) - a real tuning decision once there's real OSM road data pulled for the corridor, not a question this doc can answer without it.
- **Closure geometry precision** - whether a closure needs to reference exact start/end points along the centerline (precise, more data-entry effort for a volunteer) or a looser "this general stretch" description (faster to report, less precise) - worth deciding based on what club volunteers will actually have time to enter in the field.

## Related: reused elsewhere

[HIKER_SAFETY.md](HIKER_SAFETY.md)'s wrong-way/off-trail alert runs this doc's snap-to-segment distance math continuously against live GPS instead of once against a single tap - same `ST_LineLocatePoint`-based computation, not a second implementation.

[DATA_NUDGES.md](DATA_NUDGES.md) reuses this doc's normalize-then-`match` rendering pattern a third time (after blaze colors and walkability) to highlight POIs whose data has gone stale, and feeds the same legend this doc already designs.

[ONBOARDING.md](ONBOARDING.md) points at this doc's waypoint icon spec / legend for its one piece of "helpful info," and treats the background zoom/size choice above as the first real onboarding moment rather than a separate settings-screen-only decision.
