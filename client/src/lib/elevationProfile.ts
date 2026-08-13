// The published elevation profile, and the slice of it the ribbon draws.
//
// See features/ELEVATION_PROFILE.md for the two decisions this file encodes -
// the window length and why it is asymmetric - and for the measurements behind
// the storage shape.
//
// STORAGE. The corridor profile is ~141,000 samples. Held as an array of
// {distanceMi, elevationFt} objects that is 7-10 MB of resident heap on a phone
// that is already running a WebGL map; held as two parallel Float32Arrays it is
// 1.1 MB. The compact form costs nothing in precision - float32 resolves 0.2 m
// at mile 2,190, well under the 25 m sample spacing - and nothing in special
// cases either, because a DEM coverage gap becomes NaN, which
// cumulativeGainOverGaps already treats as a break in the run.
//
// The two sample shapes below are not redundant. ProfileSample (distanceMi,
// nullable) is what lib/elevationGain.ts counts ascent over and keeps gaps.
// ElevationSample (mile, non-null) is what the SVG draws and cannot hold a gap:
// ElevationRibbon takes Math.min of the elevations, and one NaN there turns the
// entire path into NaN and renders nothing at all.

import type { HikeDirection } from '../chrome/Header'
import type { ElevationSample } from '../chrome/ElevationRibbon'
import type { ProfileSample } from './elevationGain'

/** Parallel arrays, ascending by distance. `elevationFt[i]` is NaN where the
 *  DEM did not cover `distanceMi[i]`.
 *
 *  `partStart[i]` is 1 where sample i begins a new centerline piece, so the
 *  step into it is a seam in the trail rather than a slope (#559). A third
 *  parallel array rather than a wider object, for the same reason as the other
 *  two: a Uint8Array over ~141,000 samples is 141 KB, against the megabyte a
 *  per-sample boolean field would add to the object form this shape exists to
 *  avoid.
 *
 *  **Optional, and that is a storage fact rather than laziness.** This shape is
 *  persisted (lib/storedShapes.fixtures.ts' `storedElevation`), so a profile
 *  read back off a phone that downloaded before this field existed genuinely
 *  does not have it. Requiring it would type a lie and throw on the archive of
 *  every early tester. Absent reads as "no seams known", which is the same
 *  honest degradation the artifact itself gets. */
export interface ElevationProfile {
  distanceMi: Float32Array
  elevationFt: Float32Array
  partStart?: Uint8Array
}

export interface MileWindow {
  startMile: number
  endMile: number
}

/** How much trail the ribbon and the lanes cover. */
export const WINDOW_SPAN_MI = 10

/** How much of that span sits behind the hiker once the direction is known.
 *  Not zero: the "you are here" rule needs somewhere to be, and against the
 *  left edge it indicates nothing. */
export const WINDOW_BEHIND_MI = 1

interface RawSample {
  distance_mi?: unknown
  elevation_ft?: unknown
  part_start?: unknown
}

/**
 * The published `elevation_profile.json` as parallel arrays, or null if it is
 * not the array of samples this expects.
 *
 * Returning null rather than throwing on a malformed body is the same call
 * refreshTrailData() makes about a truncated trails.geojson: the ribbon is a
 * decoration on a screen whose job is showing a hiker where they are, and it
 * should cost itself rather than the map when its data arrives broken.
 */
export function parseProfile(text: string): ElevationProfile | null {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    return null
  }
  if (!Array.isArray(parsed)) return null

  const distanceMi = new Float32Array(parsed.length)
  const elevationFt = new Float32Array(parsed.length)
  const partStart = new Uint8Array(parsed.length)
  let count = 0

  for (const entry of parsed as RawSample[]) {
    // A sample with no distance cannot be placed on the axis at all, so it is
    // dropped. A sample with no elevation is a real DEM gap and is kept as NaN
    // - dropping those would join two samples that may be a mile apart into one
    // step and count that step as a climb nobody made.
    if (typeof entry?.distance_mi !== 'number' || !Number.isFinite(entry.distance_mi)) {
      continue
    }
    distanceMi[count] = entry.distance_mi
    elevationFt[count] =
      typeof entry.elevation_ft === 'number' ? entry.elevation_ft : Number.NaN
    // Absent on every sample but the 558 that begin a piece, and absent
    // throughout a profile published before the pipeline recorded seams -
    // which reads as "no seams known", the only honest reading of a file that
    // does not say.
    partStart[count] = entry.part_start === true ? 1 : 0
    count += 1
  }

  if (count === 0) return null

  return {
    distanceMi: distanceMi.subarray(0, count),
    elevationFt: elevationFt.subarray(0, count),
    partStart: partStart.subarray(0, count),
  }
}

