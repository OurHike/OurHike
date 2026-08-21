import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set, del } from 'idb-keyval'
import { syncTrips, type TripSyncRequest, type TripSyncResponse } from './api'
import { syncTripsWithAccount } from './tripsSync'
import { addTrip, loadTrips, renameTrip, removeTrip, saveTrips } from './trips'
import { buildPlan, type HikePlan } from './plan'

// #892's own acceptance test: "edit on A offline, edit on B offline,
// reconcile, assert BOTH survive and neither is silently rewritten."
//
// Two devices, each with its own IndexedDB, against ONE fake server that
// implements the same rule `backend/app/core/trip_sync.py` does. The
// backend's copy is tested directly in tests/test_core_trip_sync.py and end
// to end in tests/test_routers_synced_trips.py; what this file exists to
// prove is the half those cannot see - that the CLIENT offers the right
// `base_updated_at`, applies what comes back, and does not lose the local
// edit on the way.
//
// The fake server is deliberately small and deliberately not imported from
// anywhere: a client test that drove the real Python would be an integration
// suite this repository does not have, and a client test that mocked the
// answer it wanted would prove nothing about the exchange.

vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  syncTrips: vi.fn(),
}))

function makePlan(): HikePlan {
  return buildPlan(
    [
      { mile: 470.8, name: 'Damascus', resupply: false },
      { mile: 503.3, name: 'Atkins', resupply: false },
    ],
    { walkingHours: 7 },
  )
}

/** One device's IndexedDB. Swapping which Map the mocks read is what makes
 *  two devices possible in one process. */
class Device {
  readonly storage = new Map<string, unknown>()
}

let current: Device

/** The server, as far as these two devices can tell. Implements exactly the
 *  rule the backend does, including keeping both on a conflict. */
class FakeAccount {
  rows = new Map<
    string,
    { document: unknown; updated_at: string; deleted_at: string | null }
  >()
  private tick = 0
  copies = 0

  private now(): string {
    this.tick += 1
    return `2026-08-21T12:00:${String(this.tick).padStart(2, '0')}Z`
  }

  handle(request: TripSyncRequest): TripSyncResponse {
    const at = this.now()
    for (const upload of request.trips) {
      const stored = this.rows.get(upload.id)
      const clean = stored === undefined || upload.base_updated_at === stored.updated_at

      if (clean) {
        this.rows.set(upload.id, {
          document: upload.document,
          updated_at: at,
          deleted_at: upload.deleted ? at : (stored?.deleted_at ?? null),
        })
        continue
      }
      if (upload.deleted && stored.deleted_at !== null) continue

      // Keep both: the stored row is untouched, and what this device holds
      // lands beside it under a new id.
      this.copies += 1
      const kept = upload.deleted ? stored.document : upload.document
      const name = `${(kept as { name: string }).name} (edited on another device, 2026-08-21)`
      if (upload.deleted) {
        this.rows.set(upload.id, { document: null, updated_at: at, deleted_at: at })
      }
      this.rows.set(`copy-${this.copies}`, {
        document: { ...(kept as object), id: `copy-${this.copies}`, name },
        updated_at: at,
        deleted_at: null,
      })
    }

    const after = this.now()
    return {
      now: after,
      trips: [...this.rows.entries()]
        .filter(([, row]) => request.since === null || row.updated_at > request.since)
        .map(([id, row]) => ({ id, ...row })),
      hike: null,
      conflicts: this.copies,
    }
  }
}

let account: FakeAccount

async function on<T>(device: Device, work: () => Promise<T>): Promise<T> {
  current = device
  return work()
}

