import { describe, it, expect } from 'vitest'
import {
  buildLineDetail,
  CHOSEN_SYSTEM_SOURCES,
  THROUGH_ROUTE_SOURCES,
  type TappedLineFacts,
  type TrailSourceTable,
} from './lineDetail'
import { PRIMARY_TRAIL_SOURCES } from '../map/style'
import { CHOSEN_SYSTEM_SOURCES as MAP_CHOSEN_SYSTEM_SOURCES } from '../map/nearbyTrails'
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

  it('keeps its chosen-system list pinned to the map’s', () => {
    expect(CHOSEN_SYSTEM_SOURCES).toEqual(MAP_CHOSEN_SYSTEM_SOURCES)
  })
})

// features/NEARBY_TRAILS.md §§2, 3 and 6 - what a line belonging to somebody
// else's network says, and what it refuses to offer (#783).

/** A nearby trail as the network artifact publishes it. */
const NEARBY_LINE: TappedLineFacts = {
  id: 'oprhp_trails:8812',
  source: 'oprhp_trails',
  name: 'Suffern–Bear Mountain Trail',
  blazeColor: 'Yellow',
  lengthMiles: 24,
  park: 'Harriman State Park',
  trailStatus: 'Open',
}

/** The published attribution for that source, verbatim from
 *  pipeline/sources.json's `oprhp_trails` record. */
const SOURCES: TrailSourceTable = {
  oprhp_trails: {
    attribution: 'New York State Office of Parks, Recreation and Historic Preservation',
    edited: '2026-08-04T12:00:00Z',
  },
}

describe('a nearby trail’s sheet', () => {
  it('names its length and its park on one line', () => {
    const detail = buildLineDetail(NEARBY_LINE, {}, [], 'imperial', 'Appalachian Trail')
    expect(detail.extentLine).toBe('24.0 mi · Harriman State Park')
  })

  it('keeps whichever half it has when the other is missing', () => {
    // OPRHP publishes Miles on every segment and a Unit on most, so a trail
    // with a length and no park is ordinary rather than an error - and
    // "24.0 mi · " with nothing after it would read as one.
    const noPark = buildLineDetail({ ...NEARBY_LINE, park: null }, {}, [])
    expect(noPark.extentLine).toBe('24.0 mi')

    const noLength = buildLineDetail({ ...NEARBY_LINE, lengthMiles: null }, {}, [])
    expect(noLength.extentLine).toBe('Harriman State Park')

    const neither = buildLineDetail(
      { ...NEARBY_LINE, lengthMiles: null, park: null },
      {},
      [],
    )
    expect(neither.extentLine).toBeNull()
  })

  it('takes its provenance from the published attribution, never from a table in this file', () => {
    // §6's prohibition. The wording is a licence condition, so it ships from
    // the steward's own record and this client only renders it.
    const detail = buildLineDetail(
      NEARBY_LINE,
      {},
      [],
      'imperial',
      'Appalachian Trail',
      undefined,
      SOURCES,
    )
    expect(detail.sourceLine).toBe(
      'From New York State Office of Parks, Recreation and Historic Preservation.',
    )
  })

  it('falls back to the raw source id when nothing published an attribution', () => {
    const detail = buildLineDetail(NEARBY_LINE, {}, [])
    expect(detail.sourceLine).toBe('From oprhp_trails.')
  })

  it('says a trail is not the chosen one, and where switching lives', () => {
    const detail = buildLineDetail(NEARBY_LINE, {}, [])
    expect(detail.switchNote).toBe(
      'Not the trail you chose. Switching happens in the picker.',
    )
  })

  it('says nothing about switching on the chosen trail’s own lines', () => {
    for (const source of CHOSEN_SYSTEM_SOURCES) {
      const detail = buildLineDetail(
        { id: 'x', source, name: null, blazeColor: 'White' },
        {},
        [],
      )
      expect(detail.switchNote).toBeNull()
    }
  })
})

