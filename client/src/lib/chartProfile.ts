// The desktop elevation chart's view of the published profile (#135).
//
// The ribbon draws a 10-mile window of ~640 samples and can hand them
// straight to an SVG path. The chart's resting domain is the whole trail -
// ~141,000 samples for ~1,200 device pixels - and a path with a hundred
// samples per pixel is not a rendering cost problem so much as an honesty
// problem: the browser rasterises them into a column of overdrawn strokes,
// and what survives visually is an accident of paint order.
//
// So the chart decimates, and the method is the decision worth writing down:
// **a min-max envelope per pixel bucket, never an average.** Each bucket
// keeps its lowest and highest sample, in the order they occur, so a summit
// or a notch inside a bucket survives at its true elevation. Averaging would
// shave every peak by an amount that grows exactly where terrain is most
// dramatic - the chart would be smoothest where the ground is roughest,
// which is the confidently-wrong direction (FEATURES.md: accuracy is the
// whole point).
//
// DEM gaps (NaN) are dropped from the drawing here, the same trade
// lib/elevationProfile.ts's ribbonSamples makes and documents: the picture
// interpolates, the number does not. Every figure the chart prints goes
// through lib/route.ts's legFigures, where the gaps and the part seams still
// break the runs.

import type { ElevationProfile } from './elevationProfile'
import type { ElevationSample } from '../chrome/ElevationRibbon'

/** The stretch of trail the chart is currently showing. */
export interface ChartDomain {
  startMile: number
  endMile: number
}

/** Buckets for a chart drawn ~1,200px wide: close to one bucket per device
 *  pixel, and two emitted points per bucket keeps every extreme while the
 *  path stays ~2,400 points - cheap to build and cheap to draw. */
export const ENVELOPE_BUCKETS = 1200

/** The narrowest domain a zoom can reach, in miles. At 2 miles a ~1,200px
 *  chart draws the 25 m samples about seven pixels apart - past that there
 *  is no more data to reveal, only interpolation stretched wider. */
export const MIN_DOMAIN_SPAN_MI = 2

/** The whole profile as a domain, or null when it holds no samples. */
export function fullDomain(profile: ElevationProfile): ChartDomain | null {
  if (profile.distanceMi.length === 0) return null
  return {
    startMile: profile.distanceMi[0],
    endMile: profile.distanceMi[profile.distanceMi.length - 1],
  }
}

/**
 * A requested domain, kept inside the profile and above the minimum span.
 *
 * Widening happens around the request's centre, then the whole window slides
 * back inside the profile - the same slide-don't-shrink behaviour
 * ribbonWindow() has at the terminuses, so zooming right up to Katahdin
 * pins the window against the end rather than past it.
 */
export function clampDomain(
  requested: ChartDomain,
  profile: ElevationProfile,
): ChartDomain | null {
  const full = fullDomain(profile)
  if (full === null) return null

  const fullSpan = full.endMile - full.startMile
  let low = Math.min(requested.startMile, requested.endMile)
  let high = Math.max(requested.startMile, requested.endMile)

  if (fullSpan <= MIN_DOMAIN_SPAN_MI) return full

  if (high - low < MIN_DOMAIN_SPAN_MI) {
    const centre = (low + high) / 2
    low = centre - MIN_DOMAIN_SPAN_MI / 2
    high = centre + MIN_DOMAIN_SPAN_MI / 2
  }

  if (low < full.startMile) {
    high += full.startMile - low
    low = full.startMile
  }
  if (high > full.endMile) {
    low -= high - full.endMile
    high = full.endMile
    if (low < full.startMile) low = full.startMile
  }

  return { startMile: low, endMile: high }
}

/** Index of the first sample at or past `mile` - the same binary search
 *  lib/elevationProfile.ts uses, restated here because it is not exported
 *  and the two files answer different questions with it. */
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
 * The domain's samples decimated to a min-max envelope, ready to draw.
 *
 * Each bucket contributes its minimum and its maximum sample in the order
 * they occur along the trail (one point where they coincide), so the drawn
 * line passes through every local extreme at its real elevation. Buckets an
 * entire DEM gap wide contribute nothing and the line joins across them -
 * ribbonSamples' documented trade, kept identical here.
 *
 * When the domain holds fewer samples than two per bucket the samples are
 * returned as they are: there is nothing to decimate, and a zoomed-in chart
 * should draw the real measurements rather than an envelope of them.
 */
