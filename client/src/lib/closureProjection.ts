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
