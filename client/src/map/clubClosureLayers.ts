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
// one cross. ATC's closures are not in the file: ATC's own band draws them
// (map/atcUpdateLayers.ts).
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
import {
  buildClosureLayers,
  CLOSURE_CROSS_ICON_ID,
  CLOSURE_MARK_HALO_WIDTH,
  CLOSURE_MARK_MIN_ZOOM,
  CLOSURE_MARK_SIZE,
  closurePointId,
} from '../lib/closureStyle'
import { CLUB_CLOSURE_LAYER_ID } from './styleIds'

export const CLUB_CLOSURE_SOURCE_ID = 'club-closures'

/** The lines a closure is crossed out along: a line closure's own, and the
 *  trail stretches cut inside an area. A GeoJSON source's features reach a
 *  filter as tile features, whose `geometry-type` is LineString for a
 *  MultiLineString too (maplibre-gl-style-spec 26's EvaluationContext reads
 *  the tile's numeric type), so one test takes both. */
export const CLUB_CLOSURE_LINE_FILTER: unknown[] = ['==', ['geometry-type'], 'LineString']

/** The points, each drawn as one cross. */
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
 * One cross at each point closure (the maintainer's S6: "a point one ✕"):
 * lib/closureStyle.ts's far mark - its image, size, ink and paper halo -
 * placed at the point, with the id `closurePointId` gives.
 *
 * FROM CLOSURE_MARK_MIN_ZOOM, LIKE THE FAR MARK, so below the pin seam a
 * point closure draws nothing: the maintainer's call of 2026-09-08 (#1292)
 * keeps point marks off the far zooms, and a point has no run to knock out
 * of a trail there. NO MAXZOOM: the far mark gives way to a chain along its
 * line, and a point has no line for a chain.
 *
 * ALWAYS DRAWN, where the far mark collides (lib/closureStyle.ts's
 * CLOSURE_MARK_PADDING): the far mark drops the extra candidates of one
 * closed network, while this cross is a closure's only mark, so dropping it
 * for a label would draw a closed bridge as open. It still holds its place
 * (`icon-ignore-placement` is left false), so a waypoint pin under it falls
 * back to its dot, the standing the far mark already has.
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
