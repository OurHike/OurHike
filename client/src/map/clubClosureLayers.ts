// Every club closure on the map (the maintainer's polls of 2026-10-11): the
// source and the layers, which map/style.ts builds when the map opens. The
// data and the taps are map/clubClosureTaps.ts, loaded the first time there
// is a closure to draw. Neither is in the launch bundle
// (features/LAUNCH_BUDGET.md §3): map/style.ts loads behind the map screen.
//
// THE STANDARD IS S6, AS THE MAINTAINER DREW IT (s6-map.html, adopted by poll
// about 17:45 UTC): every closure in conditions/trail_closures.json, crossed
// out with the mark every other closure feed wears (lib/closureStyle.ts). A
// line closure is crossed out along its own line; an area closure's trails
// are crossed out where they run inside it, which the pipeline cuts into
// lines hourly, so here an area is lines like any other; a point closure is
// one cross, or one at each point of a MultiPoint. ATC's closures are not in
// the file: ATC's own band draws them (map/atcUpdateLayers.ts). The A.T. is
// crossed out like any trail where it runs inside a club's area (decision
// 192, the poll of 2026-10-14, "Yes, like any trail"): the pipeline cuts its
// lines with the rest, and these layers sit above the A.T.'s own line in
// map/style.ts.
//
// A CLOSURE TOO SHORT FOR THE CHAIN KEEPS THE BOLD ✕ (decision 198, the poll
// of 2026-10-15, "B: bold ✕ until chain fits"). The chain of small crosses
// puts none on a run shorter than about 9.33 px, and club closures run down
// to 4.5 m, so the far mark does not stop at CLOSURE_NEAR_MIN_ZOOM here: each
// line closure carries the first zoom its longest run is
// CLOSURE_MARK_UNTIL_CROSSES chain crosses long (`clubClosureChainFrom`), and
// the far mark stays on it until then. A long closure looks exactly as it did
// before; at latitude 41 a 20 m one is one bold ✕ from z7 to z17. The source
// keeps every line, however short (`buildClubClosureSource`), because the far
// mark is placed on the line.
//
// NOTHING OF A CLUB CLOSURE DRAWS FARTHER OUT THAN CLOSURE_MARK_MIN_ZOOM, the
// pin seam the far mark and the point cross already started at (thread
// 4279229785 of the collaborator's review of #1805 — dlt → dbt re-platform as
// one go/no-go change, 2026-10-15). The paper, the trace and the shade had no
// minzoom, and lib/closureStyle.ts's widths stop tapering at that zoom, so
// farther out every closure was a 4 px white paper under a 1.4 px dotted
// trace whatever its length: on UA's file of 2026-10-15, 8,987 of the 10,262
// line parts (88%) are under 1 px at z5 on MapLibre's 512 px tiles, and the
// review saw its 1,661 closures draw as black-and-white smudges over the West
// from the opening camera in (rendered at z5 to z7 the same day). The other
// closure feeds were already held off those zooms by their own sources and
// map/style.ts's clamps. Whether a closure should say anything below the seam
// is the maintainer's call, and this does not make it: no mark starts lower.
//
// AN AREA NO MAPPED TRAIL RUNS INSIDE IS SHADED (decision 191, the poll of
// 2026-10-14, "Shade them, no edge", from open-questions-1014.html's frame
// A): its own outline, a `shade` row, filled with a light diagonal hatch in
// the design system's stone and nothing drawn on its edge, so an open trail
// along the edge never reads as closed. Unlike the crossed-out mark it sits
// UNDER every trail line, in the hazard areas' place in the stack, so any
// line inside or along it is drawn over it whole. Its pixels are
// map/closureShade.ts's, registered with the data.
//
// WHAT DRAWS IS DECIDED BEFORE IT GETS HERE. chrome/noticesPanel.tsx hands
// the map only the closures that close the trail on the phone's own day
// (lib/noticeCurrency.ts's `obstructsOn`: from the day before a closure's
// own start). A closure the list greys as possibly stale draws with the same
// full mark: the maintainer chose "B: same mark" over fading it, so only its
// sheet says it may no longer apply.
//
// THE ROUTER DOES NOT READ ANY OF THIS. A route still goes through a closure
// drawn here until a later change (the maintainer's Q2 answer, "Build the map
// file now", whose option said so); the closure's sheet says OurHike does not
// work out detours.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { Map as MapLibreMap } from 'maplibre-gl'
import {
  buildClosureLayers,
  CLOSURE_CROSS_ICON_ID,
  CLOSURE_CROSS_SIZE,
  closureCrossImageSize,
  CLOSURE_MARK_HALO_WIDTH,
  CLOSURE_MARK_MIN_ZOOM,
  CLOSURE_MARK_SIZE,
  CLOSURE_MARK_UNTIL_CROSSES,
  CLOSURE_NEAR_MIN_ZOOM,
  closurePointId,
} from '../lib/closureStyle'
import type { NoticeGeometryValue } from '../lib/noticeGeometry'
import { CLUB_CLOSURE_ID_PROPERTY } from './closureLayers'
import { redLightActive, sheetIsDark } from './sheetInks'
import type { SheetAppearance } from './sheets'
import { CLUB_CLOSURE_LAYER_ID } from './styleIds'

