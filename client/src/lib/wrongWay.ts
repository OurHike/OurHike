// The wrong-way / off-trail alert's pure detection math. See
// features/HIKER_SAFETY.md §5 - the only notification OurHike ever sends,
// deliberately conservative. Two independent detection modes, either one
// alone can trigger: (1) distance from the nearest trail line exceeds a
// threshold (reuses Map Options' snap-to-segment math conceptually - this
// module takes the already-computed distance as an input, it doesn't do
// the geometry itself), (2) a sustained reversed bearing vs. the hike's
// intended direction. A `bearingDeltaDeg` of `null` means "not moving
// enough to have a meaningful bearing" (e.g. standing still at a shelter)
// and must never count toward sustained divergence - that's what makes a
// long dwell silent instead of a false alarm.
//
// IMPORTANT: the three threshold constants below are WIREFRAMES.md UI-
// mockup placeholders, not a validated HIKER_SAFETY.md spec - that doc
// explicitly declines to guess real numbers pending field-testing under
// tree canopy (ROADMAP.md Phase 4, not achievable by writing more code).
// Treat these as configurable, not as ground truth.

export const OFF_TRAIL_THRESHOLD_FT = 90
export const CUE_PERSISTENCE_MS = 12 * 60 * 1000
export const PUSH_PERSISTENCE_MS = 25 * 60 * 1000
const REVERSED_BEARING_THRESHOLD_DEG = 90

export interface WrongWaySample {
  timestampMs: number
  distanceFromTrailFt: number
  /** Degrees of deviation from the hike's intended bearing; null if the
   * hiker isn't moving enough for a bearing to mean anything. */
  bearingDeltaDeg: number | null
}

export type WrongWayAlert = 'silent' | 'cue' | 'push'

function isDiverging(sample: WrongWaySample): boolean {
  const offTrail = sample.distanceFromTrailFt > OFF_TRAIL_THRESHOLD_FT
  const reversed =
    sample.bearingDeltaDeg !== null &&
    sample.bearingDeltaDeg > REVERSED_BEARING_THRESHOLD_DEG
  return offTrail || reversed
}

export function detectWrongWay(trace: WrongWaySample[]): WrongWayAlert {
  let sustainedSinceMs: number | null = null
  let alert: WrongWayAlert = 'silent'

  for (const sample of trace) {
    if (!isDiverging(sample)) {
      sustainedSinceMs = null
      alert = 'silent'
      continue
    }

    if (sustainedSinceMs === null) sustainedSinceMs = sample.timestampMs

    const sustainedMs = sample.timestampMs - sustainedSinceMs
    if (sustainedMs >= PUSH_PERSISTENCE_MS) {
      alert = 'push'
    } else if (sustainedMs >= CUE_PERSISTENCE_MS) {
      alert = 'cue'
    }
  }

  return alert
}
