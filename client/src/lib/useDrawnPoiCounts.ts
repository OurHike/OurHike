// React binding for map/drawnPois.ts, so the legend can say how many of the
// waypoints in view are actually drawn (#528).
//
// A hook rather than a read in the render, for the reason the issue names:
// `queryRenderedFeatures` reflects the LAST RENDERED FRAME, so the count has to
// be taken when the map has settled. It recomputes on `idle` and never on
// `move` - a count recomputed mid-fling is a query per frame for a number
// nobody can read yet, and it would lag anyway.
//
// The one-frame lag behind a fling is fine for a count, and is also why #528
// stops at counting rather than trying to route anyone anywhere.

import { useEffect, useState } from 'react'
import { drawnPoiCounts, type DrawnPoiMap } from '../map/drawnPois'
import { POI_MIN_ZOOM } from '../map/poiLayers'

/** The real MapLibre map - see map/drawnPois.ts for why this is not a
 *  structural stand-in. */
export type IdleMap = DrawnPoiMap

export interface DrawnPois {
  /**
   * Drawn waypoints per `type::confidence`, or undefined before the first
   * settled frame.
   *
   * Undefined rather than empty on purpose: an empty map means "measured, and
   * none of these were drawn", which the legend renders as `0 shown`. Claiming
   * that before anything has been measured would be a drop that has not
   * happened.
   */
  counts: ReadonlyMap<string, number> | undefined
  /** Whether the settled camera is below the zoom the pin layer draws at, so
   *  the panel can say which of two very different things is true. */
  belowPoiZoom: boolean
}

export function useDrawnPoiCounts(map: IdleMap | null): DrawnPois {
  const [drawn, setDrawn] = useState<DrawnPois>({
    counts: undefined,
    belowPoiZoom: false,
  })

  useEffect(() => {
    if (map === null) {
      // Back to unmeasured, not to zero. A map being torn down is not a map
      // drawing nothing.
      setDrawn({ counts: undefined, belowPoiZoom: false })
      return
    }

    const measure = () =>
      setDrawn({
        counts: drawnPoiCounts(map),
        belowPoiZoom: map.getZoom() < POI_MIN_ZOOM,
      })

    // Once up front: the map may already be idle by the time this runs, and
    // waiting for the next `idle` would leave the panel unmeasured until the
    // hiker happened to move.
    measure()
    map.on('idle', measure)
    return () => {
      map.off('idle', measure)
    }
  }, [map])

  return drawn
}
