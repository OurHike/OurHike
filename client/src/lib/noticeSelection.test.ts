import { describe, expect, it } from 'vitest'
import type { FeatureCollection } from 'geojson'
import { hazardView } from './noticeSelection'
import type { TrailNotice } from './notices'
import { buildTrailIndex } from './trailPosition'

// What chrome/noticesPanel.tsx loads behind import() decides beyond the
// planned-hike rule (lib/plannedNotices.test.ts holds that one). Every row
// here is invented.

function row(
  notice_id: string,
  first_seen_at: string | null,
  extra: Partial<TrailNotice> = {},
): TrailNotice {
  return {
    notice_id,
    source_key: notice_id.split(':')[0],
    title: notice_id,
    category: null,
    locality: '',
    place: { kind: 'unplaced' },
    obstructs_trail: false,
    updated_at: null,
    source_url: null,
    review_state: 'unreviewed',
    first_seen_at,
    changed_at: first_seen_at,
    ...extra,
  }
}

describe('which file decision 67’s areas are drawn from (decision 84)', () => {
  const area = (id: string): TrailNotice =>
    row(`oprhp_hunting_areas:${id}`, null, {
      hazard: 'hunting',
      place: { kind: 'geometry', geometry: { type: 'Point', coordinates: [-77, 34.3] } },
    })
  const at = new Date('2026-10-05T00:00:00Z')

  /** A centerline due north along 77° W, through the invented area at 34.3° N. */
  const INDEX = buildTrailIndex({
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { source: 'centerline' },
        geometry: {
          type: 'LineString',
          coordinates: Array.from({ length: 101 }, (_, i) => [-77, 34 + i * 0.01]),
        },
      },
    ],
  } as FeatureCollection)

  it('draws nothing, and says so with null, with neither file on the phone', () => {
    expect(hazardView(null, null, null, INDEX, null)).toBeNull()
  })

  it('draws the area from notices.json alone, where it crosses a held trail', () => {
    expect(hazardView([area('1')], at, null, INDEX, null)?.areas).toHaveLength(1)
  })

  it('reads an arrived empty hazard file as no area, over an older notices.json', () => {
    const older = new Date(at.getTime() - 1)
    const view = hazardView(
      [area('1')],
      older,
      { items: [], generatedAt: at },
      INDEX,
      null,
    )
    expect(view?.areas).toEqual([])
  })
})
