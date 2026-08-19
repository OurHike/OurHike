/**
 * Closure miles, re-read against the release this phone is holding (#674).
 *
 * `features/POI_IDENTITY.md`'s "Miles are a projection, not an anchor": a mile
 * is a reading against one particular measurement of the centerline, and the
 * ATC re-measures. The same physical stretch gets a slightly different number,
 * so a closure authored against last year's measurement quietly names a
 * different stretch under this year's. The backend cannot fix this — it holds
 * no centerline geometry (`backend/app/models/report.py` says so for the
 * sibling case) — so the conversion happens here, where the trail index is.
 *
 * This is `seriousWarnings.placeAll`'s rule applied to a line rather than a
 * point, and deliberately the same rule: snap the stored geometry onto the
 * index this phone actually has, and fall back to the stored mile when there
 * is no geometry to snap. A closure is never dropped for failing to project —
 * a closure a hiker cannot see is one they walk into.
 *
 * **`@unvalidated` — the tolerance this inherits was derived for a different
 * question.** `mileOnTrail` accepts any point within `MAX_OFF_TRAIL_MILES`
 * (3) of a centerline vertex and returns that vertex's mile, discarding how
 * far away it was. That 3 is well argued where it lives, but the argument is
 * about *a hiker's GPS fix* and about fitting inside the latitude bucket
 * search — not about re-projecting an endpoint that was itself computed from
 * a centerline and should therefore land within feet of one. Two consequences
 * nobody has measured:
 *
 * - an endpoint 2.9 miles from any vertex projects, and the band is drawn
 *   there with no hint that it moved that far;
 * - where the trail doubles back within three miles — switchbacks, parallel
 *   ridges — the nearest *vertex* can sit on the wrong lobe, so a closure
 *   could be drawn on the stretch beside the closed one.
 *
 * What would settle it: the distribution of `locateOnTrail(...).offTreadFeet`
 * for real closure endpoints projected across two real releases. Until a
 * closure is authored with geometry there is nothing to measure — no client
 * writes it yet — so this is deliberately left as the loose inherited gate
 * rather than tightened to a number picked in advance. `locateOnTrail` already
 * returns that offset, which is where a real threshold, or a note on the sheet
 * saying how far the stretch moved, would come from.
 *
 * **Two consequences of projecting, named rather than left to be discovered.**
 * Neither is acted on here, because both need a decision this change is not
 * the place to take:
 *
 * - `isBroadAdvisory` (`lib/closureSpan.ts`) gates on `end - start` and
 *   decides whether a closure is drawn as a band at all. Projection changes
 *   the span, so a closure sitting near `MAX_BAND_MILES` can cross that line
 *   in either direction as a side effect of being re-projected — the band
 *   appearing or vanishing without the closure itself having changed.
 * - `screens/Moderation.tsx` renders `mi start–end` off `QueuedClosure`,
 *   which this does not touch. So a moderator reads the stored authoring-datum
 *   miles while the map and banner read the projected ones, for the same
 *   closure. That is arguably right — a moderator is judging what the reporter
 *   filed — but it is a divergence somebody should decide on rather than meet.
 */

import { mileOnTrail, type TrailIndex } from './trailPosition'

/** The fields this needs. Optional as well as nullable — see below. */
export interface ProjectableClosure {
  start_mile_marker: number
  end_mile_marker: number
  start_lat?: number | null
  start_lon?: number | null
  end_lat?: number | null
  end_lon?: number | null
}

/**
 * A number, or nothing usable.
 *
 * Tests for a number rather than against null on purpose. Three absences all
 * mean "no geometry" and only two of them are null: the live API sends null,
 * a baseline baked before these columns existed omits the key entirely so a
 * phone on last month's release reads `undefined`, and a corrupted or
 * hand-edited artifact could carry a string. `typeof` covers all three, where
 * `!== null` would let `undefined` through into `mileOnTrail` and produce a
 * mile from `NaN` coordinates — a number, wrong, and indistinguishable from a
 * real one downstream.
 */
function project(index: TrailIndex, lat: unknown, lon: unknown): number | null {
  if (typeof lat !== 'number' || typeof lon !== 'number') return null
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
  return mileOnTrail(index, { lon, lat })
}

/**
 * One closure's miles against `index`, or the closure unchanged.
 *
 * **All or nothing, and that is the load-bearing decision here.** A closure is
 * a stretch, and its two miles are only comparable when both were read off the
 * same ruler. If one end projects and the other does not — no geometry on that
 * end, or a point `mileOnTrail` refuses because it sits past
 * `MAX_OFF_TRAIL_MILES` — then taking the one that worked would produce a
 * stretch measured half against this release and half against whichever one
 * the closure was authored on. Its length would be the difference between two
 * different rulers, which is not a distance at all. Both stale miles are
 * consistent with each other and wrong by a few hundred feet; a mixed pair can
 * be wrong by the whole drift and looks exactly as trustworthy. So a
 * half-projectable closure keeps the miles it was stored with.
 *
 * Reordered if the projection inverts the pair, for the reason `#257` gives on
 * the backend's own normalisation: `closureBanner` assumes `start <= end` and
 * `warningsOnRoute` normalises, so an inverted pair makes the
 * inside-the-closure test unsatisfiable. Projection should not invert a pair —
 * both ends move a few hundred feet in the same direction — but "should not"
 * is not a guarantee worth a silent banner failure.
 */
export function projectClosure<T extends ProjectableClosure>(
  closure: T,
  index: TrailIndex,
): T {
  const start = project(index, closure.start_lat, closure.start_lon)
  const end = project(index, closure.end_lat, closure.end_lon)
  if (start === null || end === null) return closure

  return {
    ...closure,
    start_mile_marker: Math.min(start, end),
    end_mile_marker: Math.max(start, end),
  }
}

/**
 * Every closure's miles against `index`.
 *
 * Returns the same array when nothing projected, so a caller memoising on
 * identity does not re-render for a no-op — which is every call until a
 * closure is authored with geometry, since no client writes one yet.
 */
export function projectClosures<T extends ProjectableClosure>(
  closures: readonly T[],
  index: TrailIndex,
): readonly T[] {
  let moved = false
  const projected = closures.map((closure) => {
    const next = projectClosure(closure, index)
    if (next !== closure) moved = true
    return next
  })
  return moved ? projected : closures
}
