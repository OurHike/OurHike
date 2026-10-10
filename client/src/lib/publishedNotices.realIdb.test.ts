// conditions/notices.json and conditions/hazard_areas.json as a phone keeps
// them for its next launch with no signal (#447), against a REAL IndexedDB:
// idb-keyval over fake-indexeddb, as lib/archiveDownload.realIdb.test.ts runs
// it, so what is read back is what a phone would hold.
//
// UA's dbt-written notices.json measured 11,811,478 characters on 2026-10-09
// (8,309 notices, 1,257 of them obstructing a trail), and lib/conditionsCache.ts
// deleted the kept copy of anything over 2 MiB. A planned hike's closures were
// on the phone until its first relaunch with no signal, and then gone:
// chrome/noticesPanel.tsx fell back to ATC's and NYNJTC's own lists, and
// nothing said why.
//
// AND THE DEADLINES. A request with no deadline does not fail on a captive
// portal or a one-bar link: it hangs, and lib/publishedConditions.ts's
// `fetchPublished` reaches the kept copy only once its request fails. So each
// read here is held to answering, from the kept copy, once its deadline
// passes, and not before.

import 'fake-indexeddb/auto'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clear } from 'idb-keyval'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

import { recallPublished, rememberPublished } from './conditionsCache'
import { MANIFEST_READ_TIMEOUT_MS } from './dataManifest'
import { PUBLISHED_NOTICES_KEY } from './publishedConditions'
import {
  NOTICES_DOWNLOAD_TIMEOUT_MS,
  PUBLISHED_HAZARD_AREAS_KEY,
  fetchPublishedHazardAreas,
  noticesListed,
  readPublishedNotices,
} from './publishedNotices'

const NOTICES_URL = `https://data.example/${PUBLISHED_NOTICES_KEY}`

/** A planned hike's closure, and one area outline long enough to carry the
 *  document past `characters`: outlines are what make the live file large. */
function noticesLongerThan(characters: number) {
  // `[-74.123456,41.234567],` is 23 characters, and these run longer.
  const ring = Array.from({ length: Math.ceil(characters / 23) }, (_, index) => [
    -74.123456 + (index % 1000) * 1e-6,
    41.234567,
  ])
  ring.push(ring[0])
  return {
    generated_at: '2026-10-08T22:51:29Z',
    notices: [
      {
        notice_id: 'club_page:footbridge',
        source_key: 'club_page',
        title: 'Fixture footbridge out',
        obstructs_trail: true,
        place: { kind: 'unplaced' },
      },
      {
        notice_id: 'club_page:area',
        source_key: 'club_page',
        title: 'Fixture closed area',
        place: { kind: 'geometry', geometry: { type: 'Polygon', coordinates: [ring] } },
      },
    ],
  }
}

const KEPT_NOTICES = {
  generated_at: '2026-10-07T06:00:00Z',
  notices: [
    {
      notice_id: 'club_page:footbridge',
      source_key: 'club_page',
      title: 'Fixture footbridge out',
      obstructs_trail: true,
      place: { kind: 'unplaced' },
    },
  ],
}

const KEPT_HAZARDS = {
  generated_at: '2026-10-07T06:00:00Z',
  notices: [
    {
      notice_id: 'oprhp_hunting_areas:1',
      source_key: 'oprhp_hunting_areas',
      title: 'Fixture hunting area',
      hazard: 'hunting',
      place: { kind: 'geometry', geometry: { type: 'Point', coordinates: [-74, 41] } },
    },
  ],
}

/** A request nobody answers, as on a captive portal or one bar, that gives
 *  up when its signal aborts, as fetch does. */
function unanswered(init?: RequestInit): Promise<Response> {
  return new Promise((_, reject) => {
    init?.signal?.addEventListener('abort', () =>
      reject(new DOMException('The operation was aborted.', 'AbortError')),
    )
  })
}

afterEach(async () => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  await clear()
})

describe('a planned hike’s notices.json on a relaunch with no signal', () => {
  it('reads back a file longer than the old 2 MiB ceiling, as it was online', async () => {
    const document = noticesLongerThan(3_000_000)
    expect(JSON.stringify(document).length).toBeGreaterThan(2 * 1024 * 1024)
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async (input) =>
        String(input) === NOTICES_URL
          ? new Response(JSON.stringify(document), { status: 200 })
          : new Response('', { status: 404 }),
      )

    const online = await readPublishedNotices(true, { online: true })
    expect(online.published?.items).toHaveLength(2)
    // Written behind the read (`void rememberPublished`), so waited for.
    await vi.waitFor(
      async () => expect(await recallPublished(PUBLISHED_NOTICES_KEY)).not.toBeNull(),
      { timeout: 5_000 },
    )

    // The relaunch: every module starts again, and the phone has no signal.
    vi.resetModules()
    fetched.mockClear()
    const relaunched = await import('./publishedNotices')
    const offline = await relaunched.readPublishedNotices(true, { online: false })

    expect(fetched).not.toHaveBeenCalled()
    expect(offline.published?.items.map((notice) => notice.notice_id)).toEqual([
      'club_page:footbridge',
      'club_page:area',
    ])
    expect(offline.published?.generatedAt.toISOString()).toBe('2026-10-08T22:51:29.000Z')
  })
})

