// When the frame on screen is the one the map will keep showing (#1538, #1696).
//
// Two modules read the map back through `queryRenderedFeatures`, which answers
// for the LAST RENDERED FRAME: lib/useDrawnPoiCounts.ts (how many waypoints
// are drawn) and map/trailsInView.ts (which trails are drawn, and where each
// through-route's badge goes). Both have to measure once the map has settled,
// and never per frame mid-pan.
//
// "SETTLED" USED TO MEAN MapLibre's `idle`, AND `idle` CAN NEVER COME. It
// fires only once every source has every tile, so one basemap tile that fails
// or hangs - a normal event on a trail with one bar - holds it off for as long
// as the map is open, and whatever was measured before the lines and pins drew
// stays on screen. That happened to both readers, one at a time:
//
//  - #1538: the waypoint chip read "0 of 1568 waypoints fit" over about forty
//    pins, with the `osm` source's tiles failing and no `idle` in 30 s.
//  - #1696: the legend's Trails in view block and the through-route badges
//    stayed empty. Traced 2026-09-26 against the UA bucket, Manhattan at z11,
//    with one basemap tile's request left hanging: one measurement at 2.1 s
//    finding no trails, then nothing in 30 s, where the same camera with every
//    tile served found 499 trails at the `idle` 13 s in.
//
// So this counts the map as settled on `idle` OR once it has drawn no frame
// for SETTLE_MS - the question the readers actually ask, answered without
// depending on a tile that may never arrive. One home for the rule, so the
// next reader of rendered features does not learn it a third time.

import type { Map as MapLibreMap } from 'maplibre-gl'

/**
 * How long the map has to go without drawing a frame before the frame on
 * screen counts as settled, in milliseconds.
 *
 * Reasoned rather than measured: MapLibre draws a frame about every 16 ms
 * while anything is moving or fading, and its symbol fade - the one animation
 * that runs after the camera stops, while new pins are placed - is 300 ms by
 * default, so a silence as long as a whole fade is not a gap between frames.
 *
 * @unvalidated on a slow phone. A device drawing a frame every 300 ms or more
 * while still busy would be measured mid-settle; the next quiet spell measures
 * again, so the cost is a reading that is briefly one frame stale, never one
 * that sticks. What would settle it: the longest gap between `render` events
 * during a pan on the slowest phone this app supports.
 */
export const SETTLE_MS = 300

/**
 * Calls `settled` each time the map settles - on `idle`, or after SETTLE_MS
 * without a frame, whichever comes first - and returns a detach.
 *
 * `render` is listened to only to notice when frames stop: each frame pushes
 * the timer back, so a pan is one call after it ends, not one per frame. An
 * `idle` cancels the pending quiet-spell call, because it answers for the
 * same frames and a second call would only measure them twice.
 *
 * Nothing is called up front. A reader that wants an answer before the first
 * settle - the map may already be settled when it attaches - measures once
 * itself.
 */
export function onSettled(map: MapLibreMap, settled: () => void): () => void {
  let quiet: ReturnType<typeof setTimeout> | undefined

  const onRender = () => {
    clearTimeout(quiet)
    quiet = setTimeout(settled, SETTLE_MS)
  }
  const onIdle = () => {
    clearTimeout(quiet)
    settled()
  }

  map.on('render', onRender)
  map.on('idle', onIdle)
  return () => {
    clearTimeout(quiet)
    map.off('render', onRender)
    map.off('idle', onIdle)
  }
}
