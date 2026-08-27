// The shape of the ground along a day hike, on the walk's own mile axis
// (#1045).
//
// WHAT THIS FIXES, AND WHY IT IS NOT "THE RIBBON WAS MISSING"
//
// #1041 shipped the follow screen with no ribbon, deliberately: two scalars
// per edge (`trail_graph_elevation.json`) say how much an edge climbs and
// nothing about WHERE, so a staircase drawn from them is a picture of terrain
// nobody measured, on the band a hiker uses to judge whether they beat the
// dark. #1045 publishes the fourth artifact - a dense sampled profile per
// edge - and this module is the client half: it turns the walk
// lib/dayHikeWalk.ts already flattened into the samples the ribbon draws.
//
// **The x-axis is distance along the hiker's own route**, which is what the
// storyboard asked for and what a day hike has instead of a trail mile: "the
// same numbers, measured from your first step instead of from Springer."
// `WalkStep.beforeMetres` is that axis and it already exists - it is the one
// lib/dayHikeFollow.ts reports `walkedMi` on and lib/dayHikeTurns.ts prices
// turns on, so the rule under this ribbon lands on the same number the header
// above it is printing. A fourth accumulation would have been a fourth chance
// for those to disagree, which is the thing lib/dayHikeWalk.ts exists to
// prevent.
//
// FOUR RULES FROM THE PIPELINE, EACH OF WHICH IS A WRONG PICTURE IF DROPPED
//
// 1. **The sample count comes from the array's own length**, never from
//    dividing `length_m` by 25 m. pipeline/export_network_profile.py measured
//    that 63 of 40,596 edges (0.155%) get a different count that way, because
//    the published length and the walked geometry differ by up to 1.50 m -
//    and those 63 would draw every sample after the first in the wrong place.
//
// 2. **A null is unknown and never zero**, in both of its shapes - a whole
//    entry null (the DEM covers none of that edge) and a null inside an array
//    (one missing sample with its place kept). Either one anywhere on the
//    walk returns null from here and the ribbon does not draw, which is the
//    all-or-nothing rule `ResolvedDayHike.climb` already follows for the same
//    reason: a shape missing a piece reads as the shape of the whole walk.
//
// 3. **Nothing here sums a climb.** This artifact is for drawing; the walk's
//    ± figures come from `trail_graph_elevation.json` through
//    `routeClimb`, which is per-edge by construction. Two screens showing two
//    totals for one walk is worse than either total on its own, and
//    export_network_profile.py measured what the disagreement would be:
//    per-edge summing understates a continuous profile by a median 6.9%
//    (p90 46.9%) on 300 six-mile routes - in the unsafe direction. That
//    measurement is #1120's subject and not this module's.
//
// 4. **A gap between stretches breaks the line rather than sloping across
//    it.** A day hike built from several stretches (#983) has ground between
//    them that OurHike will not route, and `partStart` on the first sample of
//    each later stretch is what stops the drawn line claiming a slope over it.
//    The gap consumes NO x-axis, because `ResolvedDayHike.miles` does not
//    count it either - one axis for the ribbon, the header and the card,
//    rather than a ribbon measuring the walk differently from every figure
//    printed beside it.
//
// WHAT IT DOES NOT DO: decimate. A 6-mile walk at 25 m sampling is about 390
// samples and a 20-mile one about 1,290 - already near one per device pixel on
// a phone, which is the density lib/chartProfile.ts's envelope exists to
// reduce TO. There is nothing to gain by reducing it further and a real
// summit to lose.

import type { ElevationSample } from '../chrome/ElevationRibbon'
import type { WalkStep } from './dayHikeWalk'
import { metresToMiles, type TrailGraph } from './trailGraph'

/**
 * `trail_graph_profile.json` as the client holds it: one array of whole feet
 * per edge, index-aligned with the graph's `edges`, or null for an edge the
 * DEM covers none of.
 *
 * No distances travel with it and none are needed - sample `j` of edge `i`
 * sits at fraction `j / (n - 1)` along that edge, where `n` is the array's own
 * length (rule 1 above).
 */
