// The zoom at which the pins that are being dropped would actually fit (#528).
//
// The legend saying "38 of 112 waypoints fit at this zoom" is half a feature: it
// tells a hiker they are not being shown everything and leaves them to find the
// zoom that fixes it by pinching and checking. The number that fixes it is
// computable, so this computes it and the control does it.
//
// WHY THIS AND NOT FANNING THE HIDDEN PINS OUT. Displacing them - spiderfy, a
// jiggle, leader lines - recovers the count and draws every displaced pin at a
// position it is not at. features/POI_SITES.md refuses that explicitly, and the
// reason it gives is the one that governs this whole app: "This app refuses to
// draw a stale GPS fix like a live one; drawing a privy 80 px from where it is,
// is the same refusal." Moving the CAMERA reaches the same pins at their real
// coordinates, which is the same remedy without the lie.
//
// THE ARITHMETIC, and it is checkable against features/POI_SITES.md's own table.
// MapLibre uses 512 px tiles, so at zoom z a pixel is
// 78271.517 * cos(latitude) / 2^z metres. At z14 and latitude 40 that is 3.66
// m/px against the doc's measured 3.7, and 42 px of collision box is 154 m
// against its measured 154 m.

import type { MapPoint } from './legendContents'

/**
 * How close two pin centres may be before MapLibre drops one.
 *
 * `POI_PIN_SIZE` (38) plus `icon-padding` (2) on each side, read from the two
 * places that own those numbers rather than restated - a collision distance that
 * drifted from the layer's real padding would compute a zoom that does not
 * actually fit anything.
 */
export const POI_COLLISION_PX = 42

/** Metres per pixel at zoom 0 on the equator, for 512 px tiles - which is what
 *  MapLibre uses, and the reason this is half the figure a 256 px-tile formula
 *  gives. */
const METRES_PER_PIXEL_AT_Z0 = 78_271.517

/** Never past this, whatever the arithmetic asks for. Two waypoints ATC recorded
 *  at the same coordinates never separate at any zoom, and chasing them would
 *  fling the camera to street level for a pair that cannot be helped.
 *  POI_SITES.md's placement table stops at 17 for the same reason. */
export const MAX_FIT_ZOOM = 17

/** And never more than this in one press. A jump of six levels is a different
 *  place rather than a closer look - the hiker loses the stretch they were
 *  reading. Pressing again goes further, and the counts say whether it is
 *  worth it. */
export const MAX_FIT_STEP = 4

/** How far apart pin centres are, in metres, at the moment they stop
 *  colliding. */
export function collisionMetres(zoom: number, latitude: number): number {
  const metresPerPixel =
    (METRES_PER_PIXEL_AT_Z0 * Math.cos((latitude * Math.PI) / 180)) / 2 ** zoom
  return POI_COLLISION_PX * metresPerPixel
}

/** Equirectangular, like pipeline/lib/spurs.py's - accurate to well under a
 *  percent at the distances that decide a collision, and cos() at the midpoint
 *  keeps a degree of longitude honest across the trail's latitude span. */
function metresBetween(a: MapPoint, b: MapPoint): number {
  const meanLat = (((a.lat + b.lat) / 2) * Math.PI) / 180
  const dy = (b.lat - a.lat) * 111_320
  const dx = (b.lon - a.lon) * 111_320 * Math.cos(meanLat)
  return Math.hypot(dx, dy)
}

/**
 * For each point, how far away its nearest neighbour is.
 *
 * O(n²), which is nothing here: a viewport holds ~70-90 waypoints on the
 * measured corridor and this runs when a button is pressed, not per frame.
 */
function nearestNeighbourMetres(points: readonly MapPoint[]): number[] {
  return points.map((point, index) => {
    let nearest = Infinity
    for (let other = 0; other < points.length; other += 1) {
      if (other === index) continue
      const metres = metresBetween(point, points[other])
      if (metres < nearest) nearest = metres
    }
    return nearest
  })
}

/**
 * The zoom to go to so that most of what is currently colliding fits, or null
 * where there is nothing to fix.
 *
 * Null in three cases, and each means the control should not be offered: fewer
 * than two points, nothing crowded at this zoom, and already at the ceiling.
 * A button that would not move the camera is worse than no button.
 *
 * WHICH CROWDED PIN IT AIMS AT. Not the worst one: two waypoints a metre apart
 * would demand z22 and take the whole viewport with them. It targets the 25th
 * percentile of the crowded pins' nearest-neighbour distances, so roughly three
 * quarters of them separate - a closer look that recovers most of what was
 * missing, rather than a teleport that recovers all of it.
 *
 * The remainder is not hidden by this: the counts recompute on the next settled
 * frame, so whatever still does not fit still says so, and pressing again goes
 * further.
 */
export function zoomToFit(
  points: readonly MapPoint[],
  currentZoom: number,
  latitude: number,
): number | null {
  if (points.length < 2) return null
  if (currentZoom >= MAX_FIT_ZOOM) return null

  const collision = collisionMetres(currentZoom, latitude)
  const crowded = nearestNeighbourMetres(points)
    .filter((metres) => Number.isFinite(metres) && metres < collision)
    .sort((first, second) => first - second)
  if (crowded.length === 0) return null

  // The distance three quarters of the crowded pins are at least as far apart
  // as. Guarded against a zero: two points at identical coordinates give 0, and
  // no zoom separates them - fall through to the step cap rather than dividing
  // by it.
  const target = crowded[Math.floor(crowded.length * 0.25)]
  const needed =
    target > 0
      ? Math.log2(
          (POI_COLLISION_PX *
            METRES_PER_PIXEL_AT_Z0 *
            Math.cos((latitude * Math.PI) / 180)) /
            target,
        )
      : Infinity

  const wanted = Number.isFinite(needed) ? Math.ceil(needed) : currentZoom + MAX_FIT_STEP
  return Math.min(
    Math.max(wanted, currentZoom + 1),
    currentZoom + MAX_FIT_STEP,
    MAX_FIT_ZOOM,
  )
}
