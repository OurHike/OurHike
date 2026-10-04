import { describe, expect, it } from 'vitest'
import type { FeatureCollection } from 'geojson'
import {
  NOTICE_WINDOW_DAYS,
  inNoticeWindow,
  plannedNotices,
  shiftDay,
  shownNotices,
} from './plannedNotices'
import type { ClubSections } from './clubSections'
import type { DayHike } from './dayHikes'
import type { TrailNotice } from './notices'
import type { Steward, Stewards } from './stewards'
import { buildTrailIndex } from './trailPosition'
import type { Trip } from './trips'

// Decision 66's rule (the maintainer, 2026-10-04): "Every notice that touches
// a planned hike in the next 7 days. for a long hike get everything along the
// planned hike in the next 7". The cases the brief named: the 7-day window's
// edge, a long hike's 7-day stretch, a placed notice off the route, and an
// unplaced notice of a club the route does not touch - each against the
// rule's own inputs, which are what the phone already stores.

const TODAY = '2026-10-04'

/** A centerline due north up one meridian, a vertex every 0.01 degrees (about
 *  0.7 mi apart), 100 vertices: about 69 mi of "A.T." to plan along. */
function northboundLine(): FeatureCollection {
  const coordinates: Array<[number, number]> = []
  for (let i = 0; i <= 100; i += 1) coordinates.push([-77, 34 + i * 0.01])
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { source: 'centerline' },
        geometry: { type: 'LineString', coordinates },
      },
    ],
  } as FeatureCollection
}

const INDEX = buildTrailIndex(northboundLine())

function steward(provider: string, keys: string[]): Steward {
  return {
    provider,
    name: `${provider} name`,
    trust: null,
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: [],
    keys,
    support: null,
    store: null,
  }
}

const STEWARDS: Stewards = [
  steward('ATC', ['centerline', 'atc_trail_updates']),
  steward('GMC', ['gmc_trail_conditions']),
  steward('BTA', ['bta_trail_closures']),
  steward('NYS OPRHP', ['oprhp_trails', 'oprhp_trail_closures']),
]

/** ATC's club sections: GMC maintains miles 0 to 20 of the fixture line. */
const SECTIONS: ClubSections = {
  clubs: [
    {
      acronym: 'GMC',
      name: 'Green Mountain Club',
      region: null,
      runs: [{ startMile: 0, endMile: 20 }],
      miles: 20,
    },
    {
      acronym: 'NOPE',
      name: 'A club with no registry provider',
      region: null,
      runs: [{ startMile: 0, endMile: 69 }],
      miles: 69,
    },
  ],
  unattributed: [],
  sources: { attribution: null, names: null, miles: null },
  sourceEdited: {},
}

function notice(
  overrides: Partial<TrailNotice> & Pick<TrailNotice, 'notice_id' | 'source_key'>,
): TrailNotice {
  return {
    title: overrides.notice_id,
    category: null,
    locality: '',
    place: { kind: 'unplaced' },
    obstructs_trail: false,
    updated_at: '2026-10-01T12:00:00Z',
    source_url: null,
    review_state: 'unreviewed',
    ...overrides,
  }
}

/** A long hike of ten five-mile days from mile 0, the first dated today. */
function tenDayTrip(firstDay = TODAY): Trip {
  const stops = Array.from({ length: 11 }, (_, i) => ({ mile: i * 5, resupply: false }))
  const days = Array.from({ length: 10 }, (_, i) => ({
    id: `d${i}`,
    date: shiftDay(firstDay, i),
    pinned: false,
    generated: true,
  }))
  return {
    id: 'trip-1',
    name: 'Fixture section',
    plan: { target: { miles: 5 }, stops, days },
  }
}

function dayHike(date: string | null, overrides: Partial<DayHike> = {}): DayHike {
  return {
    id: 'hike-1',
    name: 'Fixture loop',
    date,
    segments: [
      [
        { coord: [-76.5, 41.1], poiId: null },
        { coord: [-76.5, 41.2], poiId: null },
      ],
    ],
    figures: {
      miles: 7,
      legs: [
        { name: 'Fixture Trail', source: 'oprhp_trails', blaze_color: null, miles: 7 },
      ],
    },
    looped: false,
    recorded: 'planned',
    note: '',
    ...overrides,
  }
}

