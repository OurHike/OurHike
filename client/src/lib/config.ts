// Where published data is fetched from.
//
// The base URL is a build-time variable rather than a constant because the
// bucket it points at is not knowable from the source tree - it is whatever
// R2 (or a local static server, during a field test) is serving
// pipeline/publish.py's output. Set VITE_DATA_BASE_URL at build time; see
// client/README.md.
//
// Keys must match publish.py's artifact names exactly - a mismatch here is a
// 404 on a mountain, which is why the background tier names are spelled the
// same way in both places.
//
// The keys are what publish.py writes; WHERE they are fetched from is
// dataRelease.ts's (DATA_RELEASES.md section 4). Since #1333 a release
// artifact resolves under `releases/<DATA_RELEASE>/`, immutable and pinned by
// a committed constant, while `conditions/`, `photos/` and `latest.json` stay
// at the root - safety data has to be rewritable, photos are already
// content-addressed, and the pointer cannot version itself. `dataUrl` below
// applies that split; nothing calling it needs to know.
//
// EVERY `*_KEY` BELOW CARRIES AN `@release` LINE saying `required` or
// `optional`, and `expected_client_keys` (pipeline/verify_release.py) RAISES
// on one that does not. That is the point of putting the declaration here
// rather than in the pipeline: this file is where an artifact is added, so
// this is the only home where adding one cannot skip the question.
//
// It answers "must a release built from THIS CHECKOUT carry it", which is not
// the same question as "does the app survive its absence" - the app survives
// every one of them, deliberately, because a hiker on an older release must
// not be shown an error (lib/trailData.ts's fetchOptionalArtifact). `optional`
// here means publish.py can decline to write it for a reason outside the code:
// a steward's `reaches_hikers` in sources.json, or a sheet whose cut has not
// run. Name that reason on the line.

import type { DetailLevel } from './downloadDetail'
import { RELEASE_MANIFEST_PATH, releasePath } from './dataRelease'

const RAW_BASE: string = import.meta.env.VITE_DATA_BASE_URL ?? ''

export const DATA_BASE_URL = RAW_BASE.replace(/\/+$/, '')

/** False when no bucket was configured at build time, so the UI can say so
 *  instead of firing downloads at a relative path that will never resolve. */
export const DATA_CONFIGURED = DATA_BASE_URL !== ''

export function dataUrl(key: string): string {
  return `${DATA_BASE_URL}/${releasePath(key)}`
}

/** The manifest for the pinned release - see dataRelease.RELEASE_MANIFEST_PATH
 *  for why this is not the root `latest.json`. */
export function releaseManifestUrl(): string {
  return `${DATA_BASE_URL}/${RELEASE_MANIFEST_PATH}`
}

/** Mirrors publish.py's BACKGROUND_ARCHIVES. */
const BACKGROUND_ARCHIVES: Record<DetailLevel, string> = {
  light: 'background_z11.pmtiles',
  standard: 'background.pmtiles',
  fine: 'background_z13.pmtiles',
}

export function archiveUrl(level: DetailLevel): string {
  return dataUrl(BACKGROUND_ARCHIVES[level])
}

/** The same tier as `latest.json` names it - the flat key publish.py uploaded,
 *  which is what a published hash is looked up by (lib/dataManifest.ts). */
export function archiveKey(level: DetailLevel): string {
  return BACKGROUND_ARCHIVES[level]
}

/**
 * The hiking sheet's coverage cells - the index `pipeline/cut_cells.py` writes
 * beside the cell archives it cuts (#1175, features/OFFLINE_COVERAGE.md), read
 * by lib/coverageCells.ts.
 *
 * One 1°×1° cell per entry, named for its south-west corner the way a USGS
 * quad is (`n34w085`), with the flat key of its archive and its core bounds.
 * The list is what was BUILT, not what the grid defines: a corridor is a thin
 * band inside a big rectangle, and 62 of the 221 cells the A.T. package's
 * bounds cover hold trail (measured 2026-08-28, PR #1176). Which cells exist
 * is the one thing a phone cannot compute for itself, which is why this is
 * fetched rather than derived from the grid.
 *
 * A 404 is an ordinary answer - a release cut before the cells existed, or a
 * bucket a publish has not reached (production holds none while the cells
 * are UA-only) - and reads as "no pieces on offer": the whole sheet stays one
 * tap, and nothing the app had before is lost. It used to be held out of
 * `expected_client_keys`'s contract (pipeline/verify_release.py) for that
 * reason - an optional artifact must not fail the release gate by its absence.
 * Since #1048 it is IN the contract and declared optional there, which buys
 * the same immunity and says so out loud: absence is now a named SKIPPED in
 * the verdict rather than a key the gate never mentions.
 *
 * @release optional - published by whichever sheet's cut ran
 * (publish.py's CELL_FAMILIES loop), so a release holding none is the
 * partial-checkout posture that loop is written for rather than a gap.
 */
