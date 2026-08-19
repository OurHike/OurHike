import { describe, it, expect } from 'vitest'
import {
  buildLineDetail,
  THROUGH_ROUTE_SOURCES,
  type TappedLineFacts,
} from './lineDetail'
import { PRIMARY_TRAIL_SOURCES } from '../map/style'
import type { SpurRecord } from './spurDestination'
import type { StoredPoi } from './trailData'

// What the line-detail sheet says (#134), decided as strings so the
// decisions are testable without a canvas. The fixture spur is the one
// SPUR_TRAILS.md §3 sketches: blue-blazed, 0.2 mi to Rocky Run Shelter,
// joining the AT at mi 1,043.2.

const ROCKY_RUN: StoredPoi = {
  id: 'atc_shelters:rocky-run',
  type: 'shelter',
  name: 'Rocky Run Shelter',
  lat: 39.4,
  lon: -77.6,
  confidence: 'high',
}

const SPUR_LINE: TappedLineFacts = {
  id: 'side_trails:abc',
  source: 'side_trails',
  name: 'Rocky Run Spur Trail',
  blazeColor: 'Blue',
}

function spur(overrides: Partial<SpurRecord> = {}): Record<string, SpurRecord> {
  return {
    'side_trails:abc': {
      name: 'Rocky Run Spur Trail',
      length_ft: 1056, // 0.2 mi
      destination_poi_id: 'atc_shelters:rocky-run',
      destination_distance_m: 1,
      junction_mile: 1043.2,
      ...overrides,
    },
  }
}

describe('a spur', () => {
  it('says everything SPUR_TRAILS.md sketches, in its words', () => {
    const detail = buildLineDetail(SPUR_LINE, spur(), [ROCKY_RUN])

    expect(detail.heading).toBe('Blue blaze · spur')
    expect(detail.name).toBe('Rocky Run Spur Trail')
    expect(detail.destinationLine).toBe('To Rocky Run Shelter — 0.2 mi each way')
    expect(detail.roundTripLine).toMatch(/there and back$/)
    expect(detail.junctionLine).toBe('Joins the AT at mi 1,043.2')
    expect(detail.sourceLine).toBe(
      'From the Appalachian Trail Conservancy’s side trails data.',
    )
  })

  it('shows the distance alone when no destination resolved - never "Unknown destination"', () => {
    const detail = buildLineDetail(
      SPUR_LINE,
      spur({ destination_poi_id: null, destination_distance_m: null }),
      [ROCKY_RUN],
    )

    expect(detail.destinationLine).toBe('0.2 mi each way')
  })

  it('does not name a destination this phone cannot resolve to a name', () => {
    // A release skew case: the spur record points at a POI id the stored
    // POIs do not hold. "To atc_shelters:rocky-run" would be worse than the
    // distance alone.
    const detail = buildLineDetail(SPUR_LINE, spur(), [])

    expect(detail.destinationLine).toBe('0.2 mi each way')
  })

  it('leaves the destination unnamed when the match is not confident', () => {
    // describeSpur's own 50 m bar: a wrongly-named destination sends
    // someone downhill expecting water that is somewhere else.
    const detail = buildLineDetail(SPUR_LINE, spur({ destination_distance_m: 140 }), [
      ROCKY_RUN,
    ])

    expect(detail.destinationLine).toBe('0.2 mi each way')
  })

  it('omits the junction line when the pipeline published null', () => {
    // Null means the spur's two ends could not be told apart (#136), and a
    // sheet must not guess a mile the pipeline refused to.
    const detail = buildLineDetail(SPUR_LINE, spur({ junction_mile: null }), [ROCKY_RUN])

    expect(detail.junctionLine).toBeNull()
  })

  it('omits the junction line for a release that predates the field', () => {
    const detail = buildLineDetail(SPUR_LINE, spur({ junction_mile: undefined }), [
      ROCKY_RUN,
    ])

    expect(detail.junctionLine).toBeNull()
  })

  it('states the numbers on a long spur as readily as a short one', () => {
    // No length threshold at either end: the 4.53 mi outlier is a nine-mile
    // round trip, which is precisely the case a hiker most needs told.
    const detail = buildLineDetail(SPUR_LINE, spur({ length_ft: 23_918 }), [ROCKY_RUN])

    expect(detail.destinationLine).toBe('To Rocky Run Shelter — 4.5 mi each way')
    expect(detail.roundTripLine).toMatch(/there and back$/)
  })
})

describe('every other line', () => {
  it('names the through-route as the trail it is', () => {
    const detail = buildLineDetail(
      { id: 'centerline:chain:0', source: 'centerline', name: null, blazeColor: 'White' },
      {},
      [],
    )

    expect(detail.heading).toBe('White blaze · Appalachian Trail')
    expect(detail.name).toBeNull()
    expect(detail.destinationLine).toBeNull()
    expect(detail.sourceLine).toBe(
      'From the Appalachian Trail Conservancy’s trail centerline.',
    )
  })

  it('calls a side trail with no spur record a side trail', () => {
    // Access approaches and alternate routes are real side trails ATC
    // classifies as something other than a spur - and a spur record can
    // also simply be missing on an old release.
    const detail = buildLineDetail(
      {
        id: 'side_trails:xyz',
        source: 'side_trails',
        name: 'Approach Trail',
        blazeColor: 'Blue',
      },
      {},
      [],
    )

    expect(detail.heading).toBe('Blue blaze · side trail')
    expect(detail.name).toBe('Approach Trail')
  })

  it('says plainly when the blaze is unknown, and keeps unblazed apart from it', () => {
    // WIREFRAMES.md §3: "says plainly when it's unknown". The pipeline's
    // "None" is CONFIRMED unblazed while "Unknown" failed to decode -
    // different claims, and flattening them would assert something nobody
    // checked.
    const facts = (blazeColor: string | null): TappedLineFacts => ({
      id: 'side_trails:xyz',
      source: 'side_trails',
      name: null,
      blazeColor,
    })

    expect(buildLineDetail(facts('Unknown'), {}, []).heading).toBe(
      'Blaze not recorded · side trail',
    )
    expect(buildLineDetail(facts(null), {}, []).heading).toBe(
      'Blaze not recorded · side trail',
    )
    expect(buildLineDetail(facts('None'), {}, []).heading).toBe('Unblazed · side trail')
    expect(buildLineDetail(facts('Other'), {}, []).heading).toBe(
      'Other blaze · side trail',
    )
  })

  it('shows a future source id raw rather than nothing', () => {
    // The same call chrome/poiSources.ts makes: a raw id is a poor label
    // and still tells someone more than silence.
    const detail = buildLineDetail(
      { id: 'long_path:1', source: 'long_path', name: 'Long Path', blazeColor: 'Blue' },
      {},
      [],
    )

    expect(detail.sourceLine).toBe('From long_path.')
  })

  it('keeps its through-route list pinned to the map style’s', () => {
    // Restated rather than imported so lib/ stays free of the map layer -
    // which only holds if the two lists cannot drift apart silently.
    expect(THROUGH_ROUTE_SOURCES).toEqual(PRIMARY_TRAIL_SOURCES)
  })
})