function pick(notices: TrailNotice[], trips: Trip[], dayHikes: DayHike[]) {
  return plannedNotices({
    notices,
    trips,
    dayHikes,
    today: TODAY,
    trailIndex: INDEX,
    routeDayHike: null,
    clubSections: SECTIONS,
    stewards: STEWARDS,
  })
}

describe('the 7-day window', () => {
  it('holds today and the six days after it, and not the seventh', () => {
    expect(NOTICE_WINDOW_DAYS).toBe(7)
    expect(inNoticeWindow(TODAY, TODAY)).toBe(true)
    expect(inNoticeWindow('2026-10-10', TODAY)).toBe(true)
    expect(inNoticeWindow('2026-10-11', TODAY)).toBe(false)
    expect(inNoticeWindow('2026-10-03', TODAY)).toBe(false)
  })

  it('crosses a month end and a DST change by calendar days', () => {
    expect(shiftDay('2026-10-29', 6)).toBe('2026-11-04')
    expect(inNoticeWindow('2026-11-04', '2026-10-29')).toBe(true)
    expect(inNoticeWindow('2026-11-05', '2026-10-29')).toBe(false)
  })

  it('picks a day hike dated on the window’s last day, and none dated the day after', () => {
    const club = notice({
      notice_id: 'oprhp_trail_closures:1',
      source_key: 'oprhp_trail_closures',
    })
    const lastDay = pick([club], [], [dayHike('2026-10-10')])
    expect(lastDay.hikes).toHaveLength(1)
    expect(lastDay.hikes[0].fromClubs.map((n) => n.notice_id)).toEqual([
      'oprhp_trail_closures:1',
    ])

    const dayAfter = pick([club], [], [dayHike('2026-10-11')])
    expect(dayAfter.hikes).toEqual([])
    expect(dayAfter.empty).toBe('nothing_in_the_window')
  })

  it('says nothing is planned, rather than showing every club, with no plan at all', () => {
    const everything = [
      notice({ notice_id: 'bta_trail_closures:1', source_key: 'bta_trail_closures' }),
      notice({
        notice_id: 'atc_trail_updates:a',
        source_key: 'atc_trail_updates',
        place: { kind: 'at_miles', start: 1, end: 1 },
      }),
    ]
    const none = pick(everything, [], [])
    expect(none).toEqual({ hikes: [], empty: 'nothing_planned', undated: 0 })
    expect(shownNotices(none)).toEqual([])
  })

  it('counts undated plans, which no window can hold, and never guesses a date for one', () => {
    const undated = pick([], [], [dayHike(null)])
    expect(undated.empty).toBe('nothing_in_the_window')
    expect(undated.undated).toBe(1)
  })

  it('leaves out a recorded walk and a day already walked', () => {
    const walked = tenDayTrip()
    walked.plan.days = walked.plan.days.map((day) => ({ ...day, walked: true }))
    expect(pick([], [walked], [dayHike(TODAY, { recorded: 'walked' })]).hikes).toEqual([])
  })
})

describe('a long hike’s 7-day stretch', () => {
  it('is the miles of the days dated in the window, never the whole hike', () => {
    const { hikes } = pick([], [tenDayTrip()], [])
    expect(hikes).toHaveLength(1)
    const { stretch } = hikes[0]
    // Days 1 to 7 of ten five-mile days: miles 0 to 35, not 0 to 50.
    expect(stretch.atSpans).toEqual([[0, 35]])
    expect(stretch.from).toBe('2026-10-04')
    expect(stretch.to).toBe('2026-10-10')
    expect(stretch.kind).toBe('long_hike')
  })

  it('takes an A.T. notice placed inside the stretch and leaves one placed past it', () => {
    const inside = notice({
      notice_id: 'atc_trail_updates:bridge',
      source_key: 'atc_trail_updates',
      place: { kind: 'at_miles', start: 30, end: 30 },
      obstructs_trail: true,
    })
    const past = notice({
      notice_id: 'atc_trail_updates:later',
      source_key: 'atc_trail_updates',
      place: { kind: 'at_miles', start: 40, end: 42 },
    })
    const { hikes } = pick([inside, past], [tenDayTrip()], [])
    expect(hikes[0].onRoute.map((n) => n.notice_id)).toEqual(['atc_trail_updates:bridge'])
  })

  it('starts the stretch at today for a hike already under way', () => {
    const { hikes } = pick([], [tenDayTrip('2026-10-01')], [])
    // Days 4 to 10 (2026-10-04 to 10-10) are in the window: miles 15 to 50.
    expect(hikes[0].stretch.atSpans).toEqual([[15, 50]])
  })

  it('finds the clubs from ATC’s club sections, by provider and never by name', () => {
    const gmc = notice({
      notice_id: 'gmc_trail_conditions:1',
      source_key: 'gmc_trail_conditions',
    })
    const { hikes } = pick([gmc], [tenDayTrip()], [])
    expect([...hikes[0].stretch.providers].sort()).toEqual(['ATC', 'GMC'])
    expect(hikes[0].fromClubs.map((n) => n.notice_id)).toEqual(['gmc_trail_conditions:1'])
  })
})

