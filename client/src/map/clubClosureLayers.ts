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
  CLOSURE_MARK_HALO_WIDTH,
  CLOSURE_MARK_MIN_ZOOM,
  CLOSURE_MARK_SIZE,
  closurePointId,
} from '../lib/closureStyle'
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

/** An empty source, filled once the closures land - `buildHazardSource`'s
 *  reason: a style naming a source it does not have drops the WebGL context.
 *  No `attribution`, for the ATC notices' reason in map/style.ts: what a
 *  hiker needs is the closing organization's name on the closure, which its
 *  sheet gives (chrome/ClubClosureSheet.tsx). */
export function buildClubClosureSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/**
 * One cross at each point closure (the maintainer's S6: "a point one ✕"),
 * and one at each point of a MultiPoint: lib/closureStyle.ts's far mark -
 * its image, size, ink and paper halo - placed at the point, with the id
 * `closurePointId` gives.
 *
 * FROM CLOSURE_MARK_MIN_ZOOM, LIKE THE FAR MARK, so below the pin seam a
 * point closure draws nothing: the maintainer's call of 2026-09-08 (#1292)
 * keeps point marks off the far zooms, and a point has no run to knock out
 * of a trail there. NO MAXZOOM: the far mark gives way to a chain along its
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
 *  closureTapeGround and closureInk). */
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
    }),
    buildClosurePointLayer(
      CLUB_CLOSURE_SOURCE_ID,
      ground,
      ink,
      CLUB_CLOSURE_LAYER_ID,
      CLUB_CLOSURE_POINT_FILTER,
    ),
  ]
}
