// Where the pointer is over a route being built, on a laptop (the
// maintainer's review of #1374: the design's step 2 draws "Hovering ·
// Reeves Meadow → Tuxedo station · 6.4 mi · ≈3 h 20" beside the pointer over
// the map, and the maintainer asked for it on a laptop only). The plate that
// prints it is chrome/RouteHover.tsx; this is the hook that says where.
//
// POINTER-FINE ONLY, AND ONLY WHILE A ROUTE IS DRAWN. A touch has no hover,
// so the hook does nothing where the pointer is coarse, and a phone with a
// mouse plugged in gets it, which is the honest reading of "on a laptop".
// Null the moment the pointer leaves the line, leaves the canvas, or the
// builder closes - so a plate never outlives the route it names.
//
// The hit test is a small box round the pointer rather than the point: a
// route line is four to six px wide and a pointer on its edge should still
// count as on it. Six px each way is a guess at "on the line" for a mouse,
// @unvalidated against anybody's hand; what would settle it is a laptop
// tester saying the plate flickers as the pointer runs along the route.

import { useEffect, useState } from 'react'
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import {
  DAY_HIKE_CASING_LAYER_ID,
  DAY_HIKE_OUTER_CASING_LAYER_ID,
} from '../map/dayHikeLayers'

export const ROUTE_HOVER_LAYER_IDS: readonly string[] = [
  DAY_HIKE_CASING_LAYER_ID,
  DAY_HIKE_OUTER_CASING_LAYER_ID,
]

const HIT_SLOP_PX = 6

export interface HoverPoint {
  x: number
  y: number
}

function pointerIsFine(): boolean {
  try {
    return window.matchMedia('(pointer: fine)').matches
  } catch {
    return false
  }
}

export function useRouteHover(
  map: MapLibreMap | null,
  enabled: boolean,
): HoverPoint | null {
  const [at, setAt] = useState<HoverPoint | null>(null)
  const active = map !== null && enabled

  useEffect(() => {
    if (!active || !pointerIsFine()) return
    const move = (event: MapMouseEvent) => {
      const layers = ROUTE_HOVER_LAYER_IDS.filter((id) => map.getLayer(id) !== undefined)
      if (layers.length === 0) {
        setAt(null)
        return
      }
      const { x, y } = event.point
      const hits = map.queryRenderedFeatures(
        [
          [x - HIT_SLOP_PX, y - HIT_SLOP_PX],
          [x + HIT_SLOP_PX, y + HIT_SLOP_PX],
        ],
        { layers },
      )
      setAt(hits.length > 0 ? { x, y } : null)
    }
    const leave = () => setAt(null)
    map.on('mousemove', move)
    map.on('mouseout', leave)
    return () => {
      map.off('mousemove', move)
      map.off('mouseout', leave)
      setAt(null)
    }
  }, [map, active])

  // Derived rather than reset in the effect: a plate for a builder that has
  // closed is gone on the same render, not one later.
  return active ? at : null
}