export function envelopeSamples(
  profile: ElevationProfile,
  domain: ChartDomain,
  buckets = ENVELOPE_BUCKETS,
): ElevationSample[] {
  const { distanceMi, elevationFt } = profile
  const first = firstIndexAtOrAfter(distanceMi, domain.startMile)
  const span = domain.endMile - domain.startMile
  if (span <= 0) return []

  let last = first
  while (last < distanceMi.length && distanceMi[last] <= domain.endMile) last += 1

  if (last - first <= buckets * 2) {
    const samples: ElevationSample[] = []
    for (let i = first; i < last; i += 1) {
      const ft = elevationFt[i]
      if (!Number.isNaN(ft)) samples.push({ mile: distanceMi[i], elevationFt: ft })
    }
    return samples
  }

  const samples: ElevationSample[] = []
  let bucket = -1
  let minIdx = -1
  let maxIdx = -1

  const flush = () => {
    if (minIdx === -1) return
    const a = Math.min(minIdx, maxIdx)
    const b = Math.max(minIdx, maxIdx)
    samples.push({ mile: distanceMi[a], elevationFt: elevationFt[a] })
    if (b !== a) samples.push({ mile: distanceMi[b], elevationFt: elevationFt[b] })
  }

  for (let i = first; i < last; i += 1) {
    const ft = elevationFt[i]
    if (Number.isNaN(ft)) continue

    const k = Math.min(
      buckets - 1,
      Math.floor(((distanceMi[i] - domain.startMile) / span) * buckets),
    )
    if (k !== bucket) {
      flush()
      bucket = k
      minIdx = i
      maxIdx = i
      continue
    }
    if (ft < elevationFt[minIdx]) minIdx = i
    if (ft > elevationFt[maxIdx]) maxIdx = i
  }
  flush()

  return samples
}

/**
 * The nearest sample's own mile, gaps included - for snapping a selection
 * endpoint onto the axis the figures are computed over. A dragged endpoint
 * lands between samples (and floating point puts even a clean-looking drag a
 * hair off the sample it prints as), so an unsnapped range can exclude the
 * boundary sample its own label claims to start at. Snapping makes the
 * printed range and the measured range the same range, at the profile's own
 * resolution - which is the only resolution the claim honestly has.
 */
export function nearestMile(profile: ElevationProfile, mile: number): number | null {
  const { distanceMi } = profile
  if (distanceMi.length === 0) return null

  const after = firstIndexAtOrAfter(distanceMi, mile)
  if (after >= distanceMi.length) return distanceMi[distanceMi.length - 1]
  if (after === 0) return distanceMi[0]
  return distanceMi[after] - mile < mile - distanceMi[after - 1]
    ? distanceMi[after]
    : distanceMi[after - 1]
}

/**
 * The sample nearest `mile`, for the hover readout - or null when the domain
 * is empty or the nearest sample is a DEM gap. A gap answers null rather
 * than the nearest measured neighbour: the readout claims "the ground at
 * this mile is at N feet", and the honest answer over a gap is no answer.
 */
export function sampleAtMile(
  profile: ElevationProfile,
  mile: number,
): ElevationSample | null {
  const { distanceMi, elevationFt } = profile
  if (distanceMi.length === 0) return null

  const after = firstIndexAtOrAfter(distanceMi, mile)
  const before = after - 1

  let best = -1
  if (after >= distanceMi.length) best = before
  else if (before < 0) best = after
  else best = distanceMi[after] - mile < mile - distanceMi[before] ? after : before

  const ft = elevationFt[best]
  if (Number.isNaN(ft)) return null
  return { mile: distanceMi[best], elevationFt: ft }
}

/** A tick step that yields 4-8 labelled ticks: 1/2/5 × 10^k of the span. */
export function tickStep(span: number): number {
  if (span <= 0) return 1
  const rough = span / 6
  const power = Math.pow(10, Math.floor(Math.log10(rough)))
  for (const step of [1, 2, 5, 10]) {
    if (rough <= step * power) return step * power
  }
  return 10 * power
}

/** The tick positions inside [from, to] at `step` intervals, on round
 *  multiples of the step. */
export function ticks(from: number, to: number, step: number): number[] {
  const out: number[] = []
  const first = Math.ceil(from / step) * step
  // Float steps accumulate error; counting an index keeps mile 2,000 from
  // printing as 1,999.9999999.
  for (let i = 0; ; i += 1) {
    const value = first + i * step
    if (value > to + step / 1e6) break
    out.push(Number(value.toFixed(6)))
  }
  return out
}
