import { describe, expect, it } from 'vitest'
import { EMPTY_CLUB_SECTIONS } from './clubSections'
import { plannedNotices } from './plannedNotices'
import { validNotice } from './publishedNotices'

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
  it('with no readable coordinates is unplaced, as a polygon a source sent empty arrives', () => {
    // What the writer's ST_AsGeoJSON makes of an empty polygon (the
    // reviewer's empty_geom.py, DuckDB spatial): {"type":"Polygon","coordinates":[]}.
    const empty = validNotice(
      row({
        place: { kind: 'geometry', geometry: { type: 'Polygon', coordinates: [] } },
      }),
    )
    expect(empty?.place).toEqual({ kind: 'unplaced' })
    const strings = validNotice(
      row({
        place: { kind: 'geometry', geometry: { type: 'Point', coordinates: ['a', 'b'] } },
      }),
    )
    expect(strings?.place).toEqual({ kind: 'unplaced' })
  })

  it('with no readable coordinates still reaches a planned hike on its club’s trails', () => {
    const closure = validNotice(
      row({
        place: { kind: 'geometry', geometry: { type: 'Polygon', coordinates: [] } },
      }),
    )
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
    expect(hikes[0].fromClubs.map((n) => n.notice_id)).toEqual(['oprhp_trail_closures:7'])
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
