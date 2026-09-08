import { describe, it, expect } from 'vitest'
import {
  NO_FACETS,
  anchorOf,
  appliedFilters,
  authorLine,
  availableFacets,
  availableSorts,
  effectiveSort,
  facetCounts,
  findHikes,
  hikeEstimate,
  hikePlaces,
  publishersByKind,
  searchPlaces,
  shelfPicks,
  timeBucketOf,
  withoutFacet,
  withoutFilter,
  type HikeFacets,
  type SuggestedHike,
} from './suggestedHikes'
import { STANDARD_PACE } from '../lib/pace'

// The pure half of the hike finder (#1284). What is asserted here is the
// honesty contract the sheets and the list rely on: a facet cuts what it
// says, the counts are the numbers the list then shows, a walk nobody can
// price is never priced from distance alone, and a sort never drops a row.

/** Two clusters of starts: three in northern New Jersey, two in Virginia. */
const NJ = { lon: -74.6, lat: 41.2 }
const VA = { lon: -80.7, lat: 37.3 }

function hike(
  overrides: Partial<SuggestedHike> & Pick<SuggestedHike, 'id'>,
): SuggestedHike {
  return {
    name: overrides.id,
    miles: 5,
    climb: { gainFt: 500, lossFt: 500 },
    difficulty: 'moderate',
    author: { kind: 'club', name: 'A club' },
    segments: [
      [
        { coord: [NJ.lon, NJ.lat], poiId: null },
        { coord: [NJ.lon + 0.01, NJ.lat], poiId: null },
      ],
    ],
    ...overrides,
  }
}

// At the standard pace: Sunrise ≈2h 30m, Angels Rest ≈2h 35m, Pochuck
// ≈1h 15m, Dismal Falls ≈50m, Wapiti unpriced.
const SUNRISE = hike({
  id: 'sunrise',
  name: 'Sunrise Mtn loop',
  miles: 6.2,
  climb: { gainFt: 980, lossFt: 980 },
  difficulty: 'moderate',
  author: { kind: 'club', name: 'NY-NJ Trail Conference' },
  transit: {
    line: 'NJT 197',
    toStop: 'Culvers Gap',
    walkMiles: 0.3,
    source: 'NY-NJ Trail Conference',
  },
  segments: [
    [
      { coord: [NJ.lon, NJ.lat], poiId: null },
      { coord: [NJ.lon + 0.02, NJ.lat], poiId: null },
    ],
  ],
})
const ANGELS = hike({
  id: 'angels',
  name: 'Angels Rest',
  miles: 5.6,
  climb: { gainFt: 1540, lossFt: 1540 },
  difficulty: 'strenuous',
  author: { kind: 'guidebook', name: 'L. Adkins' },
  segments: [
    [
      { coord: [VA.lon, VA.lat], poiId: null },
      { coord: [VA.lon + 0.02, VA.lat], poiId: null },
    ],
  ],
})
const POCHUCK = hike({
  id: 'pochuck',
  name: 'Pochuck boardwalk',
  miles: 3.6,
  climb: { gainFt: 120, lossFt: 120 },
  difficulty: 'easy',
  author: { kind: 'hiker', name: '@slackpack' },
  transit: { line: 'NJT 890', toStop: 'Vernon', walkMiles: 0.6, source: 'NJ Transit' },
  segments: [
    [
      { coord: [NJ.lon + 0.1, NJ.lat + 0.05], poiId: null },
      { coord: [NJ.lon + 0.12, NJ.lat + 0.05], poiId: null },
    ],
  ],
})
const WAPITI = hike({
  id: 'wapiti',
  name: 'Wapiti to Docs Knob',
  miles: 7.9,
  climb: null,
  difficulty: 'moderate',
  author: { kind: 'ourhike', name: 'Vernon Trails' },
  segments: [
    [
      { coord: [VA.lon + 0.05, VA.lat + 0.05], poiId: null },
      { coord: [VA.lon + 0.07, VA.lat + 0.05], poiId: null },
    ],
  ],
})
const DISMAL = hike({
  id: 'dismal',
  name: 'Dismal Falls',
  miles: 2.2,
  climb: { gainFt: 180, lossFt: 180 },
  difficulty: null,
  author: { kind: 'club', name: 'Outdoor Club at Virginia Tech' },
  transit: {
    line: 'Route 100',
    toStop: 'Pearisburg',
    walkMiles: 1.4,
    source: 'the club',
  },
  segments: [
    [
      { coord: [VA.lon + 0.2, VA.lat + 0.2], poiId: null },
      { coord: [VA.lon + 0.22, VA.lat + 0.2], poiId: null },
    ],
  ],
})

