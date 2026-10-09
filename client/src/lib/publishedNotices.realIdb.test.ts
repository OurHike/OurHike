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

import 'fake-indexeddb/auto'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clear } from 'idb-keyval'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

import { recallPublished } from './conditionsCache'
import { PUBLISHED_NOTICES_KEY } from './publishedConditions'
import { readPublishedNotices } from './publishedNotices'

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

afterEach(async () => {
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
