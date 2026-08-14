// Cumulative ascent over a window of the elevation profile.
//
// The same algorithm as pipeline/lib/elevation_gain.py, deliberately, and
// with the same threshold. That module's docstring carries the full
// reasoning; the short version is that summing every rise in the 25 m profile
// over-counts the full AT by ~17% (594,520 ft against a ~510,000 ft
// consensus), because summing is the operation that turns DEM measurement
// error into signal. Half a metre of jitter per sample across ~141,000
// samples is tens of thousands of feet.
//
// It exists twice because it is asked two different questions. The pipeline
// asks once, about the whole trail, and could publish the answer. The app
// asks about "the climb ahead" - an arbitrary window that moves as a hiker
// walks - which no precomputed total can answer.
//
// Two implementations of one number is a drift risk, so both are pinned to
// one table of vectors - pipeline/reference/gain_vectors.json, read by this
// module's test and by test_lib_elevation_gain.py. A change made in one
// language and not the other fails a test rather than going unnoticed.
//
// The number matters beyond display: it feeds naismith.ts, so an inflated
// gain becomes an inflated hiking time. Over-stating is the safer direction
// to be wrong in and is still wrong.

export const METERS_PER_FOOT = 0.3048

/** How far the ground must reverse before a turning point is believed.
 *  6x the DEM's sample-to-sample error, and the conventional dead band for
 *  DEM-derived gain. See pipeline/lib/elevation_gain.py. */
export const THRESHOLD_M = 3.0
export const THRESHOLD_FT = THRESHOLD_M / METERS_PER_FOOT

export interface ProfileSample {
  distanceMi: number
  elevationFt: number | null
  /** First sample of a centerline piece, so the step INTO it is a seam in the
   *  trail rather than a slope. See cumulativeGainOverProfile. */
  partStart?: boolean
}

/**
 * Total confirmed ascent over one unbroken run of samples.
 *
 * Tracks the running high and low since the last confirmed turning point. A
 * climb is banked only once the ground has come back down by `threshold` - at
 * which point the whole trough-to-peak rise is added at its true size.
 *
 * That last part is the subtle half. The obvious implementation carries a
 * running reference and adds whenever it moves past the threshold, which
 * quietly loses up to one threshold at the top of every climb - an error in
 * the opposite direction, and just as large across enough reversals.
 */
export function cumulativeGain(elevations: number[], threshold = THRESHOLD_FT): number {
  if (elevations.length < 2) return 0

  let gain = 0
  let low = elevations[0]
  let high = elevations[0]
  let rising: boolean | null = null

  for (const value of elevations.slice(1)) {
    if (rising === true) {
      if (value > high) {
        high = value
      } else if (value <= high - threshold) {
        // The ground turned over by more than the DEM can invent, so the
        // peak was real. Bank the whole climb.
        gain += high - low
        low = value
        rising = false
      }
    } else if (rising === false) {
      if (value < low) {
        low = value
      } else if (value >= low + threshold) {
        high = value
        rising = true
      }
    } else {
      // Direction not established: the profile has not moved far enough from
      // where it started to say which way it is going. Both extremes are
      // tracked so that when it does break out, the climb is measured from
      // the true trough rather than from wherever the window happened to
      // begin.
      if (value > high) high = value
      if (value < low) low = value
      if (high - low >= threshold) rising = value >= high
    }
  }

  // A climb still in progress when the samples ran out. Unconfirmed, but
  // discarding a real ascent because the window ended at the top of it is the
  // worse answer.
  if (rising) gain += high - low

  return gain
}

/**
 * Total confirmed ascent across samples that may contain DEM coverage gaps.
 *
 * A null elevation is a real gap, kept in the profile so a chart's distance
 * axis stays continuous. Skipping over it silently would join two samples
 * that may be miles and hundreds of feet apart into a single step, and count
 * that step as a climb nobody made - so each unbroken run is measured on its
 * own and the runs are added.
 */
export function cumulativeGainOverGaps(
  elevations: (number | null)[],
  threshold = THRESHOLD_FT,
): number {
  let total = 0
  let run: number[] = []
  for (const value of elevations) {
    if (value === null || value === undefined || Number.isNaN(value)) {
      total += cumulativeGain(run, threshold)
      run = []
    } else {
      run.push(value)
    }
  }
  return total + cumulativeGain(run, threshold)
}

/**
 * Total confirmed ascent over a profile, breaking at DEM gaps AND at
 * centerline part boundaries.
 *
 * Two things end a run, and they are different in kind. A null elevation is a
 * hole in the DEM - the trail is continuous, the measurement is not. A
 * `partStart` is the reverse: the measurement is fine and the TRAIL is not
 * continuous. The pipeline walks 558 disconnected centerline pieces and
 * carries the distance axis straight across the space between them, so the
 * step from the last sample of one piece into the first of the next is not a
 * slope anybody walks. Summing it added ~36,800 ft of phantom climb to the
 * published total, the largest single "step" +2,588 ft across 25 m of ground.
 *
 * A profile with no `partStart` anywhere is read as one run - the correct
 * reading of an artifact published before the pipeline recorded seams, since
 * that file genuinely does not say where they are.
 */
export function cumulativeGainOverProfile(
  samples: ProfileSample[],
  threshold = THRESHOLD_FT,
): number {
  let total = 0
  let run: number[] = []
  for (const sample of samples) {
    if (sample.partStart && run.length > 0) {
      total += cumulativeGain(run, threshold)
      run = []
    }
    const value = sample.elevationFt
    if (value === null || value === undefined || Number.isNaN(value)) {
      total += cumulativeGain(run, threshold)
      run = []
    } else {
      run.push(value)
    }
  }
  return total + cumulativeGain(run, threshold)
}

/**
 * Confirmed ascent between two mileposts, in feet. Bounds are inclusive.
 *
 * A window too short to hold two samples has no gain rather than throwing: on
 * a 25 m profile, asking about the next tenth of a mile is a reasonable
 * question that happens to select one sample.
 *
 * The window keeps whole samples rather than bare elevations, because
 * `partStart` has to survive the slice: a window spanning a seam that dropped
 * the marker would sum the jump across it as a climb, which is the thing this
 * exists to stop.
 */
export function gainBetween(
  profile: ProfileSample[],
  startMi: number,
  endMi: number,
  threshold = THRESHOLD_FT,
): number {
  const window = profile.filter((s) => s.distanceMi >= startMi && s.distanceMi <= endMi)
  return cumulativeGainOverProfile(window, threshold)
}

/** Every rise summed, noise included - what a zero threshold gives.
 *  Named rather than left implicit because it is the number being replaced,
 *  and the comparison is the argument. */
export function rawCumulativeGain(elevations: (number | null)[]): number {
  return cumulativeGainOverGaps(elevations, 0)
}