const HIKES = [SUNRISE, ANGELS, POCHUCK, WAPITI, DISMAL]

function facets(overrides: Partial<HikeFacets>): HikeFacets {
  return { ...NO_FACETS, ...overrides }
}

function ids(hikes: readonly SuggestedHike[]): string[] {
  return hikes.map((h) => h.id)
}

describe('pricing a suggested hike', () => {
  it('prices a walk from its cached climb at the hiker’s pace, ≈-prefixed', () => {
    expect(hikeEstimate(SUNRISE, STANDARD_PACE)?.text).toBe('≈2h 30m')
  })

  it('offers no time at all for a walk whose climb nobody measured', () => {
    // Never from distance alone: Naismith without ascent is a flat-ground
    // claim, and on this network it is short.
    expect(hikeEstimate(WAPITI, STANDARD_PACE)).toBeNull()
    expect(hikeEstimate({ ...WAPITI, climb: undefined }, STANDARD_PACE)).toBeNull()
  })

  it('buckets on the printed, rounded time so a row never disagrees with its sheet', () => {
    expect(timeBucketOf(117)).toBe('under2')
    // 119 raw minutes prints as ≈2h, which reads as "2 – 4 hours".
    expect(timeBucketOf(119)).toBe('2to4')
    expect(timeBucketOf(239)).toBe('4to6')
    expect(timeBucketOf(360)).toBe('allDay')
  })
})

describe('filtering', () => {
  it('cuts by the publisher’s difficulty, and an unrated route by any difficulty', () => {
    const easy = findHikes(HIKES, facets({ difficulty: ['easy'] }), STANDARD_PACE, null)
    expect(ids(easy)).toEqual(['pochuck'])
    const rated = findHikes(
      HIKES,
      facets({ difficulty: ['easy', 'moderate', 'strenuous'] }),
      STANDARD_PACE,
      null,
    )
    // Dismal Falls carries no rating, so asking for any rating excludes it.
    expect(ids(rated)).not.toContain('dismal')
  })

  it('cuts by a time bucket, and an unpriced route falls in no bucket', () => {
    const afternoon = findHikes(HIKES, facets({ time: '2to4' }), STANDARD_PACE, null)
    expect(ids(afternoon).sort()).toEqual(['angels', 'sunrise'])
    for (const time of ['under2', '2to4', '4to6', 'allDay'] as const) {
      expect(ids(findHikes(HIKES, facets({ time }), STANDARD_PACE, null))).not.toContain(
        'wapiti',
      )
    }
  })

  it('excludes a route with no published transit under the switch, and lists it otherwise', () => {
    const byTransit = findHikes(HIKES, facets({ transitOnly: true }), STANDARD_PACE, null)
    expect(ids(byTransit).sort()).toEqual(['dismal', 'pochuck', 'sunrise'])
    expect(ids(findHikes(HIKES, NO_FACETS, STANDARD_PACE, null))).toContain('angels')
  })

  it('cuts by who published it', () => {
    const clubs = findHikes(HIKES, facets({ authors: ['club'] }), STANDARD_PACE, null)
    expect(ids(clubs).sort()).toEqual(['dismal', 'sunrise'])
  })

  it('never cuts by distance - a place orders the list, it does not fence it', () => {
    const fromVirginia = findHikes(
      HIKES,
      facets({ place: { label: 'Pearisburg, VA', at: VA }, sort: 'nearest' }),
      STANDARD_PACE,
      null,
    )
    expect(fromVirginia).toHaveLength(HIKES.length)
    expect(ids(fromVirginia)[0]).toBe('angels')
  })
})