export const CLUB_CLOSURE_SOURCE_ID = 'club-closures'

/** The hatch over an area no mapped trail runs inside (decision 191). Here
 *  and not in map/styleIds.ts, which the launch bundle carries: nothing
 *  there needs it. */
export const CLUB_CLOSURE_SHADE_LAYER_ID = 'club-closure-shade'

/** The areas, a tile feature of type Polygon - a MultiPolygon included, as
 *  the line filter takes a MultiLineString. */
export const CLUB_CLOSURE_SHADE_FILTER: unknown[] = ['==', ['geometry-type'], 'Polygon']

/** The hatch's ink family per sheet, as the hiker's mark has one
 *  (map/sheetInks.ts's positionInkFor): red light's one hue where it is in
 *  force, a light stone on every other dark sheet, the frame's own stone by
 *  day. */
export type ShadeInk = 'day' | 'night' | 'red'

export const SHADE_INKS: readonly ShadeInk[] = ['day', 'night', 'red']

export function shadeInkFor(appearance: SheetAppearance): ShadeInk {
  if (redLightActive(appearance)) return 'red'
  return sheetIsDark(appearance) ? 'night' : 'day'
}

/** The pattern image an ink family's hatch is drawn with (map/closureShade.ts). */
export function clubClosureShadeImageId(ink: ShadeInk): string {
  return `club-closure-shade-${ink}`
}

/**
 * The shaded areas' layer: a fill of the hatch and nothing else, the
 * sheet's image named at build and again on every sheet change
 * (map/style.ts's attachMapAppearance).
 *
 * `fill-antialias` OFF, which is the "no edge" of the maintainer's choice
 * held literally: MapLibre antialiases a fill by drawing its outline again
 * over it, and for a pattern with no `fill-outline-color` that pass draws
 * the pattern itself as lines along the edge (maplibre-gl 6.7.0's fill
 * draw, its `fillOutlinePattern` program, read 2026-10-14) - the wash twice
 * over along the edge, a faint line around every area. Off, the hatch
 * simply stops at the edge, a stair-step a pixel deep at most.
 */
export function buildClubClosureShadeLayer(
  appearance: SheetAppearance,
): LayerSpecification {
  return {
    id: CLUB_CLOSURE_SHADE_LAYER_ID,
    type: 'fill',
    source: CLUB_CLOSURE_SOURCE_ID,
    filter: CLUB_CLOSURE_SHADE_FILTER as never,
    // From the pin seam in, with the rest of the feed (the header's NOTHING
    // OF A CLUB CLOSURE): farther out an area is a few pixels of hatch.
    minzoom: CLOSURE_MARK_MIN_ZOOM,
    paint: {
      'fill-pattern': clubClosureShadeImageId(shadeInkFor(appearance)),
      'fill-antialias': false,
    },
  }
}

