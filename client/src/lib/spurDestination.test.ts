// Tests for spurDestination.ts.
//
// Why this exists
// ---------------
// The pipeline resolves a spur's destination out to a loose 150 m and
// publishes how far the match actually was. Whether that is good enough to
// *name* is decided here, and the two failure modes are not symmetrical:
//
//   - not naming a real destination leaves a hiker exactly where they were
//     before this feature existed;
//   - naming the wrong one sends someone down a hill expecting water that is
//     somewhere else.
//
// So the tests below lean hard on the second: an unjudgeable match, a
// too-distant match and a missing distance all have to come back unnamed.

import { describe, expect, it } from 'vitest'

import { describeSpur, NAME_DESTINATION_WITHIN_M } from './spurDestination'

const spur = (over: Partial<Parameters<typeof describeSpur>[0]> = {}) => ({
  name: 'Rocky Run Shelter Trail',
  length_ft: 1056, // 0.2 mi
  destination_poi_id: 'shelter:rocky-run',
  destination_distance_m: 1,
  ...over,
})

describe('naming a destination', () => {
  it('names one the spur ends on', () => {
    // Half of all real spurs end within a metre of their destination.
    expect(describeSpur(spur()).destinationPoiId).toBe('shelter:rocky-run')
  })

  it('names one just inside the threshold', () => {
    expect(
      describeSpur(spur({ destination_distance_m: NAME_DESTINATION_WITHIN_M }))
        .destinationPoiId,
    ).toBe('shelter:rocky-run')
  })

  it('declines to name one just outside it', () => {
    expect(
      describeSpur(spur({ destination_distance_m: NAME_DESTINATION_WITHIN_M + 1 }))
        .destinationPoiId,
    ).toBeNull()
  })

  it('declines to name a match whose distance is missing', () => {
    // An unjudgeable match is not a confident one. Naming it anyway would mean
    // trusting a link precisely where the evidence for it went missing.
    expect(
      describeSpur(spur({ destination_distance_m: null })).destinationPoiId,
    ).toBeNull()
  })

  it('declines to name a match whose distance is not a number', () => {
    expect(
      describeSpur(spur({ destination_distance_m: NaN })).destinationPoiId,
    ).toBeNull()
  })

  it('says nothing at all when the pipeline resolved nothing', () => {
    // ~12% of spurs lead somewhere unmapped. Not "Unknown destination", which
    // reads as a data error rather than the ordinary situation it is.
    const detail = describeSpur(
      spur({ destination_poi_id: null, destination_distance_m: null }),
    )

    expect(detail.destinationPoiId).toBeNull()
    // The rest of the sheet still has something to show.
    expect(detail.distanceLabel).not.toBeNull()
  })

  it('lets the threshold be raised without a re-export', () => {
    // The whole reason the distance is published rather than thresholded away
    // in the pipeline: 150 m captures 88% of spurs, 50 m captures 77% with far
    // higher confidence, and the call is not settled.
    const distant = spur({ destination_distance_m: 140 })

    expect(describeSpur(distant).destinationPoiId).toBeNull()
    expect(describeSpur(distant, 150).destinationPoiId).toBe('shelter:rocky-run')
  })
})

describe('distance and the round trip', () => {
  it('states the one-way distance in miles', () => {
    expect(describeSpur(spur()).distanceLabel).toBe('0.2 mi each way')
  })

  it('keeps two decimals on a spur under a tenth of a mile', () => {
    // The median spur is 385 ft. One decimal would round it to "0.0 mi" and
    // say nothing at all - and the median is exactly the case that has to work.
    expect(describeSpur(spur({ length_ft: 385 })).distanceLabel).toBe('0.07 mi each way')
  })

  it('states a round trip, which is the decision being made', () => {
    // The walk back up is the part that hurts, and spurs to water tend to go
    // down. Doubling is the point.
    expect(describeSpur(spur()).roundTripLabel).toMatch(/there and back$/)
  })

  it('gives the longest real spur a round trip that reflects nine miles', () => {
    // 4.53 mi reads as a pleasant detour until it is stated as nine miles
    // there and back. This is precisely the case a hiker most needs told, and
    // the one a length threshold would have suppressed.
    const longest = describeSpur(spur({ length_ft: 4.53 * 5280 }))

    expect(longest.distanceLabel).toBe('4.5 mi each way')
    expect(longest.roundTripLabel).toMatch(/^≈[12]?\dh/)
  })

  it('states distance on a tiny spur as readily as a long one', () => {
    // No length threshold at either end: suppressing the numbers on short
    // spurs saves nothing and makes the sheet inconsistent.
    expect(describeSpur(spur({ length_ft: 100 })).distanceLabel).not.toBeNull()
  })
})

describe('facts that are independently missing', () => {
  it('shows a destination even when ATC published no length', () => {
    const detail = describeSpur(spur({ length_ft: null }))

    expect(detail.destinationPoiId).toBe('shelter:rocky-run')
    expect(detail.distanceLabel).toBeNull()
    expect(detail.roundTripLabel).toBeNull()
  })

  it('treats a zero length as no length published', () => {
    // Zero is a real value in the raw data and is not a distance anyone can
    // walk. "0.00 mi each way" would read as a spur you are standing at the
    // end of.
    expect(describeSpur(spur({ length_ft: 0 })).distanceLabel).toBeNull()
  })

  it('treats a negative length as no length published', () => {
    expect(describeSpur(spur({ length_ft: -5 })).distanceLabel).toBeNull()
  })

  it('has an answer for a trail with no spur record at all', () => {
    // Tapping a white-blazed line, or a spur from a data release older than
    // this feature. Neither is an error.
    for (const missing of [undefined, null]) {
      const detail = describeSpur(missing)
      expect(detail.destinationPoiId).toBeNull()
      expect(detail.distanceLabel).toBeNull()
      expect(detail.roundTripLabel).toBeNull()
    }
  })
})