export const BASEMAP_CELLS_KEY = 'at_basemap_cells.json'

/**
 * @release required - publish.py:527 writes it from trails_manifest.json with
 * nothing in front of it, and it is the one key the client fetches through
 * `fetchArtifact` ("an artifact this release must have", lib/trailData.ts:724).
 */
export const TRAILS_KEY = 'trails.geojson'

/**
 * The mile of every centerline vertex in `trails.geojson`, on the pipeline's
 * calibrated axis (pipeline/export_trails.py's write_trail_miles, #1192).
 *
 * Keyed by the feature ids trails.geojson carries and naming that file's
 * hash, so a phone can only ever pair a line with the miles measured on it.
 * Optional the way spurs.json is: a release exported before it existed has
 * none, and the phone measures the line itself as it always did - with the
 * two-axis anchors lib/route.ts keeps for exactly that release.
 *
 * @release required - publish.py:553, ungated, beside the file it measures.
 */
export const TRAIL_MILES_KEY = 'trail_miles.json'

/**
 * The corridor-view centerline: the same trail, simplified to 100 m and
 * merged into one feature (pipeline/export_trails.py's write_overview, #869).
 *
 * 51,068 gzipped bytes against `trails.geojson`'s 4,143,296, measured against
 * the live bucket 2026-08-20 - 81x smaller, which at 12 Mbps is about 34 ms
 * of transfer against 2.8 s. That difference is the whole point: a first run
 * spends its three entry steps looking at the map behind them, and the real
 * centerline cannot arrive inside them.
 *
 * NOT NAVIGATION DATA, and the client has to keep that true. No point on it
 * is more than 100 m from the surveyed line, which is 0.013 px at the
 * corridor view and 0.43 px at the pin seam - and 14 px at z14, which is a
 * line in the wrong place. So it is drawn only below the seam
 * (map/style.ts's TRAIL_OVERVIEW_LAYER_ID), dropped the moment the real
 * centerline is on the map, and never stored: a phone with no signal has no
 * trail line, exactly as before, because what it is missing is the real one.
 *
 * Absent from a release exported before it existed, which reads as "no
 * overview" rather than as a failure - the same rule spurs.json and
 * elevation_profile.json already follow.
 *
 * @release required - publish.py:537 writes it whenever the trails manifest
 * carries an overview, with no gate in front. Absent from a release built
 * here, it is the promotion gap #1048 describes rather than an old release.
 */
export const TRAILS_OVERVIEW_KEY = 'trails_overview.geojson'