beforeEach(() => {
  account = new FakeAccount()
  vi.mocked(get).mockImplementation((key) =>
    Promise.resolve(current.storage.get(key as string)),
  )
  vi.mocked(set).mockImplementation((key, value) => {
    current.storage.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(del).mockImplementation((key) => {
    current.storage.delete(key as string)
    return Promise.resolve()
  })
  vi.mocked(syncTrips).mockImplementation(async (request) => account.handle(request))
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('a laptop and a phone', () => {
  it('carries a plan made on one to the other', async () => {
    // The feature, in one test. Until #892 the laptop's plan did not exist
    // on the phone in any form.
    const laptop = new Device()
    const phone = new Device()

    await on(laptop, async () => {
      await saveTrips(addTrip(await loadTrips(), makePlan(), 'Grayson Highlands'))
      await syncTripsWithAccount()
    })
    await on(phone, () => syncTripsWithAccount())

    const arrived = await on(phone, loadTrips)
    expect(arrived.trips.map((trip) => trip.name)).toEqual(['Grayson Highlands'])
  })

  it('keeps both when each edits the same trip offline', async () => {
    const laptop = new Device()
    const phone = new Device()

    // Both devices start level, holding the same trip.
    await on(laptop, async () => {
      await saveTrips(addTrip(await loadTrips(), makePlan(), 'Grayson Highlands'))
      await syncTripsWithAccount()
    })
    await on(phone, () => syncTripsWithAccount())
    const id = (await on(phone, loadTrips)).trips[0].id

    // Both go offline and edit. Neither has heard from the other.
    await on(laptop, async () =>
      saveTrips(renameTrip(await loadTrips(), id, 'Grayson Highlands, four days')),
    )
    await on(phone, async () =>
      saveTrips(renameTrip(await loadTrips(), id, 'Grayson Highlands, three days')),
    )

    // Both come back.
    await on(laptop, () => syncTripsWithAccount())
    await on(phone, () => syncTripsWithAccount())
    await on(laptop, () => syncTripsWithAccount())

    const names = (await on(laptop, loadTrips)).trips.map((trip) => trip.name).sort()
    expect(names).toHaveLength(2)
    expect(names.some((name) => name.includes('four days'))).toBe(true)
    expect(names.some((name) => name.includes('three days'))).toBe(true)
  })

  it('carries a delete made on one device to the other', async () => {
    const laptop = new Device()
    const phone = new Device()

    await on(laptop, async () => {
      await saveTrips(addTrip(await loadTrips(), makePlan(), 'Grayson Highlands'))
      await syncTripsWithAccount()
    })
    await on(phone, () => syncTripsWithAccount())
    const id = (await on(phone, loadTrips)).trips[0].id

    await on(laptop, async () => {
      await saveTrips(removeTrip(await loadTrips(), id))
      await syncTripsWithAccount()
    })
    await on(phone, () => syncTripsWithAccount())

    expect((await on(phone, loadTrips)).trips).toEqual([])
  })

  it('does not resurrect a deleted trip on the next sync', async () => {
    // The failure this would look like: the delete travels, and then the
    // OTHER device - which still had the trip when it last synced - offers
    // it back as an edit and the hiker's delete is undone.
    const laptop = new Device()
    const phone = new Device()

    await on(laptop, async () => {
      await saveTrips(addTrip(await loadTrips(), makePlan(), 'Grayson Highlands'))
      await syncTripsWithAccount()
    })
    await on(phone, () => syncTripsWithAccount())
    const id = (await on(phone, loadTrips)).trips[0].id

    await on(phone, async () => {
      await saveTrips(removeTrip(await loadTrips(), id))
      await syncTripsWithAccount()
    })

    await on(laptop, () => syncTripsWithAccount())
    await on(phone, () => syncTripsWithAccount())

    expect((await on(laptop, loadTrips)).trips).toEqual([])
    expect((await on(phone, loadTrips)).trips).toEqual([])
  })

  it('settles: a third sync round changes nothing on either device', async () => {
    // Convergence, which is the property a delta protocol can lose without
    // any single step looking wrong.
    const laptop = new Device()
    const phone = new Device()

    await on(laptop, async () => {
      await saveTrips(addTrip(await loadTrips(), makePlan(), 'One'))
      await syncTripsWithAccount()
    })
    await on(phone, async () => {
      await syncTripsWithAccount()
      await saveTrips(addTrip(await loadTrips(), makePlan(), 'Two'))
      await syncTripsWithAccount()
    })
    await on(laptop, () => syncTripsWithAccount())

    const before = (await on(laptop, loadTrips)).trips.map((t) => t.name).sort()
    expect(await on(laptop, () => syncTripsWithAccount())).toBeNull()
    expect(await on(phone, () => syncTripsWithAccount())).toBeNull()

    expect((await on(laptop, loadTrips)).trips.map((t) => t.name).sort()).toEqual(before)
    expect(before).toEqual(['One', 'Two'])
  })
})
