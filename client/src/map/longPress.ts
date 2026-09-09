// Press and hold a spot on the map (#1137).
//
// The third way into a report, and the only one that can name a place the app
// has no name for: a blow-down at a nameless bend, a washed-out tread two
// miles past the last shelter, the mile somebody cleared forty blow-downs out
// of. Today's foot anchors on the hiker's own fix and a place's card anchors
// on that place; neither reaches a point between them.
//
// WHY THIS IS NOT `contextmenu`, which is the one-line version of this file
// and was rejected rather than overlooked. MapLibre does forward the browser's
// `contextmenu`, and on a desktop right-click it is exactly right. On touch it
// is not dependable: whether a long press raises `contextmenu` at all is a
// browser decision, iOS Safari's is entangled with its own text-selection and
// callout behaviour, and the ones that do raise it also want the native menu
// suppressed. A gesture this app owns is one it can also explain, test, and
// keep the same on every phone.
//
// THE ONE-INTERPRETER RULE, AND HOW THIS FILE KEEPS IT. routeLayers.ts states
// it: one touch, one meaning. The trap here is that a press and a pan and a
// pinch all start with exactly the same event, and only time and movement
// tell them apart afterwards. So this file does not try to win the touch -
// **it yields.** `movestart` is MapLibre saying "this touch was a drag or a
// zoom, I am acting on it", and it cancels the press outright. The built-in
// handlers are never suspended and `preventDefault` is never called; a hiker
// dragging the map never has to fight a plate for it.

import type { Map as MapLibreMap, MapMouseEvent, MapTouchEvent } from 'maplibre-gl'

/** A screen position, in the canvas pixels `queryRenderedFeatures` wants. */
export interface PressPoint {
  x: number
  y: number
}

/** Where the press landed. */
export interface PressAt {
  lat: number
  lon: number
}

/**
 * How long a finger has to stay down.
 *
 * @unvalidated - picked, not measured. 500 ms is what Android's own long-press
 * and iOS's callout both use, so it is the interval a phone has already taught
 * this hiker; that is a reason to match it and not evidence that it is right
 * for somebody in gloves on a cold ridge. What would settle it is field use
 * (#105, #106) reporting presses that fired late or not at all.
 */
export const LONG_PRESS_MS = 500

/**
 * How far the finger may drift and still count as held.
 *
 * Larger than poiTaps.ts's 3 px tap slop, deliberately: that number is about
 * which pin you meant, and a wobble of three pixels changes the answer. This
 * one is about whether you moved AT ALL over half a second, and a hand holding
 * a phone at arm's length does not sit inside three pixels for that long.
 *
 * It is a floor rather than the whole guard. Real dragging is caught by
 * `movestart` below, which fires as soon as MapLibre decides the touch is a
 * pan - so this only has to cover the drift too small for MapLibre to call a
 * drag at all.
 */
export const LONG_PRESS_SLOP_PX = 10

/**
 * Wires press-and-hold to `onLongPress`, and returns a detach function.
 *
 * Fires ON THE TIMER, while the finger is still down, rather than on release.
 * That is what a hiker has been taught to expect everywhere else - the thing
 * appears under your thumb and lifting it does nothing - and it is also the
 * safer half: a press that only resolved on release would leave somebody
 * holding a finger on the map with no idea whether anything was happening.
 *
 * WHAT ABOUT THE CLICK THAT FOLLOWS. Lifting the finger still produces a
 * `click`, which `attachPoiTaps` would read as "select whatever is here" and
 * `attachLineTaps` as "open this trail's facts". This file does not try to
 * swallow it, because a module cannot honestly suppress another module's
 * listener - MapView.tsx detaches those handlers while the plate is open,
 * the same suppression it already does for route mode, and by the time a
 * finger held for half a second lifts, that render has long since happened.
 */
export function attachLongPress(
  map: MapLibreMap,
  onLongPress: (at: PressAt, point: PressPoint) => void,
): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null
  let from: PressPoint | null = null

  const cancel = () => {
    if (timer !== null) clearTimeout(timer)
    timer = null
    from = null
  }

  const begin = (event: MapMouseEvent | MapTouchEvent) => {
    // A second finger is a pinch, whatever the first one was doing. Cancelled
    // rather than ignored: the press that was already running is no longer
    // what this touch means.
    if ('points' in event && event.points.length > 1) {
      cancel()
      return
    }
    cancel()
    from = { x: event.point.x, y: event.point.y }
    const at = { lat: event.lngLat.lat, lon: event.lngLat.lng }
    const point = { x: event.point.x, y: event.point.y }
    timer = setTimeout(() => {
      timer = null
      from = null
      onLongPress(at, point)
    }, LONG_PRESS_MS)
  }

  const drift = (event: MapMouseEvent | MapTouchEvent) => {
    if (from === null) return
    const dx = event.point.x - from.x
    const dy = event.point.y - from.y
    if (Math.hypot(dx, dy) > LONG_PRESS_SLOP_PX) cancel()
  }

  map.on('mousedown', begin)
  map.on('touchstart', begin)
  map.on('mousemove', drift)
  map.on('touchmove', drift)
  map.on('mouseup', cancel)
  map.on('touchend', cancel)
  map.on('touchcancel', cancel)
  // MapLibre acting on the touch itself - a drag, a pinch, a double-tap zoom.
  // The whole of this file's deference to the built-in handlers is this line.
  map.on('movestart', cancel)

  return () => {
    cancel()
    map.off('mousedown', begin)
    map.off('touchstart', begin)
    map.off('mousemove', drift)
    map.off('touchmove', drift)
    map.off('mouseup', cancel)
    map.off('touchend', cancel)
    map.off('touchcancel', cancel)
    map.off('movestart', cancel)
  }
}