/**
 * The trail lines other organizations maintain - NYS OPRHP's, NYNJTC's,
 * Mohonk Preserve's and NYS DEC's (#950, #992, #1019,
 * pipeline/export_nearby_trails.py, features/NEARBY_TRAILS.md) - as vector
 * tiles (#1257, export_nearby_trails.py's write_tiles): what map/style.ts's
 * NEARBY_TRAILS_SOURCE_ID draws above the pin seam, through
 * map/networkTiles.ts.
 *
 * THEIR OWN ARTIFACT BECAUSE OF A LICENCE, not because of their size. Five
 * stewards, three different bases: ATC's centerline ships on recorded
 * permission, NYS OPRHP's on their own published terms (reuse permitted,
 * attribution REQUIRED - see map/credits.ts), and NYNJTC's, Mohonk Preserve's
 * and NYS DEC's on the maintainer's authorisation, since none of the three
 * states any terms at all. Keeping these lines out of `trails.geojson` is what
 * lets any one of those be held without touching the others, which is what
 * `reaches_hikers` exists to make possible per source. Both outstanding
 * licences resolved on 2026-08-24.
 *
 * THE FILE THIS IS CUT FROM IS NO LONGER A KEY HERE. `nearby_trails.geojson`
 * was the phone's artifact until 2026-09-07, when it was promoted at
 * 228,820,578 bytes with nationwide USFS trails in it (#1231) and every phone
 * that took it whole crashed its map (#1254). It stays published - it is what
 * these tiles are cut from, and pipeline/build_trail_graph.py and
 * fetch_trail_water.py read it - but no phone on this build asks for it, and
 * a key nothing fetches must not be declared here: verify_release.py's check
 * 22 weighs what config.ts declares, and would keep the gate red on a file no
 * phone parses. lib/nearbyTrailData.ts deletes the copy earlier releases
 * stored.
 *
 * READ BY BYTE RANGE, NEVER WHOLE, and that is the entire reason it exists. A
 * PMTiles archive is a header, directories and tiles; a phone reads the header
 * and root directory once, then one leaf directory and one tile per request,
 * each a ranged GET the bucket answers with the bytes asked for. So the
 * 228.8 MB above becomes some kilobytes a tile, however many organizations
 * the export grows to hold - the way the hiking sheet has shipped since it
 * existed, and these lines never did.
 *
 * Measured against that day's real file: 112,378 features tiled z9-z14 in
 * 92 s into 132,995,363 bytes and 173,209 tiles, 388 bytes of header and root
 * directory to open. Uploaded uncompressed (pipeline/lib/content_types.py's
 * BINARY_TYPES), because a gzipped body has no byte ranges to ask for.
 *
 * NOT STORED ON THE PHONE AS A WHOLE, said plainly: a tile read from the
 * bucket lives in the browser's HTTP cache and nowhere else. What a phone
 * keeps is the stretch it took - the 1° cells of these tiles under the hike
 * (NEARBY_TRAILS_CELLS_KEY below, #1257 stage 2), which map/networkTiles.ts
 * answers from before it asks the bucket. Off the stretch and with no
 * signal, the map above the seam draws no nearby trails: the state before
 * #1082 cached the whole file, and the state #1254's budget already left
 * every phone in from 2026-09-07.
 *
 * Absent from a release exported before write_tiles existed, which reads as
 * "no network above the seam" rather than as a failure: map/networkTiles.ts
 * asks latest.json before it asks the bucket, answers every tile empty when
 * the manifest names no archive, and the sketch below the seam still draws.
 *
 * TWO PROPERTIES THE TILES CARRY THAT THE FILE THEY ARE CUT FROM DOES NOT
 * (#1384, export_nearby_trails.py's SHARED GROUND block): where two trails
 * run on one treadway, the tiles also hold a PAIR of features on one chord,
 * each with `concurrent_with` (the other trail's name) and `concurrent_side`
 * (+1 or -1). map/sharedGround.ts draws them as two halves of one line, and
 * the network's own layers exclude them. A release cut before the pairing
 * existed carries neither property and draws exactly as it did.
 *
 * @release optional - inside its parent's `reaches_hikers` branch in
 * publish.py's collect_artifacts, held back and shipped as one decision with
 * the lines it is cut from.
 */
export const NEARBY_TRAILS_TILES_KEY = 'nearby_trails.pmtiles'

/**
 * The zoom range that archive is cut to - the one contract a tileset has that
 * a GeoJSON does not. A vector source asked for a zoom its archive does not
 * hold draws nothing, silently, with no error anywhere. So both ends are
 * declared here for the source map/style.ts builds, export_nearby_trails.py
 * declares its own pair (TILES_MIN_ZOOM, TILES_MAX_ZOOM) for the cut, and
 * pipeline/tests/test_export_nearby_trails.py reads this file to hold the two
 * pairs equal - the way verify_release.py reads the keys above.
 *
 * 9 is the pin seam (map/poiLayers.ts's POI_PIN_MIN_ZOOM), the zoom the full
 * network's layers already start at; below it the corridor-view sketch
 * (NETWORK_OVERVIEW_KEY) is the drawing of these trails, so tiles there would
 * be tiles nothing asks for. 14 is where the Fine hiking sheet stops and
 * MapLibre overzooms - a line simplified to 1 m (export_nearby_trails.py's
 * tolerance) has nothing more to show past it.
 */
export const NEARBY_TRAILS_TILES_MIN_ZOOM = 9
export const NEARBY_TRAILS_TILES_MAX_ZOOM = 14