describe('the counts the sheets print', () => {
  it('counts each option with every other facet as set', () => {
    const counts = facetCounts(HIKES, facets({ transitOnly: true }), STANDARD_PACE)
    // Of the three with transit: Pochuck and Dismal are under two hours,
    // Sunrise is an afternoon.
    expect(counts.time).toEqual({ under2: 2, '2to4': 1, '4to6': 0, allDay: 0 })
    expect(counts.difficulty).toEqual({ easy: 1, moderate: 1, strenuous: 0 })
    expect(counts.authors).toEqual({ club: 2, guidebook: 0, hiker: 1, ourhike: 0 })
  })

  it('counts the option alone, not the option added to what is already picked', () => {
    // With "easy" already set, the moderate row still says what picking
    // moderate INSTEAD would leave - the number the hiker would then see.
    const counts = facetCounts(HIKES, facets({ difficulty: ['easy'] }), STANDARD_PACE)
    expect(counts.difficulty.moderate).toBe(2)
    // The OTHER facets still hold: of the easy routes, only Pochuck is by
    // transit (Dismal Falls carries no rating at all).
    expect(counts.transit).toBe(1)
  })

  it('agrees with the list: the primary button’s number is the list’s length', () => {
    const chosen = facets({ time: '2to4', transitOnly: true })
    const counts = facetCounts(HIKES, facets({ transitOnly: true }), STANDARD_PACE)
    expect(findHikes(HIKES, chosen, STANDARD_PACE, null)).toHaveLength(
      counts.time['2to4'],
    )
  })
})

describe('the three sorts', () => {
  it('nearest first from the anchor, and a start nobody can read goes last', () => {
    const noStart = hike({ id: 'lost', segments: [] })
    const nearest = findHikes(
      [...HIKES, noStart],
      facets({ sort: 'nearest' }),
      STANDARD_PACE,
      NJ,
    )
    expect(ids(nearest).slice(0, 2)).toEqual(['sunrise', 'pochuck'])
    expect(ids(nearest).at(-1)).toBe('lost')
  })

  it('shortest first prices from the climb, and an unmeasured climb sorts last rather than at zero', () => {
    const shortest = findHikes(HIKES, facets({ sort: 'shortest' }), STANDARD_PACE, null)
    expect(ids(shortest)).toEqual(['dismal', 'pochuck', 'sunrise', 'angels', 'wapiti'])
  })

  it('easiest first quotes the publisher, and an unrated route sorts last', () => {
    const easiest = findHikes(HIKES, facets({ sort: 'easiest' }), STANDARD_PACE, null)
    expect(ids(easiest)).toEqual(['pochuck', 'sunrise', 'wapiti', 'angels', 'dismal'])
  })

  it('offers each sort only when it can be honest', () => {
    expect(availableSorts(HIKES, null, STANDARD_PACE)).toEqual(['shortest', 'easiest'])
    expect(availableSorts(HIKES, NJ, STANDARD_PACE)).toEqual([
      'nearest',
      'shortest',
      'easiest',
    ])
    expect(availableSorts([WAPITI], null, STANDARD_PACE)).toEqual(['easiest'])
    expect(
      availableSorts([{ ...WAPITI, difficulty: null }], null, STANDARD_PACE),
    ).toEqual([])
  })

  it('falls back to the first honest sort, then to the published order', () => {
    expect(effectiveSort('nearest', ['shortest', 'easiest'])).toBe('shortest')
    expect(effectiveSort('easiest', ['shortest', 'easiest'])).toBe('easiest')
    expect(effectiveSort(null, [])).toBeNull()
    // Nothing to price, nothing rated, nowhere to measure from: the list is
    // the publisher's own order, not a sort pretending to be one.
    const unsortable = [
      { ...WAPITI, difficulty: null },
      { ...SUNRISE, climb: null, difficulty: null },
    ]
    expect(ids(findHikes(unsortable, NO_FACETS, STANDARD_PACE, null))).toEqual([
      'wapiti',
      'sunrise',
    ])
  })

  it('anchors on a picked place before the fix', () => {
    expect(anchorOf(facets({ place: { label: 'x', at: VA } }), NJ)).toEqual(VA)
    expect(anchorOf(NO_FACETS, NJ)).toEqual(NJ)
    expect(anchorOf(NO_FACETS, null)).toBeNull()
  })
})

