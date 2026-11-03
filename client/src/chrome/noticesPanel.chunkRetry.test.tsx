// lib/noticeSelection.ts reaches chrome/noticesPanel.tsx behind import(), and a
// chunk can fail to arrive: a precache that a service-worker update left
// stale, on a phone with no signal to fetch the new one. Without that module
// the panel draws no hazard area and counts no planned-hike notice. The hook
// lives in App for the app's whole life, so a failure must not be final: the
// next notices or hazard file to land asks for the chunk again.
//
// Its own file because the module is mocked to fail once, for every test here.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import type { FeatureCollection } from 'geojson'
import { useNoticesPanel } from './noticesPanel'
import type { TrailNotice } from '../lib/notices'
import { buildTrailIndex } from '../lib/trailPosition'

const chunk = vi.hoisted(() => ({ loads: 0 }))

vi.mock('../lib/noticeSelection', async (importOriginal) => {
  chunk.loads += 1
  if (chunk.loads === 1) {
    throw new TypeError('Failed to fetch dynamically imported module')
  }
  return importOriginal()
})

const NOW = new Date('2026-10-09T12:00:00.000Z')

/** A centerline due north along 77° W, 34° to 35° N, as
 *  noticesPanel.test.tsx's hazard cases draw against. */
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

/** An invented hunting area the centerline crosses at 34.3° N. */
const HUNTING_AREA: TrailNotice = {
  notice_id: 'oprhp_hunting_areas:1',
  source_key: 'oprhp_hunting_areas',
  title: 'Fixture hunting area',
  category: null,
  locality: '',
  hazard: 'hunting',
  obstructs_trail: false,
  updated_at: null,
  source_url: null,
  review_state: 'unreviewed',
  place: {
    kind: 'geometry',
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-77.01, 34.3],
          [-76.99, 34.3],
          [-76.99, 34.31],
          [-77.01, 34.31],
          [-77.01, 34.3],
        ],
      ],
    },
  },
}

afterEach(() => {
  cleanup()
})

describe('lib/noticeSelection.ts failing to load once', () => {
  it('is asked for again when the next hazard file lands, and then draws its areas', async () => {
    const { result, rerender } = renderHook(
      ({ hazardFile }) =>
        useNoticesPanel({
          updates: [],
          orgNotices: [],
          reviewedAt: null,
          stewards: [],
          trailIndex: INDEX,
          bbox: { west: -78, south: 34, east: -76, north: 35 },
          now: NOW,
          hazardFile,
        }),
      { initialProps: { hazardFile: { items: [HUNTING_AREA], generatedAt: NOW } } },
    )
    await waitFor(() => expect(chunk.loads).toBe(1))
    // Let the failed import settle before looking.
    await act(async () => {})
    expect(result.current.hazardAreas).toEqual([])

    // The next conditions read: the same file, read again, as a new object.
    rerender({ hazardFile: { items: [HUNTING_AREA], generatedAt: NOW } })

    await waitFor(() => expect(result.current.hazardAreas).toHaveLength(1))
    expect(chunk.loads).toBe(2)
  })
})