/**
 * The same tiles cut into 1° coverage cells (#1257 stage 2): the index
 * pipeline/cut_cells.py writes for its `nearby_trails` family, the exact
 * shape of BASEMAP_CELLS_KEY's and read by the same lib/coverageCells.ts
 * code, so a stretch download (screens/StretchCard.tsx) carries the network
 * above the seam as well as the ground under it, and map/networkTiles.ts asks
 * a held cell before it asks the bucket - the local-first order
 * map/basemap.ts walks for the hiking sheet.
 *
 * No context archive, unlike the basemap's: the index's `context` is null,
 * because z9 nationwide is 9,653,907 bytes (measured 2026-09-07) for a zoom
 * the sketch already draws below and the cells draw above, so z9 rides in the
 * cells and a first stretch costs nothing shared.
 *
 * @release optional - inside its parent's `reaches_hikers` branch in
 * publish.py's collect_artifacts, the one gated cell family: held back and
 * shipped as one decision with the lines its cells are cut from.
 */
export const NEARBY_TRAILS_CELLS_KEY = 'nearby_trails_cells.json'

/**
 * The corridor-view sketch of that whole network (#1135,
 * pipeline/export_nearby_trails.py's write_overview) - trails_overview.geojson's
 * pattern applied to the artifact above, so the opening camera draws every
 * organization's trails without fetching or parsing the file whose lines only
 * draw from the pin seam anyway.
 *
 * WHAT BOTH OF THOSE WEIGH, and both figures here have moved by an order of
 * magnitude since they were first written. Measured 2026-08-27 against the
 * live artifacts, this said 255,263 gzipped bytes for all 7,669.7 line-miles
 * as 31 features, beside the A.T. overview's 51,068 - about 306 KB for every
 * line the opening camera can draw - and called its parent a 7.3 MB file.
 * Re-measured 2026-09-04 off `latest.json`:
 *
 *   nearby_trails.geojson    228,820,578 raw   59,155,072 on the wire
 *   network_overview.geojson  10,804,839 raw    3,042,884 on the wire (38 features)
 *
 * so the parent is 8x its stated size on the wire and this sketch is 12x its
 * stated size. THE CAUSE IS ONE FEATURE. `usfs_trails` was registered
 * nationwide (#1207), and `write_overview` unions each organization into one
 * simplified geometry - so a single feature of 437,633 vertices spanning the
 * country is 80.6% of this artifact's raw bytes and 2,577,012 of its 3,042,884
 * gzipped. Every other organization together is under 500 KB gzipped, which is
 * roughly the figure this comment used to claim for the whole thing.
 *
 * The sketch still saves a hiker the parent file, which is the argument for it
 * and is unchanged. What is no longer true is that it is cheap in absolute
 * terms, and whether nationwide USFS belongs in a corridor-view sketch at all
 * is #1231's question rather than this file's. Each feature
 * carries the three properties the paint and the tape read - `source`,
 * `blaze_color`, `trail_status` - so it draws through the same expressions the
 * real lines do, ghosting included, and closed ground stays closed-looking
 * below the seam.
 *
 * NOT NAVIGATION DATA, exactly like the A.T.'s sketch: no point on it is more
 * than 100 m from the exported line, so it draws only below the seam
 * (map/style.ts's NETWORK_OVERVIEW_LAYER_ID carries maxzoom for it) and the
 * real network takes over where its own layers start. Unlike that sketch it is
 * STANDING rather than a stand-in - nothing else draws these trails below z9 -
 * so it is cached and revalidated the way nearby_trails.geojson itself is
 * (lib/nearbyTrailData.ts), not dropped when something better lands.
 *
 * A 404 is an ordinary answer for the two reasons its parent's is: a release
 * exported before the artifact existed, and a bucket where either steward's
 * `reaches_hikers` is false - pipeline/publish.py holds this sketch back with
 * the artifact it sketches, as one decision.
 *
 * @release optional - inside its parent's `reaches_hikers` branch
 * (publish.py:587), held back and shipped as one decision with the lines.
 */
export const NETWORK_OVERVIEW_KEY = 'network_overview.geojson'

