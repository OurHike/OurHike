import { describe, expect, it } from 'vitest'
import { EMPTY_CLUB_SECTIONS } from './clubSections'
import { plannedNotices } from './plannedNotices'
import { validNotice } from './publishedNotices'
import { geometryParts, partsBounds } from './noticeGeometry'

// One conditions/notices.json row read defensively (lib/publishedNotices.ts's
// `validNotice`): a field this build cannot use repairs to its honest empty
// value, and never costs the row. Every row here is invented, shaped like
// what pipeline/dbt's pub_conditions_notices writes.

function row(overrides: Record<string, unknown> = {}) {
  return {
    notice_id: 'oprhp_trail_closures:7',
    source_key: 'oprhp_trail_closures',
    provider: 'NYS OPRHP',
    steward_kind: 'club',
    title: 'Fixture bridge out',
    obstructs_trail: true,
    place: { kind: 'unplaced' },
    ...overrides,
  }
}

describe('a category', () => {
  const category = (value: unknown) => validNotice(row({ category: value }))?.category

  it('that is a placeholder (None, na, n/a, null), in any case, is no category', () => {
    // Midpen's preserve-access layer sends "None" and Santa Clara County
    // Parks' sends "na" (soak run 536); decision 78 would show either under
    // the title as if the source had named a category.
    expect(category('None')).toBeNull()
    expect(category('na')).toBeNull()
    expect(category('N/A')).toBeNull()
    expect(category(' null ')).toBeNull()
  })

  it('that is a source’s own status or word is kept as it came, unknown among them', () => {
    // "unknown" is one of USFS's recreation-site openstatus values, as
    // "unreachable" and "not cleared" are: the source's status, not a blank.
    for (const value of [
      'unknown',
      'unreachable',
      'not cleared',
      'Regular',
      'None of the above',
    ])
      expect(category(value)).toBe(value)
  })
})

describe('a source_url', () => {
  it('that is a sentence is no link, though it ends in a URL', () => {
    // The shape of the value soak run 536 carried on all 111 nysdec_hab_reports
    // rows. lib/safeLink.ts resolves it as a path on OurHike's own page.
    const prose =
      'Learn how to report a fixture bloom at https://example.org/fixture.html?'
    expect(validNotice(row({ source_url: prose }))?.source_url).toBeNull()
  })

  it('is kept only as an absolute http or https URL', () => {
    const kept = (url: string) => validNotice(row({ source_url: url }))?.source_url
    expect(kept('https://example.org/fixture')).toBe('https://example.org/fixture')
    expect(kept('http://example.org/fixture')).toBe('http://example.org/fixture')
    expect(kept('/notices')).toBeNull()
    expect(kept('example.org/fixture')).toBeNull()
    expect(kept('mailto:fixture@example.org')).toBeNull()
  })
})

describe('a geometry place', () => {
  it.each([
    // What the writer's ST_AsGeoJSON makes of an empty polygon (the
    // reviewer's empty_geom.py, DuckDB spatial): {"type":"Polygon","coordinates":[]}.
    ['an empty polygon', { type: 'Polygon', coordinates: [] }],
    ['a point whose coordinates are strings', { type: 'Point', coordinates: ['a', 'b'] }],
  ])(
    'with no readable coordinates, as %s, still reaches a planned hike on its club’s trails',
    (_, geometry) => {
      const closure = validNotice(row({ place: { kind: 'geometry', geometry } }))
      const { hikes } = plannedNotices({
        notices: closure === null ? [] : [closure],
        trips: [],
        dayHikes: [
          {
            id: 'hike-1',
            name: 'Fixture loop',
            date: '2026-10-04',
            segments: [
              [
                { coord: [-76.5, 41.1], poiId: null },
                { coord: [-76.5, 41.2], poiId: null },
              ],
            ],
            figures: {
              miles: 7,
              legs: [
                {
                  name: 'Fixture Trail',
                  source: 'oprhp_trails',
                  blaze_color: null,
                  miles: 7,
                },
              ],
            },
            looped: false,
            recorded: 'planned',
            note: '',
          },
        ],
        today: '2026-10-04',
        trailIndex: null,
        routeDayHike: null,
        clubSections: EMPTY_CLUB_SECTIONS,
        stewards: [
          {
            provider: 'NYS OPRHP',
            name: 'Fixture parks office',
            trust: null,
            licence: null,
            attribution: null,
            terms: null,
            termsSource: null,
            layers: [],
            keys: ['oprhp_trails', 'oprhp_trail_closures'],
            support: null,
            store: null,
          },
        ],
      })
      expect(hikes[0].fromClubs.map((n) => n.notice_id)).toEqual([
        'oprhp_trail_closures:7',
      ])
    },
  )

  it('nested 20,000 GeometryCollections deep is kept, and reads as having no parts', () => {
    let geometry: unknown = { type: 'Point', coordinates: [-74.1, 41.2] }
    for (let i = 0; i < 20_000; i += 1) {
      geometry = { type: 'GeometryCollection', geometries: [geometry] }
    }
    const deep = validNotice(row({ place: { kind: 'geometry', geometry } }))
    expect(deep?.notice_id).toBe('oprhp_trail_closures:7')
    expect(deep?.place.kind).toBe('geometry')
    if (deep?.place.kind !== 'geometry') throw new Error('kept as a geometry')
    expect(partsBounds(geometryParts(deep.place.geometry))).toBeNull()
  })

  it('with a readable coordinate is kept as it came', () => {
    const point = { type: 'Point', coordinates: [-74.1, 41.2] }
    expect(
      validNotice(row({ place: { kind: 'geometry', geometry: point } }))?.place,
    ).toEqual({
      kind: 'geometry',
      geometry: point,
    })
  })
})