describe('a placed notice', () => {
  // The fixture line runs up lon -77; at lat 34.2 a degree of longitude is
  // about 92 km, so 0.0003 degrees is about 90 ft and 0.02 is about 1.15 mi.
  const nearPoint = notice({
    notice_id: 'club_points:near',
    source_key: 'club_points',
    place: {
      kind: 'geometry',
      geometry: { type: 'Point', coordinates: [-76.9997, 34.2] },
    },
  })
  const offPoint = notice({
    notice_id: 'club_points:off',
    source_key: 'club_points',
    place: { kind: 'geometry', geometry: { type: 'Point', coordinates: [-76.98, 34.2] } },
  })
  const crossedArea = notice({
    notice_id: 'iata_lands_hunting_regs:1',
    source_key: 'iata_lands_hunting_regs',
    hazard: 'hunting',
    place: {
      kind: 'geometry',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-77.01, 34.25],
            [-76.99, 34.25],
            [-76.99, 34.26],
            [-77.01, 34.26],
            [-77.01, 34.25],
          ],
        ],
      },
    },
  })

  it('touches the route it is beside, and not one it sits a mile off', () => {
    const { hikes } = pick([nearPoint, offPoint, crossedArea], [tenDayTrip()], [])
    expect(hikes[0].onRoute.map((n) => n.notice_id).sort()).toEqual([
      'club_points:near',
      'iata_lands_hunting_regs:1',
    ])
    expect(hikes[0].fromClubs).toEqual([])
  })

  it('does not touch a stretch past the 7 days even where it is on the trail', () => {
    // Lat 34.5 is about mile 34.6 on the line; the stretch ends at mile 35,
    // so move the point to lat 34.6, about mile 41.5, outside it.
    const later = notice({
      notice_id: 'club_points:later',
      source_key: 'club_points',
      place: { kind: 'geometry', geometry: { type: 'Point', coordinates: [-77, 34.6] } },
    })
    expect(pick([later], [tenDayTrip()], []).hikes[0].onRoute).toEqual([])
  })

  it('does not touch a hike whose days end before the notice starts', () => {
    const autumn = {
      ...nearPoint,
      notice_id: 'club_points:autumn',
      starts_on: '2026-11-15',
    }
    const ended = { ...nearPoint, notice_id: 'club_points:ended', ends_on: '2026-10-01' }
    expect(pick([autumn, ended], [tenDayTrip()], []).hikes[0].onRoute).toEqual([])
  })
})