/**
 * The waypoints those same organizations publish (#1097,
 * pipeline/export_nearby_poi.py) — NYS DEC's lean-tos, primitive campsites and
 * privies, NYS OPRHP's vistas, parking areas and trail bridges. 8,480 features
 * on 2026-08-27, 0.37 MB gzipped.
 *
 * ONE KEY WITH MIXED `poi_type`s, where `poi_*.geojson` is one key per type,
 * and the difference is deliberate rather than an inconsistency. That namespace
 * carries the invariant *live rows of one poi_type* and the download list above
 * is built from it; this is one more optional artifact alongside
 * nearby_trails.geojson, read once. `readPois` already reads `poi_type` off
 * each feature, so a mixed collection costs it nothing.
 *
 * Its features join the SAME map source ATC's waypoints feed, which is the one
 * thing here that had to be got right: map/poiLayers.ts draws every waypoint
 * through a single symbol layer because MapLibre's collision engine can only
 * declutter symbols it places together, so a second source and a second layer
 * would have stacked a DEC lean-to on top of an A.T. shelter. Joining the array
 * instead means density, the legend's filters and POI_PRIORITY all keep working
 * as one system.
 *
 * A 404 is an ordinary answer, the same reading nearby_trails.geojson gets: a
 * release exported before the artifact existed, or a bucket a publish has not
 * reached. It is also what a hiker sees while either steward's `reaches_hikers`
 * is false — pipeline/publish.py holds the whole artifact back rather than
 * publishing part of it.
 *
 * @release optional - publish.py:622, the identical `reaches_hikers` gate the
 * lines above carry, over the same registry.
 */
export const NEARBY_POI_KEY = 'nearby_poi.geojson'

/**
 * The junction graph a day hike is routed over (#974, #975), in 1° cells
 * (#1257 stage 3, pipeline/cut_trail_graph.py): the index of the cells, in
 * the exact shape of BASEMAP_CELLS_KEY's and NEARBY_TRAILS_CELLS_KEY's, read
 * by lib/coverageCells.ts under its GRAPH_CELLS family.
 *
 * WHY CELLS. build_trail_graph.py derives the graph from the other
 * organizations' lines and the A.T.'s own, so the map and the router cannot
 * disagree about which trails exist - and with those lines nationwide since
 * #1231 the whole graph was promoted at 78,595,556 bytes on 2026-09-07.
 * Parsing it on the main thread was "the app is hanging on the first page"
 * (#1254), and the budget that stopped that left the phone with no day hikes
 * at all. So a phone now loads only the cells under the hike it is planning,
 * where it is standing, where its camera is past the seam, and where it
 * taps (lib/useTrailGraph.ts decides which), and nothing else: measured on
 * that day's graph, the densest cell is 12.7 MB of edges, the median 28 KB,
 * Harriman's 1.8 MB.
 *
 * FOUR HALVES PER CELL, one file each, named by {@link trailGraphCellKey}:
 * the routing shard (`graph`: nodes, edges, lengths, attribution, plus the
 * whole graph's ids for each), its edge vertices (`geometry`, fetched only
 * when the builder opens - with the whole A.T. in the graph it is by far the
 * heavier half), the climb along each edge (`elevation`, `[gain_ft, loss_ft]`
 * or null, the sanctioned TOTAL a card prices a walk from), and the dense
 * sampled `profile` a ribbon draws on a walk being followed (#1045) - fetched
 * only when a chart opens, never with the builder. The last two answer
 * different questions and must not be swapped: a per-edge profile cannot see
 * across a node join, so its totals would disagree with the card's.
 *
 * EVERY HALF IS INDEX-ALIGNED WITH ITS CELL'S EDGES, and lib/trailGraphData.ts
 * refuses a half whose length disagrees with the shard it was fetched for -
 * edge 40 drawn from edge 41's vertices is a route on the wrong trail, and
 * edge 40 priced from edge 41's climb is a plausible number against it. Two
 * rules a reader of the profile must not get wrong, both measured by the
 * pipeline: take the sample count from the array's own length, never from
 * `length_m` divided by the interval (63 of 40,596 edges disagreed); and a
 * null is unknown, never zero - a whole entry null is an edge the DEM never
 * covered, a null inside an array is one missing sample with its place kept,
 * and either means no ribbon for that walk.
 *
 * A 404 on the index is an ordinary answer: a release exported before the cut
 * existed, or a bucket holding the graph back with the lines it derives from.
 * lib/useTrailGraph.ts reads it as "no day hikes on this phone", which
 * chrome/PlanKindSheet.tsx says in a sentence rather than by offering a
 * control that does not work. A cell with no climb or profile half is "no
 * figures for this hike" and "no ribbon", exactly as the whole artifacts'
 * absence read - and on 2026-09-07 that is every cell, because the bucket's
 * companions were written for an earlier graph and the cutter refuses to cut
 * them against the wrong edges.
 *
 * THE WHOLE FILES ARE NO LONGER KEYS HERE. `trail_graph.json` and its three
 * companions stay published as the cut's input and for older clients; no
 * phone on this build asks for them, and a key nothing fetches must not be
 * declared, for the reason NEARBY_TRAILS_TILES_KEY gives about its own source.
 *
 * @release optional - inside the graph's own `reaches_hikers` branch in
 * publish.py's collect_artifacts, the same gate its lines carry: topology of
 * data a steward has not licensed is still that steward's data.
 */
