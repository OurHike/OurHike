// Where the pin images come from, and which thread pays for them.
//
// WHAT THIS COSTS, AND WHERE IT WAS BEING PAID
//
// `buildPoiIcons()` rasterises 46 images - every published POI type in both
// confidences, plus the 28 site variants - by sub-sampling each pixel and
// counting polygon crossings for the glyph inside it. features/POI_SITES.md
// §6 records it as "a few hundred milliseconds on the main thread", measured
// on CI hardware. On a phone it is not a few hundred milliseconds: measured
// 2026-08-20 in Chromium at 390x844 on a 4x CPU throttle, replaying first run
// with the release already on the phone, it was 2,521 ms of main-thread self
// time - in a run whose longest single task was 2,374 ms.
//
// That work landed while the three entry steps were up, which is the one
// moment the app is asking somebody to tap three times (#857). None of it
// reaches a pixel there - the steps cover the map and the map has no waypoints
// on it yet - and all of it is in front of the Skip button.
//
// SO IT MOVES OFF THE UI THREAD
//
// There is nothing in the rasteriser but arithmetic: no DOM, no canvas, no
// map. It is the same shape of work map/demWorker.ts already does elsewhere
// in this directory, and the same capability check guards it - a worker where
// there is one, the plain call where there is not (contours.ts's
// `workerAvailable`).
//
// The fallback is not a browser story. MapLibre GL parses every tile in a
// worker and draws nothing at all without one (map/mapWorker.ts's header is
// the account of what that looks like), so a browser reaching this file with
// no `Worker` is not a browser this app can draw a map for. The synchronous
// path is for jsdom, where the suite runs and a real worker cannot - and
// map/MapView.tsx holds the other half of that promise: it asks for nothing
// until there is a waypoint to draw, so even where the fallback runs it does
// not run during first run.
//
// What it bought, same phone and same profile: the 2,521 ms became 79 ms (the
// serious-warning pin, which goes through the same rasteriser on its own
// clock), the longest task in the run fell from 2,374 ms to 434 ms, and the
// three taps were answered in 11, 4 and 220 ms.

import { buildPoiIcons, type RegisteredPoiIcon } from './poiIcons'

/**
 * Built once per page, whoever asks.
 *
 * The promise rather than the images, so that two maps attaching in the same
 * tick share one build instead of starting two workers - the same reason
 * `buildPoiIcons` caches its array, one thread further out.
 */
let building: Promise<readonly RegisteredPoiIcon[]> | undefined

/** jsdom has no Worker, and neither does a browser old enough that MapLibre
 *  cannot draw for it either. Asked as a capability rather than assumed. */
function workerAvailable(): boolean {
  return typeof Worker !== 'undefined'
}

function buildInWorker(): Promise<readonly RegisteredPoiIcon[]> {
  return new Promise((resolve) => {
    let worker: Worker
    try {
      worker = new Worker(new URL('./poiIconWorker.ts', import.meta.url), {
        type: 'module',
      })
    } catch {
      // A worker that cannot be constructed at all - a Content-Security-Policy
      // that refuses one, an asset that did not ship. The images still have to
      // exist: a map with no pin artwork draws no waypoints, and a hiker
      // looking for water is the reason that would matter.
      resolve(buildPoiIcons())
      return
    }

    // Not for the promise's sake - a second resolve is already a no-op - but
    // for what the argument to it would cost. `resolve(buildPoiIcons())` runs
    // the whole rasteriser before the call, so an error arriving after a good
    // reply would spend the seconds on the main thread that this file exists
    // to avoid, and throw the result away.
    let settled = false

    worker.onmessage = (event: MessageEvent) => {
      settled = true
      worker.terminate()
      resolve(event.data as readonly RegisteredPoiIcon[])
    }
    // Same argument as the catch above, one failure mode later: a worker that
    // fails to load or throws on its way through has to end with pins on the
    // map, not with an empty legend nobody can explain.
    worker.onerror = () => {
      if (settled) return
      settled = true
      worker.terminate()
      resolve(buildPoiIcons())
    }
    worker.postMessage('build')
  })
}

/**
 * Every pin the style can ask for.
 *
 * Always a promise, including on the synchronous path, so callers have one
 * shape to write against rather than two - see map/poiLayers.ts's
 * attachPoiIcons, which is the only caller.
 */
export function poiIconImages(): Promise<readonly RegisteredPoiIcon[]> {
  building ??= workerAvailable()
    ? buildInWorker()
    : Promise.resolve<readonly RegisteredPoiIcon[]>(buildPoiIcons())

  return building
}