/**
 * Which shaded area a touch landed inside, by notice id, or null: the point
 * itself, since an area is all the target a thumb needs. A hazard area is
 * asked in the 22 px box its sites' dots need instead (map/hazardAreaTaps.ts's
 * `hazardIdAt`), so a touch that close outside its edge still opens it.
 *
 * Here rather than in map/clubClosureTaps.ts because the hazard areas' tap
 * asks it too, to yield (a closure outranks an advisory on the same
 * ground), and that module should not load this feed's chunk to ask.
 * Silent before the style holds the layer, for `closureIdAt`'s reason.
 */
export function clubClosureShadeIdAt(
  map: MapLibreMap,
  point: { x: number; y: number },
): string | null {
  if (map.getLayer(CLUB_CLOSURE_SHADE_LAYER_ID) === undefined) return null
  const [feature] = map.queryRenderedFeatures([point.x, point.y], {
    layers: [CLUB_CLOSURE_SHADE_LAYER_ID],
  })
  const id = feature?.properties?.[CLUB_CLOSURE_ID_PROPERTY]
  return typeof id === 'string' && id !== '' ? id : null
}

/** The lines a closure is crossed out along: a line closure's own, and the
 *  trail stretches cut inside an area. A GeoJSON source's features reach a
 *  filter as tile features, whose `geometry-type` is LineString for a
 *  MultiLineString too (maplibre-gl-style-spec 26's EvaluationContext reads
 *  the tile's numeric type), so one test takes both. */
export const CLUB_CLOSURE_LINE_FILTER: unknown[] = ['==', ['geometry-type'], 'LineString']

/** The points, each drawn as one cross: a tile feature of type Point, a
 *  MultiPoint included, as the line filter takes a MultiLineString, and
 *  maplibre-gl 6.7.0's symbol layout places an icon at each point of it
 *  (src/symbol/symbol_layout.ts, read 2026-10-15). */
export const CLUB_CLOSURE_POINT_FILTER: unknown[] = ['==', ['geometry-type'], 'Point']

/**
 * An empty source, filled once the closures land - `buildHazardSource`'s
 * reason: a style naming a source it does not have drops the WebGL context.
 * No `attribution`, for the ATC notices' reason in map/style.ts: what a hiker
 * needs is the closing organization's name on the closure, which its sheet
 * gives (chrome/ClubClosureSheet.tsx).
 *
 * `tolerance: 0`, SO NO CLOSURE IS DROPPED AT A FAR ZOOM (decision 198).
 * MapLibre tiles a GeoJSON source with @maplibre/geojson-vt, which leaves out
 * any line part shorter than the source's tolerance (6.1.1's tile.ts,
 * `addLine`), 0.375 CSS px by default, and the far mark is placed on the
 * line, so a dropped closure had no mark at all: 78 of the 1,021 line
 * closures in UA's file of 2026-10-14 at z7, 16 at z9. The same number sets
 * how far the line is simplified, so a value that keeps the 4.5 m closure at
 * z7 (under 0.0103 px) already gives up nearly all of the simplification, and
 * 0 costs little more while keeping any length.
 *
 * What it costs, measured 2026-10-15 on that file at maplibre-gl 6.7.0's own
 * scaling (8192 / 512 per px, a 128 px buffer), on a desktop CPU and not a
 * phone: the densest tile, z7/21/44 over north-central Washington's fire
 * closures, goes from 8,168 vertices to 83,321, and geojson-vt builds it in
 * 97.6 ms instead of 29.7 (medians of 15). In maplibre-gl in headless
 * Chromium, from `setData` to that tile loaded took 1,414 ms instead of 1,278
 * (medians of 8; single runs ranged from 1,038 to 1,934 ms), and to the map
 * idle 2,163 instead of 1,699. By z10 the densest tile's vertices only
 * double, 16,254 to 32,568. @unvalidated on a phone.
 */