describe('an unplaced notice', () => {
  const bta = notice({
    notice_id: 'bta_trail_closures:1',
    source_key: 'bta_trail_closures',
  })
  const oprhp = notice({
    notice_id: 'oprhp_trail_closures:9',
    source_key: 'oprhp_trail_closures',
  })

  it('of a club the route does not touch is left out', () => {
    const { hikes } = pick([bta, oprhp], [], [dayHike(TODAY)])
    expect(hikes[0].fromClubs.map((n) => n.notice_id)).toEqual(['oprhp_trail_closures:9'])
  })

  it('names its club by the provider it carries before the registry', () => {
    const carried = {
      ...bta,
      notice_id: 'new_source:1',
      source_key: 'new_source',
      provider: 'NYS OPRHP',
    }
    expect(pick([carried], [], [dayHike(TODAY)]).hikes[0].fromClubs).toHaveLength(1)
  })

  it('of an agency is left out even where the agency manages the route, and kept placed', () => {
    // The maintainer's "clubs only" (2026-10-04): NYS OPRHP manages the day
    // hike's trail, and its unplaced notice is not shown; placed on the
    // route, the same agency's notice is.
    const agency = { ...oprhp, steward_kind: 'agency' as const }
    const placed = {
      ...agency,
      notice_id: 'oprhp_trail_closures:10',
      place: {
        kind: 'geometry' as const,
        geometry: { type: 'Point' as const, coordinates: [-76.5, 41.15] },
      },
    }
    const { hikes } = pick([agency, placed], [], [dayHike(TODAY)])
    expect(hikes[0].fromClubs).toEqual([])
    expect(hikes[0].onRoute.map((n) => n.notice_id)).toEqual(['oprhp_trail_closures:10'])
  })

  it('of a club, or with no kind at all, is matched by its provider', () => {
    const club = {
      ...oprhp,
      notice_id: 'oprhp_trail_closures:11',
      steward_kind: 'club' as const,
    }
    const unknown = { ...oprhp, notice_id: 'oprhp_trail_closures:12', steward_kind: null }
    const { hikes } = pick([club, unknown], [], [dayHike(TODAY)])
    expect(hikes[0].fromClubs.map((n) => n.notice_id).sort()).toEqual([
      'oprhp_trail_closures:11',
      'oprhp_trail_closures:12',
    ])
  })

  it('reads NYNJTC-style terms as unplaced: an unmapped term places nothing', () => {
    const terms = notice({
      notice_id: 'nynjtc_trail_alerts:x',
      source_key: 'nynjtc_trail_alerts',
      provider: 'NYNJTC',
      place: { kind: 'org_terms', terms: ['trail:appalachian-trail'] },
    })
    // The long hike walks the A.T., and NYNJTC is not one of its clubs here.
    expect(pick([terms], [tenDayTrip()], []).hikes[0].onRoute).toEqual([])
    expect(pick([terms], [tenDayTrip()], []).hikes[0].fromClubs).toEqual([])
  })
})

describe('a day hike', () => {
  it('without the graph is matched to its tapped ends, and says so', () => {
    const { hikes } = pick([], [], [dayHike(TODAY)])
    expect(hikes[0].stretch.routeResolved).toBe(false)
    expect(hikes[0].stretch.lines).toEqual([
      [
        [-76.5, 41.1],
        [-76.5, 41.2],
      ],
    ])
  })

  it('takes its clubs from the legs’ sources, concurrent designations included', () => {
    const both = dayHike(TODAY, {
      figures: {
        miles: 7,
        legs: [
          {
            name: 'Fixture Trail',
            source: 'oprhp_trails',
            blaze_color: null,
            miles: 7,
            concurrent_sources: ['bta_trail_closures'],
          },
        ],
      },
    })
    expect([...pick([], [], [both]).hikes[0].stretch.providers].sort()).toEqual([
      'BTA',
      'NYS OPRHP',
    ])
  })
})

describe('what the panel shows, once', () => {
  it('lists a notice two hikes share once, closures first', () => {
    const closure = notice({
      notice_id: 'oprhp_trail_closures:c',
      source_key: 'oprhp_trail_closures',
      obstructs_trail: true,
      updated_at: '2026-01-01T00:00:00Z',
    })
    const newer = notice({
      notice_id: 'oprhp_trail_closures:n',
      source_key: 'oprhp_trail_closures',
    })
    const second = dayHike(TODAY, { id: 'hike-2', name: 'Second loop' })
    const planned = pick([newer, closure], [], [dayHike(TODAY), second])
    expect(planned.hikes).toHaveLength(2)
    expect(planned.hikes[0].fromClubs.map((n) => n.notice_id)).toEqual([
      'oprhp_trail_closures:c',
      'oprhp_trail_closures:n',
    ])
    expect(
      shownNotices(planned)
        .map((n) => n.notice_id)
        .sort(),
    ).toEqual(['oprhp_trail_closures:c', 'oprhp_trail_closures:n'])
  })
})