export const TRAIL_GRAPH_CELLS_KEY = 'trail_graph_cells.json'

/** The four files one graph cell is published as - see TRAIL_GRAPH_CELLS_KEY. */
export type TrailGraphCellHalf = 'graph' | 'geometry' | 'elevation' | 'profile'

/**
 * The bucket key of one half of one graph cell - pipeline/cut_trail_graph.py's
 * cell_key, spelled the same way, and tests/test_cut_trail_graph.py reads this
 * file to hold the two spellings equal. Not a `*_KEY` constant because there
 * is one per cell per half; verify_release.py's check 22 weighs them by their
 * shape instead.
 */
export function trailGraphCellKey(name: string, half: TrailGraphCellHalf): string {
  return half === 'graph'
    ? `trail_graph_cell_${name}.json`
    : `trail_graph_${half}_cell_${name}.json`
}

// Where each blue-blazed spur leads, keyed by the trail id in trails.geojson.
//
// A separate artifact rather than properties on trails.geojson because the
// client stores that file as an opaque Blob and hands it straight to MapLibre
// (lib/trailData.ts) - it never reads a property off it, so enriching it would
// put the answer somewhere the app structurally cannot look.
//
// Published by pipeline/export_spurs.py. Absent from data releases built
// before that existed, which lib/trailData.ts treats as "no spur detail" - not
// as a failed download.
//
// @release required - publish.py:723, ungated.
export const SPURS_KEY = 'spurs.json'

// Who maintains which stretch of trail, published by
// pipeline/export_club_sections.py (#594): 30 clubs tiling 2,197.5 miles, plus
// the 38.5 miles in 27 runs ATC's own centerline cannot attribute.
//
// A separate artifact for the same reason spurs.json is one - the client hands
// trails.geojson to MapLibre as an opaque Blob and never reads a property off
// it. It carries mile ranges and no geometry, which is enough:
// lib/trailPosition.ts's trailSlice and trailPointAtMile turn a mile range into
// the coordinates the corridor view draws (features/CORRIDOR_VIEW.md, #598),
// so nothing about this needs the published centerline schema to change.
//
// Absent from releases built before export_club_sections.py, which
// lib/trailData.ts treats as "no attribution" rather than a failed download -
// the same way spurs.json is treated.
//
// @release required - publish.py:733, ungated.
export const CLUB_SECTIONS_KEY = 'club_sections.json'

// Who the map's data belongs to, published by pipeline/export_sources.py
// (#927, features/SOURCE_REGISTRY.md): one record per organization whose data
// actually reaches a hiker, with the licence and attribution that organization
// recorded.
//
// `stewards.json`, not `sources.json`, and deliberately - `pipeline/
// sources.json` is the REGISTRY the exporter reads, and a bucket key sharing
// its name would put two different files with one name in every conversation
// about where a licence came from.
//
// Absent from releases built before that exporter existed, which
// lib/trailData.ts treats as "no steward list" rather than a failed download -
// the same way club_sections.json above is treated.
//
// @release required - publish.py:745, ungated.
export const STEWARDS_KEY = 'stewards.json'

// Stretches of trail somebody says are worth going to, published by
// pipeline/export_highlights.py (#595): a name, ordered legs, and which basis
// the claim rests on.
//
// Small, keyed, and separate for the same reason club_sections.json is - and
// it carries no length, ascent or time, because the phone derives all three
// from the elevation profile it already holds (features/CORRIDOR_VIEW.md).
//
// Absent from releases built before that exporter, which lib/trailData.ts
// treats as "nothing to explore yet" rather than a failed download.
//
// @release required - publish.py:773, ungated. #940's own example: an
// exporter, a reference file, tests, a place in the manifest list, and three
// weeks in which nothing ran it.
export const HIGHLIGHTS_KEY = 'highlights.json'