export function buildClubClosureSource(): GeoJSONSourceSpecification {
  return {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
    tolerance: 0,
  }
}

/** The feature property a line closure carries saying the first whole zoom
 *  its chain can carry it (`clubClosureChainFrom`), which the far mark reads
 *  to let go of it then (lib/closureStyle.ts's `markUntil`). */
export const CLUB_CLOSURE_CHAIN_FROM_PROPERTY = 'chain_from'

/** The zoom `clubClosureChainFrom` answers for a run the chain never carries:
 *  MapLibre's highest, so the far mark stays at every zoom. */
export const CLUB_CLOSURE_NEVER_CHAINED = 24

type Position = [number, number]

/** A line closure's runs: its one line, or each part of a MultiLineString,
 *  an area's cut stretches among them. None for any other geometry. */
function runsOf(geometry: NoticeGeometryValue): Position[][] {
  if (geometry.type === 'LineString') return [geometry.coordinates as Position[]]
  if (geometry.type === 'MultiLineString') return geometry.coordinates as Position[][]
  return []
}

/** A lon/lat in CSS px of MapLibre's 512 px Web Mercator world at z0. */
function worldPx([lon, lat]: Position): Position {
  const sin = Math.sin((lat * Math.PI) / 180)
  return [
    ((lon + 180) / 360) * 512,
    (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * 512,
  ]
}

/** The longest run of a line closure in CSS px at z0, or null for a closure
 *  that is not a line. On screen at zoom z it is this times 2^z, the length
 *  MapLibre measures the chain against. */
export function longestRunAtZ0(geometry: NoticeGeometryValue): number | null {
  let longest: number | null = null
  for (const run of runsOf(geometry)) {
    let length = 0
    for (let i = 1; i < run.length; i += 1) {
      const [x0, y0] = worldPx(run[i - 1])
      const [x1, y1] = worldPx(run[i])
      length += Math.hypot(x1 - x0, y1 - y0)
    }
    if (longest === null || length > longest) longest = length
  }
  return longest
}

/** One chain cross on screen at a whole zoom: closureCrossImageSize() at
 *  CLOSURE_CROSS_SIZE's `icon-size`, interpolated as the style does. */
function chainCrossPx(zoom: number): number {
  const stops = CLOSURE_CROSS_SIZE
  let scale = stops[stops.length - 1][1]
  if (zoom <= stops[0][0]) scale = stops[0][1]
  for (let i = 1; i < stops.length; i += 1) {
    const [z0, s0] = stops[i - 1]
    const [z1, s1] = stops[i]
    if (zoom > z0 && zoom <= z1) scale = s0 + ((zoom - z0) / (z1 - z0)) * (s1 - s0)
  }
  return closureCrossImageSize() * scale
}

/**
 * The first whole zoom, from CLOSURE_NEAR_MIN_ZOOM in, at which a line
 * closure's longest run is CLOSURE_MARK_UNTIL_CROSSES chain crosses long on
 * screen, and so the far mark lets go of it (decision 198); null for a
 * closure that is not a line. Read off the geometry alone, never the notice,
 * so a closure the list greys is drawn as any other.
 */
export function clubClosureChainFrom(geometry: NoticeGeometryValue): number | null {
  const run = longestRunAtZ0(geometry)
  if (run === null) return null
  for (let zoom = CLOSURE_NEAR_MIN_ZOOM; zoom < CLUB_CLOSURE_NEVER_CHAINED; zoom += 1) {
    if (run * 2 ** zoom >= CLOSURE_MARK_UNTIL_CROSSES * chainCrossPx(zoom)) return zoom
  }
  return CLUB_CLOSURE_NEVER_CHAINED
}

/**
 * One cross at each point closure (the maintainer's S6: "a point one ✕"),
 * and one at each point of a MultiPoint: lib/closureStyle.ts's far mark -
 * its image, size, ink and paper halo - placed at the point, with the id
 * `closurePointId` gives.
 *
 * FROM CLOSURE_MARK_MIN_ZOOM, LIKE THE FAR MARK, so below the pin seam a
 * point closure draws nothing: the maintainer's call of 2026-09-08 (#1292 —
 * Below the seam the map draws marks that read as waypoints; the opening
 * camera should draw trail lines only) keeps point marks off the far zooms,
 * and a point has no run to knock out of a trail there. NO MAXZOOM: the far mark gives way to a chain along its
 * line, and a point has no line for a chain.
 *
 * ALWAYS DRAWN, where the far mark collides (lib/closureStyle.ts's
 * CLOSURE_MARK_PADDING): the far mark drops the extra candidates of one
 * closed network, while this cross is a closure's only mark at its point, so
 * dropping it for a label would draw a closed bridge as open. It still holds
 * its place (`icon-ignore-placement` is left false), so a waypoint pin under
 * it falls back to its dot, the standing the far mark already has.
 */
export function buildClosurePointLayer(
  sourceId: string,
  ground: string,
  ink: string,
  bandId: string,
  filter: unknown[],
): LayerSpecification {
  return {
    id: closurePointId(bandId),
    type: 'symbol',
    source: sourceId,
    filter: filter as never,
    minzoom: CLOSURE_MARK_MIN_ZOOM,
    layout: {
      'icon-image': CLOSURE_CROSS_ICON_ID,
      'icon-size': CLOSURE_MARK_SIZE,
      'icon-rotation-alignment': 'viewport',
      'icon-allow-overlap': true,
    },
    paint: {
      'icon-color': ink,
      'icon-halo-color': ground,
      'icon-halo-width': CLOSURE_MARK_HALO_WIDTH,
    },
  }
}

/** The crossed-out mark along every closed line, then one cross per closed
 *  point, on the sheet's paper and in the closure ink (map/style.ts's
 *  closureTapeGround and closureInk). None of it starts farther out than
 *  CLOSURE_MARK_MIN_ZOOM (the header's NOTHING OF A CLUB CLOSURE): the
 *  paper and the trace are held to it, as map/style.ts holds the network's
 *  closure tiles to theirs; the chain, the far mark and the point cross
 *  start where they already did. */
export function buildClubClosureLayers(
  ground: string,
  ink: string,
): LayerSpecification[] {
  return [
    ...buildClosureLayers(CLUB_CLOSURE_SOURCE_ID, {
      ground,
      ink,
      bandId: CLUB_CLOSURE_LAYER_ID,
      filter: CLUB_CLOSURE_LINE_FILTER,
      markUntil: CLUB_CLOSURE_CHAIN_FROM_PROPERTY,
    }).map(
      (layer) =>
        ({
          ...layer,
          minzoom: Math.max(layer.minzoom ?? 0, CLOSURE_MARK_MIN_ZOOM),
        }) as LayerSpecification,
    ),
    buildClosurePointLayer(
      CLUB_CLOSURE_SOURCE_ID,
      ground,
      ink,
      CLUB_CLOSURE_LAYER_ID,
      CLUB_CLOSURE_POINT_FILTER,
    ),
  ]
}

// ---------------------------------------------------------------------------
// PROTOTYPE, NOT WIRED IN (frames for Q22 of #1805 — dlt → dbt re-platform as
// one go/no-go change, 2026-10-15): the maintainer chose "A small mark from
// z5" over "nothing below z7". One mark per club closure, of every
// organization, at z5 and z6 only, on its own small source of one point per
// closure, so the line source's `tolerance: 0` and the clamp above are not
// touched. Three variants are drawn for the maintainer to pick from; none is
// in map/style.ts yet. Every size below is @unvalidated: picked off the
// renders of 2026-10-15 to read as legible but quieter than the z7 far mark
// (CLOSURE_MARK_SIZE, about 16 px of ink), and settled only by the
// maintainer's pick and a look on a real phone.
// ---------------------------------------------------------------------------

/** The far-out marks' own source: one Point per closure. */
export const CLUB_CLOSURE_FAR_SOURCE_ID = 'club-closures-far'

/** The id of the far-out marks' layer (and of its count, in the counted
 *  variant). */
export const CLUB_CLOSURE_FAR_LAYER_ID = 'club-closure-far'
export const CLUB_CLOSURE_FAR_COUNT_LAYER_ID = 'club-closure-far-count'

/** The first zoom the far-out mark draws at: the maintainer's "from z5". It
 *  stops at CLOSURE_MARK_MIN_ZOOM (maxzoom is exclusive), where the paper,
 *  the trace, the far mark and the point cross take over, so no zoom draws
 *  both. */
export const CLUB_CLOSURE_FAR_MIN_ZOOM = 5

export type ClubClosureFarVariant = 'cross' | 'dot' | 'counted'

/** The small cross's `icon-size`: the chain's own cross at full size, about
 *  7.2 px of ink (CLOSURE_CROSS_ARM + CLOSURE_CROSS_STROKE / 2, twice), under
 *  half the z7 far mark's. */
export const CLUB_CLOSURE_FAR_CROSS_SIZE = 1

/** The small cross's collision padding in CSS px, where it collides. */
export const CLUB_CLOSURE_FAR_CROSS_PADDING = 2

/** The dot's radius in CSS px (a 5 px dot), and its paper ring. */
export const CLUB_CLOSURE_FAR_DOT_RADIUS = 2.5
export const CLUB_CLOSURE_FAR_DOT_RING = 1

/** The counted variant's cluster radius in CSS px: closures whose marks
 *  fall within it share one disc with their number on it. */
export const CLUB_CLOSURE_FAR_CLUSTER_RADIUS = 28

/** The point a closure's far-out mark sits at: halfway along a line
 *  closure's longest run, a point closure's (first) point, the middle of a
 *  shaded area's outer ring's box. Null for a geometry with no coordinates. */
export function clubClosureFarPoint(geometry: NoticeGeometryValue): Position | null {
  const g = geometry as { type: string; coordinates: unknown }
  if (g.type === 'Point') return g.coordinates as Position
  if (g.type === 'MultiPoint') return (g.coordinates as Position[])[0] ?? null
  if (g.type === 'Polygon' || g.type === 'MultiPolygon') {
    const ring =
      g.type === 'Polygon'
        ? (g.coordinates as Position[][])[0]
        : (g.coordinates as Position[][][])[0]?.[0]
    if (ring === undefined || ring.length === 0) return null
    const xs = ring.map((p) => p[0])
    const ys = ring.map((p) => p[1])
    return [
      (Math.min(...xs) + Math.max(...xs)) / 2,
      (Math.min(...ys) + Math.max(...ys)) / 2,
    ]
  }
  let best: Position[] | null = null
  let bestLength = -1
  for (const run of runsOf(geometry)) {
    let length = 0
    for (let i = 1; i < run.length; i += 1) {
      length += Math.hypot(run[i][0] - run[i - 1][0], run[i][1] - run[i - 1][1])
    }
    if (length > bestLength) [best, bestLength] = [run, length]
  }
  if (best === null || best.length === 0) return null
  let left = bestLength / 2
  for (let i = 1; i < best.length; i += 1) {
    const step = Math.hypot(best[i][0] - best[i - 1][0], best[i][1] - best[i - 1][1])
    if (step >= left && step > 0) {
      const t = left / step
      return [
        best[i - 1][0] + t * (best[i][0] - best[i - 1][0]),
        best[i - 1][1] + t * (best[i][1] - best[i - 1][1]),
      ]
    }
    left -= step
  }
  return best[best.length - 1]
}

export function buildClubClosureFarSource(
  variant: ClubClosureFarVariant,
): GeoJSONSourceSpecification {
  return {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
    ...(variant === 'counted'
      ? {
          cluster: true,
          clusterRadius: CLUB_CLOSURE_FAR_CLUSTER_RADIUS,
          clusterMaxZoom: CLOSURE_MARK_MIN_ZOOM - 1,
        }
      : {}),
  }
}

/** The far-out marks, z5 to z6, in the closure ink on the sheet's paper:
 *  `cross` the small ✕, `dot` a 5 px dot, `counted` the small ✕ for a lone
 *  closure and a paper disc with the number where several share a spot.
 *  The counted variant's number needs the style's bundled glyphs. */
export function buildClubClosureFarLayers(
  variant: ClubClosureFarVariant,
  ground: string,
  ink: string,
): LayerSpecification[] {
  const zooms = { minzoom: CLUB_CLOSURE_FAR_MIN_ZOOM, maxzoom: CLOSURE_MARK_MIN_ZOOM }
  // The small cross takes part in collision in the `cross` variant, as the
  // z7 far mark does (CLOSURE_MARK_PADDING's reason): where marks would
  // pile into one black blot (north-central Washington's 809 fire closure
  // lines at z5), the first keeps its place and the rest are dropped, so a
  // dense area reads as a few crosses. In `counted` nothing is dropped: the
  // clusters already keep lone crosses apart.
  const thinned = variant === 'cross'
  const cross = (filter?: unknown[]): LayerSpecification =>
    ({
      id: CLUB_CLOSURE_FAR_LAYER_ID,
      type: 'symbol',
      source: CLUB_CLOSURE_FAR_SOURCE_ID,
      ...zooms,
      ...(filter === undefined ? {} : { filter }),
      layout: {
        'icon-image': CLOSURE_CROSS_ICON_ID,
        'icon-size': CLUB_CLOSURE_FAR_CROSS_SIZE,
        'icon-allow-overlap': !thinned,
        'icon-ignore-placement': !thinned,
        'icon-padding': CLUB_CLOSURE_FAR_CROSS_PADDING,
      },
      paint: {
        'icon-color': ink,
        'icon-halo-color': ground,
        'icon-halo-width': CLOSURE_CROSS_HALO_WIDTH_FAR,
      },
    }) as LayerSpecification
  if (variant === 'dot') {
    return [
      {
        id: CLUB_CLOSURE_FAR_LAYER_ID,
        type: 'circle',
        source: CLUB_CLOSURE_FAR_SOURCE_ID,
        ...zooms,
        paint: {
          'circle-radius': CLUB_CLOSURE_FAR_DOT_RADIUS,
          'circle-color': ink,
          'circle-stroke-color': ground,
          'circle-stroke-width': CLUB_CLOSURE_FAR_DOT_RING,
        },
      } as LayerSpecification,
    ]
  }
  if (variant === 'cross') return [cross()]
  const clustered: unknown[] = ['has', 'point_count']
  return [
    cross(['!', clustered]),
    {
      id: `${CLUB_CLOSURE_FAR_LAYER_ID}-disc`,
      type: 'circle',
      source: CLUB_CLOSURE_FAR_SOURCE_ID,
      ...zooms,
      filter: clustered as never,
      paint: {
        'circle-radius': ['step', ['get', 'point_count'], 8, 10, 10, 100, 12],
        'circle-color': ground,
        'circle-stroke-color': ink,
        'circle-stroke-width': 1.5,
      },
    } as LayerSpecification,
    {
      id: CLUB_CLOSURE_FAR_COUNT_LAYER_ID,
      type: 'symbol',
      source: CLUB_CLOSURE_FAR_SOURCE_ID,
      ...zooms,
      filter: clustered as never,
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': ['Noto Sans Regular'],
        'text-size': 10,
        'text-allow-overlap': true,
        'text-ignore-placement': true,
      },
      paint: { 'text-color': ink },
    } as LayerSpecification,
  ]
}

/** The small cross's paper ring, a little wider than the chain's
 *  CLOSURE_CROSS_HALO_WIDTH because far out it sits on the map, often on a
 *  red trail, not on the closure's own paper. */
export const CLOSURE_CROSS_HALO_WIDTH_FAR = 1.5