describe('a long-term closed trail', () => {
  it('names the steward who closed it and the layer’s own edit date', () => {
    const detail = buildLineDetail(
      { ...NEARBY_LINE, trailStatus: 'Closed' },
      {},
      [],
      'imperial',
      'Appalachian Trail',
      undefined,
      SOURCES,
    )
    expect(detail.closureLine).toBe(
      'Closed by New York State Office of Parks, Recreation and Historic Preservation · layer edited 4 Aug 2026',
    )
  })

  it('drops the "by" clause rather than inventing an authority for the claim', () => {
    const detail = buildLineDetail({ ...NEARBY_LINE, trailStatus: 'Closed' }, {}, [])
    expect(detail.closureLine).toBe('Closed')
  })

  it('says nothing for a status that is not "closed"', () => {
    // §3 is explicit that Proposed and blank/Unknown never ship at all, so a
    // value arriving here that is neither is a fact the sheet has nothing to
    // say about - not one it should paraphrase.
    for (const status of ['Open', 'Proposed', 'Unknown', '', null, undefined]) {
      const detail = buildLineDetail({ ...NEARBY_LINE, trailStatus: status }, {}, [])
      expect(detail.closureLine).toBeNull()
    }
  })

  it('reads the status case-insensitively, because a steward’s casing is not a decision', () => {
    for (const status of ['closed', 'CLOSED', ' Closed ']) {
      const detail = buildLineDetail({ ...NEARBY_LINE, trailStatus: status }, {}, [])
      expect(detail.closureLine).toBe('Closed')
    }
  })
})

describe('a temporarily closed area on a trail (#1142)', () => {
  // What the exporter ships on an area-derived closed record: the closure
  // LAYER's own registry key and the closing org's reason, verbatim -
  // export_nearby_trails.apply_area_closures. The line itself can belong to
  // a different organization entirely, which is the case that matters.
  const AREA_CLOSED = {
    ...NEARBY_LINE,
    source: 'nynjtc_long_path',
    name: 'Long Path',
    trailStatus: 'closed',
    closureKind: 'area',
    closureReason: 'Closed Until 2027',
    closureSource: 'oprhp_trail_closures',
  }
  const WITH_CLOSURE_LAYER: TrailSourceTable = {
    ...SOURCES,
    nynjtc_long_path: { attribution: 'New York–New Jersey Trail Conference' },
    oprhp_trail_closures: {
      attribution: 'New York State Office of Parks, Recreation and Historic Preservation',
    },
  }

  it('speaks in the closing organization’s voice, not the line’s', () => {
    const detail = buildLineDetail(
      AREA_CLOSED,
      {},
      [],
      'imperial',
      'Appalachian Trail',
      undefined,
      WITH_CLOSURE_LAYER,
    )
    // NYNJTC drew this line; OPRHP closed the ground. The sentence is
    // OPRHP's - reading it in NYNJTC's name is the misattribution #1142
    // exists to prevent.
    expect(detail.closureLine).toBe(
      'Temporarily closed by New York State Office of Parks, Recreation and Historic Preservation · Closed Until 2027',
    )
  })

  it('shows no date, because the closure layer publishes none per feature', () => {
    // The trails LAYER's edit date is in the table (SOURCES carries one for
    // oprhp_trails) and must not leak into this sentence: it is a fact about
    // the wrong layer. apply_area_closures' own rule: nothing invented.
    const detail = buildLineDetail(
      { ...AREA_CLOSED, source: 'oprhp_trails' },
      {},
      [],
      'imperial',
      'Appalachian Trail',
      undefined,
      WITH_CLOSURE_LAYER,
    )
    expect(detail.closureLine).not.toContain('layer edited')
  })

  it('drops the by-clause rather than printing a registry key as an authority', () => {
    // No table entry for the closure layer: the reason still shows - it is
    // the safety payload - but "by oprhp_trail_closures" would read as a
    // malfunction on the one line a hiker is meant to obey.
    const detail = buildLineDetail(AREA_CLOSED, {}, [])
    expect(detail.closureLine).toBe('Temporarily closed · Closed Until 2027')
  })

  it('stands alone when the closing organization gave no reason', () => {
    const detail = buildLineDetail({ ...AREA_CLOSED, closureReason: null }, {}, [])
    expect(detail.closureLine).toBe('Temporarily closed')
  })

  it('keeps the long-term voice for a record with no kind at all', () => {
    // An artifact published before #964 split the feeds carries closed
    // records with no closure_kind - and in that world the long-term voice
    // was the only voice there was, so it is what that build meant.
    const detail = buildLineDetail(
      { ...NEARBY_LINE, trailStatus: 'Closed' },
      {},
      [],
      'imperial',
      'Appalachian Trail',
      undefined,
      SOURCES,
    )
    expect(detail.closureLine).toBe(
      'Closed by New York State Office of Parks, Recreation and Historic Preservation · layer edited 4 Aug 2026',
    )
  })
})
