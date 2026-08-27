// The shape of the ground along a day hike (#1045).
//
// TWO ASSERTIONS HERE CARRY THE SAFETY OF THE WHOLE MODULE, and both are
// pipeline measurements rather than opinions:
//
//   - the sample count comes from the published array's OWN length, never
//     from `length_m / 25`. 63 of 40,596 live edges (0.155%) disagree, and
//     each of those would draw every sample after the first in the wrong
//     place;
//   - a null anywhere on the walk means no ribbon, never a zero and never a
//     shape with a piece missing. A shape missing a piece reads as the shape
//     of the whole walk, on the band a hiker uses to judge daylight.

import { describe, expect, it } from 'vitest'

import { resolveDayHike } from './dayHikeCard'
import { dayHikeWalk } from './dayHikeWalk'
import { NETWORK, WEST_END, EAST_END, hikeThrough } from './dayHikeWalk.fixtures'
import type { DayHike } from './dayHikes'
import { buildGraphIndex, metresToMiles } from './trailGraph'
import { walkProfile, type EdgeProfiles } from './walkProfile'

/** Edge 0 climbs west to east, edge 1 descends - so a walk straight through
 *  the junction is one hill with its top at the junction, and any test that
 *  read an edge backwards produces a visibly different shape. */
const PROFILES: EdgeProfiles = [
  [1000, 1100, 1200, 1300, 1400],
  [1400, 1300, 1200, 1100, 1000],
  [900, 950, 1000],
  [900, 950, 1000],
]

function samplesFor(
  hike: DayHike = hikeThrough([WEST_END, EAST_END]),
  profiles = PROFILES,
) {
  const index = buildGraphIndex(NETWORK)
  const resolved = resolveDayHike(index, hike)
  expect(resolved).not.toBeNull()
  return walkProfile(index.graph, dayHikeWalk(index, resolved!), profiles)
}

describe('the walk on its own axis', () => {
  it('starts at mile zero and ends at the walk’s own length', () => {
    // Not at Springer, and not at the A.T. mile the hiker happens to be near:
    // "the same numbers, measured from your first step".
    const samples = samplesFor()!

    expect(samples[0].mile).toBe(0)
    expect(samples[samples.length - 1].mile).toBeCloseTo(metresToMiles(1672), 6)
  })

  it('draws the hill the two edges make, in walking order', () => {
    const samples = samplesFor()!

    expect(samples.map((sample) => sample.elevationFt)).toEqual([
      1000, 1100, 1200, 1300, 1400, 1400, 1300, 1200, 1100, 1000,
    ])
  })

  it('reads an edge backwards when it is walked backwards', () => {
    // An out-and-back covers edge 1 twice, the second time against its
    // published direction. A module that ignored `forward` would draw the
    // hiker climbing on the way home.
    const samples = samplesFor(hikeThrough([WEST_END, EAST_END, WEST_END]))!
    const feet = samples.map((sample) => sample.elevationFt)
    const out = feet.slice(0, feet.length / 2)
    const home = feet.slice(feet.length / 2)

    // The way home is the way out, backwards - which is what the ground is.
    expect(home).toEqual([...out].reverse())
    expect(out).toEqual([1000, 1100, 1200, 1300, 1400, 1400, 1300, 1200, 1100, 1000])
  })
})

describe('where each sample sits', () => {
  it('takes the sample count from the array, never from the edge length', () => {
    // THE LOAD-BEARING ONE. Edge 0 is 836 m; a consumer dividing by the 25 m
    // sampling interval would expect 34 samples and space these three 25 m
    // apart. They are 418 m apart, because the array's own length says so.
    const samples = samplesFor(hikeThrough([WEST_END, EAST_END]), [
      [1000, 1200, 1400],
      [1400, 1300, 1200, 1100, 1000],
      null,
      null,
    ])!

    expect(samples[1].mile).toBeCloseTo(metresToMiles(418), 6)
    expect(samples[1].elevationFt).toBe(1200)
  })

  it('trims the first and last edges at the taps, and interpolates the ends', () => {
    // Half of edge 0 and half of edge 1: 836 m, and an end elevation that
    // falls between two published samples rather than snapping to one.
    const half = samplesFor(
      hikeThrough([
        [-74.095, 41.25],
        [-74.085, 41.25],
      ]),
    )!

    expect(half[0].elevationFt).toBeCloseTo(1200, 6)
    expect(half[half.length - 1].mile).toBeCloseTo(metresToMiles(836), 6)
    expect(half[half.length - 1].elevationFt).toBeCloseTo(1200, 6)
  })
})

describe('what it refuses to draw', () => {
  it('returns null when an edge of the walk was never measured', () => {
    expect(
      samplesFor(hikeThrough([WEST_END, EAST_END]), [PROFILES[0], null, null, null]),
    ).toBeNull()
  })

  it('returns null for one missing sample inside an edge', () => {
    // A null INSIDE an array is a hole in the DEM with its place on the axis
    // kept. Reading it as zero would draw a walk that drops to sea level and
    // climbs back out of it.
    expect(
      samplesFor(hikeThrough([WEST_END, EAST_END]), [
        [1000, null, 1200, 1300, 1400],
        PROFILES[1],
        null,
        null,
      ]),
    ).toBeNull()
  })

  it('returns null when there is no profile artifact at all', () => {
    expect(
      samplesFor(hikeThrough([WEST_END, EAST_END]), [null, null, null, null]),
    ).toBeNull()
  })
})

describe('a walk with a gap in it (#983)', () => {
  const TWO_STRETCHES: DayHike = {
    ...hikeThrough([WEST_END, EAST_END]),
    segments: [
      [
        { coord: WEST_END, poiId: null },
        { coord: EAST_END, poiId: null },
      ],
      [
        { coord: [-74.09, 41.255], poiId: null },
        { coord: [-74.09, 41.26], poiId: null },
      ],
    ],
  }

  it('breaks the line at the stretch boundary and nowhere else', () => {
    // The break says "OurHike will not claim to know this ground". A junction
    // INSIDE a stretch is not a break: this ribbon prices nothing, so the
    // step an endpoint weld leaves is a step in a drawing rather than
    // climbing in a total - and marking all 23-odd junctions of a real route
    // would render the ribbon as dots.
    const samples = samplesFor(TWO_STRETCHES)!
    const breaks = samples.filter((sample) => sample.partStart === true)

    expect(breaks).toHaveLength(1)
    expect(breaks[0].elevationFt).toBeCloseTo(950, 6)
    expect(samples[0].partStart).toBeUndefined()
  })

  it('gives the gap no width on the axis, because no figure counts it either', () => {
    // `ResolvedDayHike.miles` sums walked trail and leaves the gap out. A
    // ribbon that measured the walk differently from the header above it
    // would put the rule on the wrong ground.
    const samples = samplesFor(TWO_STRETCHES)!
    const at = samples.findIndex((sample) => sample.partStart === true)

    expect(samples[at].mile).toBeCloseTo(samples[at - 1].mile, 6)
  })
})
