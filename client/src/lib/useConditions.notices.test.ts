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
