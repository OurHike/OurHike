import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get } from 'idb-keyval'

import { buildAccountArchive, archiveFilename, ARCHIVE_FORMAT } from './accountArchive'
import { ApiNotConfiguredError, NotSignedInError, fetchAccountExport } from './api'
import { OUTBOX_KEY } from './outbox'
import { DAY_HIKES_KEY } from './dayHikes'
import { TRIPS_KEY } from './trips'
import { WALKED_STORAGE_KEY } from './walkedMiles'

// The export half of #895 (ACCOUNT_SYNC.md phase E).
//
// The failure this file exists to prevent is an archive that looks complete
// and is short. Two ways it can be:
//
//   - the ACCOUNT half fails and the whole export becomes an error, losing
//     the device half - which is the part a hiker cannot get anywhere else,
//     and the part they most often want on a mountain with no signal; or
//   - the account half fails and the file says nothing about it, so a hiker
//     reads "no trips" as "the account had none" rather than as "we could
//     not ask".
//
// Both come out as `your_account_is_missing_because` being either wrong or
// absent, which is why nearly every test here reads that field.

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  setMany: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  fetchAccountExport: vi.fn(),
}))

const store = new Map<string, unknown>()
const NOW = new Date('2026-08-22T12:00:00Z')

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation(async (key: IDBValidKey) => store.get(String(key)))
  vi.mocked(fetchAccountExport).mockResolvedValue({ exported_for: 'me' })
  localStorage.clear()
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('the two halves', () => {
  it('keeps this device and the account apart', async () => {
    // Merging them would have to silently pick a winner where they disagree,
    // and would destroy the one comparison this file makes possible: what
    // syncing has actually achieved.
    const archive = await buildAccountArchive(NOW)

    expect(archive.this_device).toBeTruthy()
    expect(archive.your_account).toEqual({ exported_for: 'me' })
    expect(archive.your_account_is_missing_because).toBeNull()
  })

  it('carries the device stores the account never sees', async () => {
    // Walked miles and the outbox do not sync at all. An export that shipped
    // only the server's answer would be short by exactly these.
    store.set(OUTBOX_KEY, [{ id: 'queued-report' }])
    localStorage.setItem(
      WALKED_STORAGE_KEY,
      JSON.stringify([{ startMile: 1, endMile: 2 }]),
    )

    const archive = await buildAccountArchive(NOW)

    expect(archive.this_device.not_yet_sent).toEqual([{ id: 'queued-report' }])
    expect(archive.this_device.walked_miles).toEqual([{ startMile: 1, endMile: 2 }])
  })

  it('reads trips through their own loader', async () => {
    store.set(TRIPS_KEY, { trips: [] })

    const archive = await buildAccountArchive(NOW)

    expect(archive.this_device.trips).toEqual([])
  })

  it('carries every collection the hiker owns, not just the trips (#1040)', async () => {
    // "Everything of yours, in one file" is this module's first line, and it
    // was short by three: the hikes that group trips (#788), the groups a
    // hiker named themselves (#800), and every day hike (#976) - which is
    // where the coordinates somebody tapped live, and the most personal
    // thing in the store.
    store.set(TRIPS_KEY, {
      trips: [],
      openId: null,
      hikes: [
        {
          id: 'h1',
          name: 'My thru-hike',
          type: 'thru',
          start: { mile: 0, name: 'Springer' },
          end: { mile: 2197.4, name: 'Katahdin' },
          tripIds: [],
        },
      ],
      groups: [{ id: 'g1', name: 'Weekends', tripIds: [] }],
    })
    store.set(DAY_HIKES_KEY, {
      hikes: [
        {
          id: 'd1',
          name: 'Pine Meadow loop',
          date: null,
          segments: [
            [
              { coord: [-74.09, 41.25], poiId: null },
              { coord: [-74.08, 41.25], poiId: null },
            ],
          ],
          figures: { miles: 6.4, legs: [] },
          looped: false,
          recorded: 'planned',
        },
      ],
      openId: null,
    })

    const archive = await buildAccountArchive(NOW)

    expect(archive.this_device.hikes).toHaveLength(1)
    expect(archive.this_device.groups).toHaveLength(1)
    expect(archive.this_device.day_hikes).toHaveLength(1)
    // And the file says where each came from, so a reader is not guessing.
    const readFrom = archive.this_device.read_from as Record<string, string>
    expect(readFrom.day_hikes).toBe(DAY_HIKES_KEY)
  })

  it('stamps the format so a future reader knows what they hold', async () => {
    const archive = await buildAccountArchive(NOW)

    expect(archive.format).toBe(ARCHIVE_FORMAT)
    expect(archive.exported_at).toBe('2026-08-22T12:00:00.000Z')
  })
})

describe('when the account half cannot be fetched', () => {
  it('still hands over the device half', async () => {
    vi.mocked(fetchAccountExport).mockRejectedValue(new TypeError('offline'))
    store.set(OUTBOX_KEY, [{ id: 'queued-report' }])

    const archive = await buildAccountArchive(NOW)

    expect(archive.this_device.not_yet_sent).toEqual([{ id: 'queued-report' }])
    expect(archive.your_account).toBeNull()
  })

  it('says so in the file, in words rather than a status code', async () => {
    vi.mocked(fetchAccountExport).mockRejectedValue(new TypeError('offline'))

    const archive = await buildAccountArchive(NOW)

    expect(archive.your_account_is_missing_because).toMatch(/could not be reached/i)
  })

  it('distinguishes no backend from no signal', async () => {
    // Two different facts about this build, and a hiker reading the file
    // offline has no other way to tell them apart.
    vi.mocked(fetchAccountExport).mockRejectedValue(new ApiNotConfiguredError())

    const archive = await buildAccountArchive(NOW)

    expect(archive.your_account_is_missing_because).toMatch(/no server configured/i)
  })

  it('distinguishes signed out from both', async () => {
    vi.mocked(fetchAccountExport).mockRejectedValue(new NotSignedInError())

    const archive = await buildAccountArchive(NOW)

    expect(archive.your_account_is_missing_because).toMatch(/not signed in/i)
  })

  it('never rejects', async () => {
    // A hiker asked for their data. Losing the half we had in hand because
    // the other half failed is the wrong trade.
    vi.mocked(fetchAccountExport).mockRejectedValue(new Error('anything at all'))

    await expect(buildAccountArchive(NOW)).resolves.toBeTruthy()
  })
})

describe('the filename', () => {
  it('is dated, because a hiker exports more than once', () => {
    expect(archiveFilename(NOW)).toBe('ourhike-2026-08-22.json')
  })
})