export type EdgeProfiles = ReadonlyArray<ReadonlyArray<number | null> | null>

/**
 * The elevation at a fraction along one edge, interpolated between the two
 * published samples either side of it.
 *
 * Interpolating is the same trade `ribbonSamples` names and takes: the picture
 * interpolates, the number does not. Nothing downstream of here computes a
 * figure from these samples.
 */
function elevationAt(profile: ReadonlyArray<number>, fraction: number): number {
  const x = fraction * (profile.length - 1)
  const low = Math.max(0, Math.min(profile.length - 1, Math.floor(x)))
  const high = Math.min(profile.length - 1, low + 1)
  const t = x - low
  return profile[low] * (1 - t) + profile[high] * t
}

/** Whether every sample of an edge was measured. See rule 2. */
function fullyMeasured(
  profile: ReadonlyArray<number | null>,
): profile is ReadonlyArray<number> {
  return profile.every((sample) => typeof sample === 'number')
}

/**
 * The walk's profile in the shape the ribbon draws, or null when this phone
 * cannot draw it honestly.
 *
 * Null covers three states with one answer, because the answer a hiker gets is
 * the same for all three and it is the right one: no profile artifact on this
 * phone, an edge of the walk the DEM never covered, and a walk that flattened
 * to nothing. #1041's "no ribbon at all" is the honest state, and it stays the
 * honest state wherever this returns null.
 */
export function walkProfile(
  graph: TrailGraph,
  steps: readonly WalkStep[],
  profiles: EdgeProfiles,
): ElevationSample[] | null {
  const samples: ElevationSample[] = []
  let segment: number | null = null

  for (const step of steps) {
    const edge = graph.edges[step.edgeIndex]
    const profile = profiles[step.edgeIndex]
    if (edge === undefined || profile === undefined || profile === null) return null
    if (!fullyMeasured(profile)) return null

    // A published array of one sample is a degenerate edge with no length to
    // draw across - `build_trail_graph.py` only drops zero-length loops
    // shorter than its node grid, so the shape stays expressible even though
    // none exist on the live artifact (0 of 40,596, measured 2026-08-27).
    // Skipped rather than divided by `n - 1`.
    if (profile.length < 2) continue

    const from = step.startFraction
    const to = step.endFraction
    const forward = to >= from

    // The first sample of a later STRETCH breaks the line; see rule 4. The
    // first sample of the walk never does - there is nothing before it for a
    // break to separate it from.
    const opensStretch = segment !== null && step.segment !== segment
    segment = step.segment

    const push = (fraction: number, metres: number, breaks: boolean) => {
      samples.push({
        mile: metresToMiles(step.beforeMetres + metres),
        elevationFt: elevationAt(profile, fraction),
        ...(breaks ? { partStart: true } : {}),
      })
    }

    push(from, 0, opensStretch)

    // Every published sample strictly inside the traversal, in walking order.
    // `edge.length_m` rather than the polyline's own length, because
    // `step.metres` is priced from the same figure - one axis, so the last
    // sample of a traversal lands exactly on `beforeMetres + metres`.
    const last = profile.length - 1
    const step0 = forward ? 1 : -1
    const firstIndex = forward ? Math.floor(from * last) + 1 : Math.ceil(from * last) - 1
    for (
      let j = firstIndex;
      j >= 0 && j <= last && (forward ? j / last < to : j / last > to);
      j += step0
    ) {
      const fraction = j / last
      push(fraction, Math.abs(fraction - from) * edge.length_m, false)
    }

    push(to, step.metres, false)
  }

  // One sample is a dot and none is a blank ribbon reading as "no terrain
  // here", which is a claim. The same floor lib/ribbonView.ts holds.
  return samples.length < 2 ? null : samples
}
