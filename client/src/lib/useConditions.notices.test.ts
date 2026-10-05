// conditions/notices.json only once a hike is planned (#1805, decision 77).
//
// The file was 24,966,662 bytes, 6,203,870 gzipped, on soak run 536, and
// every phone fetched it on every conditions refresh. These hold the hook to
// the maintainer's rule at the request it makes: no planned hike, no
// download, only a HEAD asking whether the bucket serves it; a hike planned,
// the download at once rather than at the next hourly read; and a list the
// phone holds is never taken away.
//
// A file of its own because the bucket has to be configured for any request
// to leave lib/publishedConditions.ts, and lib/useConditions.test.ts's cases
// rely on it not being.

import { renderHook, waitFor } from '@testing-library/react'
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type MockInstance,
} from 'vitest'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

import { useConditions } from './useConditions'
import * as notices from './publishedNotices'

const NOTICES_URL = 'https://data.example/conditions/notices.json'

const A_NOTICES_DOCUMENT = {
  generated_at: '2026-10-05T01:22:48Z',
  notices: [
    {
      notice_id: 'club_page:1',
      source_key: 'club_page',
      title: 'Fixture trail work',
      place: { kind: 'unplaced' },
    },
  ],
}

/** A bucket that serves conditions/notices.json (or does not), answering a
 *  HEAD with no body, and 404 for every other key. */
function bucket({ serves }: { serves: boolean }): MockInstance<typeof fetch> {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (String(input) !== NOTICES_URL || !serves) return new Response('', { status: 404 })
    return init?.method === 'HEAD'
      ? new Response(null, { status: 200 })
      : new Response(JSON.stringify(A_NOTICES_DOCUMENT), { status: 200 })
  })
}

/** Each request this phone made for conditions/notices.json, by method. */
function noticeRequests(spy: MockInstance<typeof fetch>): string[] {
  return spy.mock.calls
    .filter(([input]) => String(input) === NOTICES_URL)
    .map(([, init]) => init?.method ?? 'GET')
}

describe('conditions/notices.json and a planned hike (decision 77)', () => {
  let spy: MockInstance<typeof fetch>
  afterEach(() => vi.restoreAllMocks())

  describe('on a bucket that serves it', () => {
    beforeEach(() => {
      spy = bucket({ serves: true })
    })

    it('downloads no byte of it with no hike planned, and asks only whether the bucket serves it', async () => {
      const { result } = renderHook(() => useConditions(true, true, false))
      await waitFor(() => expect(result.current.clubNoticesListed).toBe(true))
      expect(noticeRequests(spy)).toEqual(['HEAD'])
      expect(result.current.clubNotices).toBeNull()
    })

    it('downloads it the moment a hike is planned, without waiting for the hourly read', async () => {
      const { result, rerender } = renderHook(
        ({ planned }) => useConditions(true, true, planned),
        { initialProps: { planned: false } },
      )
      await waitFor(() => expect(result.current.clubNoticesListed).toBe(true))
      expect(noticeRequests(spy)).toEqual(['HEAD'])

      rerender({ planned: true })
      await waitFor(() => expect(result.current.clubNotices).toHaveLength(1))
      expect(noticeRequests(spy)).toEqual(['HEAD', 'GET'])
      expect(result.current.clubNoticesGeneratedAt?.toISOString()).toBe(
        '2026-10-05T01:22:48.000Z',
      )
    })

    it('keeps the list it holds when the hike stops being planned, and downloads it no more', async () => {
      const { result, rerender } = renderHook(
        ({ planned }) => useConditions(true, true, planned),
        { initialProps: { planned: true } },
      )
      await waitFor(() => expect(result.current.clubNotices).toHaveLength(1))
      expect(noticeRequests(spy)).toEqual(['GET'])

      rerender({ planned: false })
      await waitFor(() => expect(noticeRequests(spy)).toEqual(['GET', 'HEAD']))
      expect(result.current.clubNotices).toHaveLength(1)
    })

    it('asks the radio for nothing offline with no hike planned', async () => {
      const read = vi.spyOn(notices, 'readPublishedNotices')
      const { result } = renderHook(() => useConditions(false, true, false))
      // Waits on the read itself settling, since offline it changes no state.
      await waitFor(() => expect(read).toHaveBeenCalledWith(false, { online: false }))
      await read.mock.results[0].value
      expect(noticeRequests(spy)).toEqual([])
      expect(result.current.clubNoticesListed).toBe(false)
    })
  })

  it('leaves the panel where it was when the bucket answers 404, as the exporters’ bucket does', async () => {
    spy = bucket({ serves: false })
    const { result } = renderHook(() => useConditions(true, true, false))
    await waitFor(() => expect(noticeRequests(spy)).toEqual(['HEAD']))
    expect(result.current.clubNoticesListed).toBe(false)
    expect(result.current.clubNotices).toBeNull()
  })
})