// The along-the-trail elevation profile, published by
// pipeline/export_elevation.py: ~141,000 {distance_mi, elevation_ft} samples at
// 25 m spacing along the real centerline. 7.0 MB of JSON that gzips to 0.89 MB,
// measured against the live bucket 2026-08-15 - under 7% of what trails.geojson
// already costs, which is why it is fetched whole rather than windowed.
// Windowing it would also defeat the point: the ribbon has to work in a dead
// zone fifty miles from where it downloaded.
//
// That gzipped figure is only what a hiker actually pays since #717. This
// comment quoted it for a long time while pipeline/publish.py uploaded with no
// Content-Encoding at all, so R2 served every one of the 7.0 MB - a claim about
// a compression nothing was performing.
//
// Absent from data releases built before export_elevation.py existed, which
// lib/trailData.ts treats as "no profile" rather than a failed download - the
// same way spurs.json is treated.
//
// @release required - publish.py:714, ungated.
export const ELEVATION_KEY = 'elevation_profile.json'

// The tombstones: every POI id that has ever been retired, published by
// pipeline/export_retired_poi.py (#673, features/POI_IDENTITY.md §4).
//
// This is what makes "every id ever published resolves to something" true on
// a phone. Without it, a hiker whose photos are anchored to a water point the
// ATC dropped last September gets a card that renders nothing at all rather
// than one saying what happened to the place — and the anchors on a phone are
// the ones no server-side reconciliation can ever reach.
//
// NOT `poi_retired.geojson`, and the difference is load-bearing rather than
// stylistic: `poi_*.geojson` is a namespace in this repository carrying the
// invariant *live rows of one poi_type*, `poiKey()` below builds exactly that
// name, and verify_release's check 21 fails any feature in that glob whose id
// is not a live ledger row. A tombstone file under that name would fail once
// per tombstone, by construction.
//
// **Cheap, and measured rather than assumed.** 93 retired rows against the
// ledger on 2026-08-22, at 249 bytes a tombstone (measured 2026-08-19 over
// the first 21) — about 23 KB, against a first fetch already north of 5 MB
// gzipped. #831 held it out of this list "until there is something to draw
// with it", since the list is also the size of a hiker's first fetch. There
// is now: `screens/RemovedPoiCard.tsx`.
//
// Absent from releases built before that exporter, which lib/trailData.ts
// treats as "nothing has been retired" rather than a failed download — the
// same way spurs.json is treated.
//
// @release required - publish.py:784, ungated.
export const RETIRED_POI_KEY = 'retired_poi.geojson'

// Routes somebody published - a maintaining club, a guidebook author, another
// OurHike hiker, an editorial pick - for the Today shelf and the Find-a-hike
// screen (#1284, features/SUGGESTED_HIKES.md). Read by
// lib/suggestedHikesData.ts, which validates every record through the same
// gate a saved day hike passes (lib/dayHikes.ts: ends only, never an
// edgeIndex) and keeps the last copy that arrived in IndexedDB, so the shelf
// works with no signal like everything else here.
//
// THE CLIENT HALF LANDED FIRST (#1284), and the pipeline half followed with
// NYNJTC's Favorite Hikes (#1290): pipeline/export_suggested_hikes.py writes
// this from the routes a person has signed off in
// pipeline/reference/nynjtc_hike_routes.json, measured on the junction graph
// by the twin of this app's own router. It is absent from a release for
// three reasons the client reads alike - the source's reaches_hikers, no row
// signed off yet, or a run that did not reach the exporter - and every one
// is a phone with an empty shelf and no section, never a failed download.
//
// @release optional - gated in publish.py on a manifest the exporter writes
// only when a reviewed row exists; see the paragraph above.
export const SUGGESTED_HIKES_KEY = 'suggested_hikes.json'

// The places a hiker can name before anything is downloaded - parks, towns,
// trailheads, parking areas and the long trails - published by
// pipeline/export_places.py, which lands with PR #1372 (#1371) and is not
// in this tree until it merges; until it is published, first run's place
// field reads "not published yet" and offers Skip. Read by lib/placesData.ts for first
// run's "where do you hike?" step (#1373, frame 1b), whose answer becomes the
// map's fallback centre whenever GPS has no fix, and for every place search
// after it. Kept in IndexedDB through the same cache the conditions ride, so
// the search works with no signal once it has arrived once.
//
// Every figure a row prints is the exporter's own measurement over the
// lines that run published it, and the document says when nothing could be
// measured (`trailMilesMeasured: false`) - absent means unknown, never zero.
//
// @release optional - the exporter writes a manifest publish.py collects;
// a release built before it existed has none, which the client reads as
// "nothing to search yet" and never as a failed download.
export const PLACES_KEY = 'places.json'