describe('which facets are offered at all', () => {
  it('offers nothing over an empty phone', () => {
    expect(availableFacets([], STANDARD_PACE)).toEqual([])
  })

  it('withholds a facet no route can answer', () => {
    const noTransitNoTime = [{ ...ANGELS, climb: null }]
    expect(availableFacets(noTransitNoTime, STANDARD_PACE)).toEqual([
      'difficulty',
      'author',
    ])
    expect(availableFacets(HIKES, STANDARD_PACE)).toEqual([
      'difficulty',
      'time',
      'transit',
      'author',
    ])
  })

  it('lists the publishers under each kind, once each, in published order', () => {
    const byKind = publishersByKind([...HIKES, SUNRISE])
    expect(byKind.club).toEqual([
      'NY-NJ Trail Conference',
      'Outdoor Club at Virginia Tech',
    ])
    expect(byKind.ourhike).toEqual(['Vernon Trails'])
  })
})

describe('the Today shelf', () => {
  it('picks the nearest starts when there is a fix', () => {
    expect(ids(shelfPicks(HIKES, VA))).toEqual(['angels', 'wapiti', 'dismal'])
  })

  it('picks the first published when there is not, claiming nothing about distance', () => {
    expect(ids(shelfPicks(HIKES, null))).toEqual(['sunrise', 'angels', 'pochuck'])
  })
})

describe('applied filters as chips', () => {
  it('spells each applied filter, and dropping one leaves the rest', () => {
    const chosen = facets({ time: '2to4', transitOnly: true, difficulty: ['moderate'] })
    const chips = appliedFilters(chosen)
    expect(chips.map((chip) => chip.label)).toEqual(['2–4 h', 'By transit', 'Moderate'])

    const dropped = withoutFilter(chosen, chips[1])
    expect(dropped.transitOnly).toBe(false)
    expect(dropped.time).toBe('2to4')
    expect(dropped.difficulty).toEqual(['moderate'])
  })

  it('clears one whole facet and nothing else', () => {
    const chosen = facets({ difficulty: ['easy', 'moderate'], authors: ['club'] })
    expect(withoutFacet(chosen, 'difficulty').difficulty).toEqual([])
    expect(withoutFacet(chosen, 'difficulty').authors).toEqual(['club'])
  })
})

describe('who wrote it', () => {
  it('names the publisher in the voice of what kind of publisher they are', () => {
    expect(authorLine(SUNRISE.author)).toBe('NY-NJ Trail Conference')
    expect(authorLine(ANGELS.author)).toBe('Guidebook route · L. Adkins')
    expect(authorLine(POCHUCK.author)).toBe('Published by @slackpack')
    // A pick is a label on the route; the route's own author is still named.
    expect(authorLine(WAPITI.author)).toBe('OurHike pick · route by Vernon Trails')
  })
})

describe('the places a search can be anchored on', () => {
  const POIS = [
    { id: 't1', name: 'Culvers Gap trailhead', type: 'trailhead', lat: 41.2, lon: -74.7 },
    {
      id: 'town',
      name: 'Pearisburg',
      type: 'resupply',
      source: 'atc_communities',
      lat: 37.3,
      lon: -80.7,
    },
    {
      id: 'store',
      name: 'Pearisburg Food Lion',
      type: 'resupply',
      source: 'other',
      lat: 37.3,
      lon: -80.7,
    },
    { id: 'shelter', name: 'Pearis Shelter', type: 'shelter', lat: 37.2, lon: -80.6 },
  ]

  it('offers towns and trailheads, and nothing a hiker does not set out from', () => {
    expect(hikePlaces(POIS).map((place) => place.id)).toEqual(['t1', 'town'])
    expect(hikePlaces(POIS)[1]).toEqual({
      id: 'town',
      name: 'Pearisburg',
      kind: 'town',
      at: { lon: -80.7, lat: 37.3 },
    })
  })

  it('matches on the name, earliest hit first, and nothing on an empty query', () => {
    const places = hikePlaces(POIS)
    expect(searchPlaces(places, 'pear').map((place) => place.id)).toEqual(['town'])
    expect(searchPlaces(places, 'gap').map((place) => place.id)).toEqual(['t1'])
    expect(searchPlaces(places, '  ')).toEqual([])
  })
})