describe('conditions/hazard_areas.json, read at launch whatever is planned (decision 84)', () => {
  const HAZARD_URL = 'https://data.example/conditions/hazard_areas.json'

  /** An invented hunting area and a row with no hazard, which the reader
   *  leaves out: the file holds hazard rows only, and a row that is not one
   *  is no area to draw. */
  const A_HAZARD_DOCUMENT = {
    generated_at: '2026-10-05T01:22:48Z',
    notices: [
      {
        notice_id: 'oprhp_hunting_areas:1',
        source_key: 'oprhp_hunting_areas',
        title: 'Fixture hunting area',
        hazard: 'hunting',
        place: {
          kind: 'geometry',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [-74.09, 41.24],
                [-74.08, 41.24],
                [-74.08, 41.25],
                [-74.09, 41.24],
              ],
            ],
          },
        },
      },
      {
        notice_id: 'club_page:1',
        source_key: 'club_page',
        title: 'Fixture trail work',
        hazard: null,
        place: { kind: 'unplaced' },
      },
    ],
  }

  /** A bucket serving both files, or neither (404, as production's does). */
  function bucketWithHazards({
    serves,
  }: {
    serves: boolean
  }): MockInstance<typeof fetch> {
    return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      if (!serves) return new Response('', { status: 404 })
      if (String(input) === HAZARD_URL) {
        return new Response(JSON.stringify(A_HAZARD_DOCUMENT), { status: 200 })
      }
      if (String(input) !== NOTICES_URL) return new Response('', { status: 404 })
      return init?.method === 'HEAD'
        ? new Response(null, { status: 200 })
        : new Response(JSON.stringify(A_NOTICES_DOCUMENT), { status: 200 })
    })
  }

  afterEach(() => vi.restoreAllMocks())

  it('downloads the hazard areas with no hike planned, and still no byte of notices.json', async () => {
    const spy = bucketWithHazards({ serves: true })
    const { result } = renderHook(() => useConditions(true, true, false))
    await waitFor(() => expect(result.current.hazardFile?.items).toHaveLength(1))
    expect(result.current.hazardFile?.items[0].notice_id).toBe('oprhp_hunting_areas:1')
    expect(result.current.hazardFile?.generatedAt.toISOString()).toBe(
      '2026-10-05T01:22:48.000Z',
    )
    expect(noticeRequests(spy)).toEqual(['HEAD'])
    expect(result.current.clubNotices).toBeNull()
  })

  it('keeps the hazard areas it holds when a later read finds no file, never reading that as no area', async () => {
    bucketWithHazards({ serves: true })
    const read = vi.spyOn(notices, 'readPublishedNotices')
    const { result, rerender } = renderHook(
      ({ planned }) => useConditions(true, true, planned),
      { initialProps: { planned: false } },
    )
    await waitFor(() => expect(result.current.hazardFile?.items).toHaveLength(1))

    // The next read answers nothing for the file: a 404 with no kept copy,
    // or a dead spot. Planning a hike is what runs the read again here.
    read.mockResolvedValue({ published: null, listed: false, hazards: null })
    rerender({ planned: true })
    await waitFor(() => expect(read).toHaveBeenCalledTimes(2))
    await read.mock.results[1].value
    expect(result.current.hazardFile?.items).toHaveLength(1)
  })

  it('holds no hazard file on a bucket that serves none, as production’s does today', async () => {
    const spy = bucketWithHazards({ serves: false })
    const { result } = renderHook(() => useConditions(true, true, false))
    await waitFor(() =>
      expect(spy.mock.calls.map(([input]) => String(input))).toContain(HAZARD_URL),
    )
    expect(result.current.hazardFile).toBeNull()
  })
})