// 'crossing' was listed here while it was still an empty FeatureCollection, so
// that it would start working the day the pipeline filled it rather than
// needing a client release to notice. IT WORKED, and the comment outlived the
// fact: NHD ingestion has landed and production release 2026-09-04 publishes
// **5,318** crossings, measured off the live artifact (PR #1247).
//
// 1,126 of those carry an A.T. mile and sit a median of 0 ft from the
// centerline - they are line intersections, so they are as on-trail as a
// waypoint gets. The other 4,192 carry `mile: null`, which is
// export_poi.mark_off_trail_records (#1016) withholding it on purpose: a
// crossing on somebody else's trail must not become a candidate stop in an
// A.T. itinerary. Both halves draw; only the first can be planned around.
//
// `trailhead` is the empty-but-present layer now (0 features on that same
// release), and #1218 is why - USFS's 7,358 trailheads ship as parking pins
// today. So the argument for listing a key before it has data is unchanged and
// is currently being made by a different poi_type.
//
// This list is the download list, so it is also the size of a hiker's first
// fetch. 'viewpoint', 'parking' and 'privy' roughly double the POI count
// (2,021 more features from ATC's own facility layers) - real weight, and
// still small beside trails.geojson, which at 12.3 MB raw and 4.1 MB gzipped
// (measured 2026-08-15) is the artifact that decides whether a download over a
// hostel's wifi is comfortable. The whole launch fetch is 21.5 MB of text that
// gzips to 5.3 MB, which is what #717 made it cost.
//
// Keep it in step with pipeline/lib/poi_schema.POI_TYPES: verify_release.py
// parses THIS array to know which artifacts a release must serve, so a type
// published but missing here is a layer that silently never reaches a phone.
//
// NOTHING GOES INSIDE THE BRACKETS BUT TYPE NAMES. That parser is a regex -
// it takes everything up to the `]` and then reads every single-quoted run as
// a type - so a comment in there carrying an apostrophe ("OPRHP's", "the day
// ATC fills it") publishes fragments of English as POI categories. Measured
// the hard way at #1197, where the contract test caught two of them. Say it
// out here instead.
//
// 'trailhead' (#1197) is where a hiker STARTS, and it is empty on the A.T.
// today exactly as 'crossing' is: ATC publishes no trailhead layer, and the
// 287 that ship are OPRHP's, which arrive inside `nearby_poi.geojson` rather
// than as a per-type artifact. It is listed anyway for 'crossing's reason -
// so it starts working the day ATC fills it, rather than needing a client
// release to notice.
export const POI_TYPES = [
  'shelter',
  'water',
  'campsite',
  'resupply',
  'crossing',
  'viewpoint',
  'parking',
  'privy',
  'trailhead',
] as const

export type PoiType = (typeof POI_TYPES)[number]

export function poiKey(type: PoiType): string {
  return `poi_${type}.geojson`
}

/**
 * Every artifact `downloadTrailData` fetches, and therefore every artifact a
 * refresh compares and re-fetches (#919).
 *
 * Derived from the same constants the download itself uses rather than typed
 * out again, so a layer added to that download joins the refresh in the same
 * change. A hardcoded second list is precisely how `poi_privy.geojson` could
 * come to be downloaded on first run and never updated afterwards, which is
 * the failure this whole mechanism exists to end.
 *
 * The archives are deliberately absent - vector only, the maintainer's
 * decision (2026-08-21). See lib/dataRefresh.ts.
 */
export const REFRESHABLE_KEYS: readonly string[] = [
  TRAILS_KEY,
  TRAIL_MILES_KEY,
  ...POI_TYPES.map(poiKey),
  NEARBY_POI_KEY,
  SPURS_KEY,
  CLUB_SECTIONS_KEY,
  STEWARDS_KEY,
  HIGHLIGHTS_KEY,
  RETIRED_POI_KEY,
  ELEVATION_KEY,
]