// readPublishedNotices's `missing`: the legend row "Notices for your planned
// hikes: not on this phone yet" and the warning at the top of the list it
// opens (option A of the maintainer's poll of 2026-10-09). True only when a
// hike is planned, this phone kept no copy, and the read could not bring one
// for a reason a connection can change. A 404 is not that reason: the
// exporters' bucket serves no notices.json, and connecting brings nothing.
describe('readPublishedNotices’s missing, for a planned hike with no copy on this phone', () => {
  it('is true offline with nothing kept, and no request is made', async () => {
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => new Response('', { status: 404 }))
    const read = await readPublishedNotices(true, { online: false })
    expect(read).toEqual({ published: null, listed: false, missing: true })
    expect(fetched).not.toHaveBeenCalled()
  })

  it('is false offline when this phone kept a copy', async () => {
    await rememberPublished(PUBLISHED_NOTICES_KEY, KEPT_NOTICES)
    const read = await readPublishedNotices(true, { online: false })
    expect(read.missing).toBe(false)
    expect(read.published?.items.map((notice) => notice.notice_id)).toEqual([
      'club_page:footbridge',
    ])
  })

  it('is true when the download fails with nothing kept', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    const read = await readPublishedNotices(true, { online: true })
    expect(read).toEqual({ published: null, listed: false, missing: true })
  })

  it('is true when the bucket answers 503, or a page that is not JSON, with nothing kept', async () => {
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => new Response('', { status: 503 }))
    expect((await readPublishedNotices(true, { online: true })).missing).toBe(true)

    // A captive portal's sign-in page, served with a 200 in the file's place.
    fetched.mockImplementation(
      async () => new Response('<!doctype html><title>Sign in</title>', { status: 200 }),
    )
    expect((await readPublishedNotices(true, { online: true })).missing).toBe(true)
  })

  it('is false on a 404, as the exporters’ bucket answers, so the panel stays today’s', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      async () => new Response('', { status: 404 }),
    )
    const read = await readPublishedNotices(true, { online: true })
    expect(read).toEqual({ published: null, listed: false, missing: false })
  })

  it('is false once the file arrives', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
      String(input) === NOTICES_URL
        ? new Response(JSON.stringify(KEPT_NOTICES), { status: 200 })
        : new Response('', { status: 404 }),
    )
    const read = await readPublishedNotices(true, { online: true })
    expect(read.missing).toBe(false)
    expect(read.published?.items).toHaveLength(1)
  })

  it('is false with no hike planned, which downloads nothing', async () => {
    const read = await readPublishedNotices(false, { online: false })
    expect(read).toEqual({ published: null, listed: false, missing: false })
  })
})

describe('a request that never answers', () => {
  it('reads the HEAD about notices.json as not said once MANIFEST_READ_TIMEOUT_MS passes', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) =>
      unanswered(init),
    )
    let listed: boolean | undefined
    void noticesListed().then((answer) => {
      listed = answer
    })

    await vi.advanceTimersByTimeAsync(MANIFEST_READ_TIMEOUT_MS - 1)
    expect(listed).toBeUndefined()
    await vi.advanceTimersByTimeAsync(1)
    await vi.waitFor(() => expect(listed).toBe(false))
  })

  it('answers a planned hike’s read from the kept copy once NOTICES_DOWNLOAD_TIMEOUT_MS passes', async () => {
    await rememberPublished(PUBLISHED_NOTICES_KEY, KEPT_NOTICES)
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) =>
      unanswered(init),
    )
    let read: Awaited<ReturnType<typeof readPublishedNotices>> | undefined
    void readPublishedNotices(true, { online: true }).then((answer) => {
      read = answer
    })

    // A slow link is given the whole deadline to bring the file.
    await vi.advanceTimersByTimeAsync(NOTICES_DOWNLOAD_TIMEOUT_MS - 1)
    expect(read).toBeUndefined()
    await vi.advanceTimersByTimeAsync(1)
    await vi.waitFor(() =>
      expect(read?.published?.items.map((notice) => notice.notice_id)).toEqual([
        'club_page:footbridge',
      ]),
    )
    expect(read?.published?.generatedAt.toISOString()).toBe('2026-10-07T06:00:00.000Z')
  })

  it('says a planned hike’s notices are missing only once NOTICES_DOWNLOAD_TIMEOUT_MS passes with nothing kept', async () => {
    // The panel says nothing while the first download is in flight (the
    // maintainer's poll of 2026-10-09): `readPublishedNotices` has no answer
    // until the deadline aborts the request, and then it is "missing".
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) =>
      unanswered(init),
    )
    let read: Awaited<ReturnType<typeof readPublishedNotices>> | undefined
    void readPublishedNotices(true, { online: true }).then((answer) => {
      read = answer
    })

    await vi.advanceTimersByTimeAsync(NOTICES_DOWNLOAD_TIMEOUT_MS - 1)
    expect(read).toBeUndefined()
    await vi.advanceTimersByTimeAsync(1)
    await vi.waitFor(() => expect(read?.missing).toBe(true))
    expect(read?.published).toBeNull()
  })

  it('answers the hazard areas from the kept copy once MANIFEST_READ_TIMEOUT_MS passes', async () => {
    await rememberPublished(PUBLISHED_HAZARD_AREAS_KEY, KEPT_HAZARDS)
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) =>
      unanswered(init),
    )
    let hazards: Awaited<ReturnType<typeof fetchPublishedHazardAreas>> | undefined
    void fetchPublishedHazardAreas({ online: true }).then((answer) => {
      hazards = answer
    })

    await vi.advanceTimersByTimeAsync(MANIFEST_READ_TIMEOUT_MS - 1)
    expect(hazards).toBeUndefined()
    await vi.advanceTimersByTimeAsync(1)
    await vi.waitFor(() =>
      expect(hazards?.items.map((notice) => notice.notice_id)).toEqual([
        'oprhp_hunting_areas:1',
      ]),
    )
  })
})