/** Index of the first sample at or past `mile`, or the length if there is
 *  none. Binary search rather than arithmetic on the 25 m spacing: the spacing
 *  is a property of how the pipeline happens to sample today, not a promise the
 *  artifact makes. */
function firstIndexAtOrAfter(distanceMi: Float32Array, mile: number): number {
  let low = 0
  let high = distanceMi.length

  while (low < high) {
    const mid = (low + high) >>> 1
    if (distanceMi[mid] < mile) low = mid + 1
    else high = mid
  }

  return low
}

/**
 * The stretch of trail the ribbon draws around a hiker at `atMile`.
 *
 * Asymmetric once the direction is known - nine miles ahead, one behind, and
 * mirrored for a southbounder. Centred until then, because lib/hikeDirection.ts
 * withholds the direction for the first quarter mile of movement and guessing
 * NOBO would be a confident-looking answer that is wrong for half of everyone.
 *
 * Near a terminus the window slides rather than shrinks, so the ribbon keeps
 * its full span and the "you are here" rule walks to the edge - which is what
 * is happening on the ground.
 */
export function ribbonWindow(
  profile: ElevationProfile,
  atMile: number,
  direction?: HikeDirection,
): MileWindow {
  const first = profile.distanceMi[0]
  const last = profile.distanceMi[profile.distanceMi.length - 1]

  // A profile shorter than the window is drawn whole. Sliding a 10-mile window
  // inside 4 miles of trail has no answer that is not just "all of it".
  if (last - first <= WINDOW_SPAN_MI) return { startMile: first, endMile: last }

  const behind =
    direction === undefined
      ? WINDOW_SPAN_MI / 2
      : direction === 'NOBO'
        ? WINDOW_BEHIND_MI
        : WINDOW_SPAN_MI - WINDOW_BEHIND_MI

  let startMile = atMile - behind
  if (startMile < first) startMile = first
  if (startMile + WINDOW_SPAN_MI > last) startMile = last - WINDOW_SPAN_MI

  return { startMile, endMile: startMile + WINDOW_SPAN_MI }
}

/** The window's samples in the shape lib/elevationGain.ts counts over, gaps
 *  included. Bounds are inclusive, matching gainBetween(). */
export function profileSamples(
  profile: ElevationProfile,
  { startMile, endMile }: MileWindow,
): ProfileSample[] {
  const samples: ProfileSample[] = []

  for (
    let i = firstIndexAtOrAfter(profile.distanceMi, startMile);
    i < profile.distanceMi.length && profile.distanceMi[i] <= endMile;
    i += 1
  ) {
    const elevationFt = profile.elevationFt[i]
    samples.push({
      distanceMi: profile.distanceMi[i],
      elevationFt: Number.isNaN(elevationFt) ? null : elevationFt,
      // Carried into the window, not just held on the whole profile: a
      // 10-mile window that spans a seam is exactly the case that would
      // otherwise report a phantom climb to a hiker looking at the ribbon.
      //
      // Optional-chained because a profile restored from an older download has
      // no such array at all - see ElevationProfile.
      partStart: profile.partStart?.[i] === 1,
    })
  }

  return samples
}

/**
 * The window's samples in the shape the SVG draws, with DEM gaps dropped.
 *
 * Dropping is a real trade and worth naming: the drawn line joins across a gap
 * as though the ground were continuous, which is terrain the DEM never
 * measured. It is done anyway because the alternative is one missing sample
 * blanking a whole ribbon, and because the split is on the right side of the
 * line that matters - the picture interpolates, the number does not.
 * upcomingClimb() and gainBetween() both read profileSamples() above, where the
 * gaps are still there and still break the run.
 */
export function ribbonSamples(
  profile: ElevationProfile,
  window: MileWindow,
): ElevationSample[] {
  const samples: ElevationSample[] = []

  for (const sample of profileSamples(profile, window)) {
    if (sample.elevationFt === null) continue
    samples.push({ mile: sample.distanceMi, elevationFt: sample.elevationFt })
  }

  return samples
}
