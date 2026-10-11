// React binding for map/drawnPois.ts, so the legend can say how many of the
// waypoints in view are actually drawn (#528).
//
// A hook rather than a read in the render, for the reason the issue names:
// `queryRenderedFeatures` reflects the LAST RENDERED FRAME, so the count has to
// be taken when the map has settled - never on `move`, where it would be a
// query per frame for a number nobody can read yet.
//
// The one-frame lag behind a fling is fine for a count, and is also why #528
// stops at counting rather than trying to route anyone anywhere.
//
// "SETTLED" USED TO MEAN `idle` ALONE, AND `idle` CAN NEVER COME (#1538).
// MapLibre fires it only once every source has loaded every tile, and one
// basemap tile that fails or stalls - a normal event on a trail with one bar -
// holds it off for as long as the map is open. The chip then kept the count
// taken up front, which on a cold start is taken before the waypoint source
// has loaded or a pin has been drawn: zero. Traced 2026-09-26 against the UA
// bucket, Manhattan at z11, on a build logging every measurement: one
// measurement at 1.8 s reading 0 with the style not yet loaded, then about
// forty pins drawn, every source loaded by 13 s except `osm`, whose tile
// fetches kept failing, no `idle` in 30 s, and the chip reading "0 of 1568
// waypoints fit" throughout.
//
// So two things changed:
//
//  - The map counts as settled when it has drawn no frame for SETTLE_MS, as
//    well as on `idle`. That rule lives in map/settle.ts now, shared with
//    map/trailsInView.ts, which had the same stuck reading (#1696).
//  - A count is only published when it could be true: the pin layer is in the
//    style, the waypoint source has loaded, and the pin artwork is
//    registered. Before that the answer is unmeasured, which shows no chip,
//    rather than zero, which says the map is hiding everything.

import { useEffect, useState } from 'react'
import { drawnPoiCounts, type DrawnPoiMap } from '../map/drawnPois'
import { drawsNearbyTrails } from '../map/drawnBlazes'
import { CHOSEN_SYSTEM_SOURCES } from '../map/nearbyTrails'
import { POI_LAYER_ID, POI_PIN_MIN_ZOOM, POI_SOURCE_ID } from '../map/poiIds'
import { poiIconId } from '../map/poiIcons'
import { onSettled } from '../map/settle'

/** Any one pin image, as the sign that pin artwork has arrived at all: the
 *  pins are registered together in one pass (poiLayers.ts's attachPoiIcons),
 *  so one being present means all are. */
const ANY_PIN = poiIconId('water', 'high')

/**
 * Whether a count taken now could be true.
 *
 * The pin layer must be in the style, the waypoint source must have loaded
 * the tiles for this view, and the pin artwork must be registered - a pin
 * whose image has not arrived is not drawn, and counting it as not drawn
 * would be the false zero again by another route.
 */
function canCount(map: IdleMap): boolean {
  if (map.getLayer(POI_LAYER_ID) === undefined) return false
  // Asked before `isSourceLoaded`, which throws for a source the style does
  // not hold.
  if (map.getSource(POI_SOURCE_ID) === undefined) return false
  if (!map.isSourceLoaded(POI_SOURCE_ID)) return false
  return map.hasImage(ANY_PIN)
}

/** The real MapLibre map - see map/drawnPois.ts for why this is not a
 *  structural stand-in. */
export type IdleMap = DrawnPoiMap

export interface DrawnPois {
  /**
   * Drawn waypoints per type, or undefined until a settled frame on which the
   * waypoints could be drawn at all (see canCount).
   *
   * Undefined rather than empty on purpose: an empty map means "measured, and
   * none of these were drawn", which the legend renders as `0 shown`. Claiming
   * that before anything has been measured would be a drop that has not
   * happened - #1538 is what that claim looks like on screen.
   */
  counts: ReadonlyMap<string, number> | undefined
  /** Whether the settled camera is below the zoom the pin layer draws at, so
   *  the panel can say which of two very different things is true. */
  belowPoiZoom: boolean
  /**
   * Whether any line on screen belongs to a network other than the chosen
   * trail's (#783), which is what the legend's ghosting sentence explains.
   *
   * Measured on the same settled frame as the counts above, for the reason
   * that governs everything this hook returns: they answer for ONE settled
   * frame, and a second listener would let the legend show waypoint counts
   * from this camera beside a ghosting sentence decided at the last one.
   */
  ghostedTrailsDrawn: boolean
}

export function useDrawnPoiCounts(
  map: IdleMap | null,
  /** The taken trail's sources (#1306): what "another network's" is
   *  relative to. Empty - nothing taken - and no line is ghosted. */
  chosen: readonly string[] = CHOSEN_SYSTEM_SOURCES,
): DrawnPois {
  const [drawn, setDrawn] = useState<DrawnPois>({
    counts: undefined,
    belowPoiZoom: false,
    ghostedTrailsDrawn: false,
  })

  useEffect(() => {
    if (map === null) {
      // Back to unmeasured, not to zero. A map being torn down is not a map
      // drawing nothing.
      setDrawn({
        counts: undefined,
        belowPoiZoom: false,
        ghostedTrailsDrawn: false,
      })
      return
    }

    // Everything below is one settled frame, so the waypoint counts and the
    // ghosting sentence always describe the same camera. Only the counts wait
    // for the waypoints to be countable; the zoom and the lines on screen are
    // true whatever the waypoint source is doing.
    const measure = () =>
      setDrawn({
        counts: canCount(map) ? drawnPoiCounts(map) : undefined,
        belowPoiZoom: map.getZoom() < POI_PIN_MIN_ZOOM,
        ghostedTrailsDrawn: drawsNearbyTrails(map, chosen),
      })

    // Once up front: the map may already be settled by the time this runs,
    // and waiting for the next frame would leave the panel unmeasured until
    // the hiker happened to move.
    measure()
    return onSettled(map, measure)
  }, [map, chosen])

  return drawn
}
