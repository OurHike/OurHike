import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set } from 'idb-keyval'
import {
  SYNC_ENABLED_KEY,
  everythingIsSafe,
  setSyncEnabled,
  summariseSync,
  syncEnabled,
  type SyncStatus,
} from './syncStatus'
import { EMPTY_STORE, type Trip, type TripStore } from './trips'
import type { TripSyncState } from './tripSyncState'
import type { PreferencesSyncState } from './preferences'

// What a hiker is told about their own sync (#894).
//
// Every test here is a sentence this screen could get wrong, and the
// expensive direction is always the same one: saying everything is fine
// about a phone that has never sent anything. That is the impression
// silence already gives, so a screen that reproduces it has cost a round of
// work and bought nothing.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), update: vi.fn() }))

const store = new Map<string, unknown>()

const CLEAN_TRIPS: TripSyncState = {
  dirty: [],
  deleted: [],
  seen: {},
  since: null,
  hikeDirty: false,
  hikeSeen: null,
}
const CLEAN_PREFS: PreferencesSyncState = { dirty: false, syncedAt: null }

function trip(id: string, name: string): Trip {
  return { id, name, plan: { stops: [], days: [] } as never }
}

function storeWith(...trips: Trip[]): TripStore {
  return { ...EMPTY_STORE, trips }
}

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
})

describe('whether this device syncs', () => {
  it('is on for a hiker who has never touched it', async () => {
    // The safe direction: somebody who signed in did so to have their things
    // follow them, and defaulting to off would be this screen's own failure
    // mode - a confident "fine" over a phone that has never sent anything.
    expect(await syncEnabled()).toBe(true)
  })

  it('remembers being turned off', async () => {
    await setSyncEnabled(false)

    expect(await syncEnabled()).toBe(false)
    expect(store.get(SYNC_ENABLED_KEY)).toBe(false)
  })

  it('remembers being turned back on', async () => {
    await setSyncEnabled(false)
    await setSyncEnabled(true)

    expect(await syncEnabled()).toBe(true)
  })
})

describe('when the account was last reached', () => {
  it('says never, on a device that has not', () => {
    expect(summariseSync(EMPTY_STORE, CLEAN_TRIPS, CLEAN_PREFS).lastSyncedAt).toBeNull()
  })

  it('takes the later of the two exchanges', () => {
    // Preferences and trips are separate calls. Reporting the earlier one
    // would age the whole account by its quietest half.
    const status = summariseSync(
      EMPTY_STORE,
      { ...CLEAN_TRIPS, since: '2026-08-20T09:00:00Z' },
      { dirty: false, syncedAt: '2026-08-21T09:00:00Z' },
    )

    expect(status.lastSyncedAt?.toISOString()).toBe('2026-08-21T09:00:00.000Z')
  })

  it('answers from whichever half has run, when only one has', () => {
    const status = summariseSync(
      EMPTY_STORE,
      { ...CLEAN_TRIPS, since: '2026-08-20T09:00:00Z' },
      CLEAN_PREFS,
    )

    expect(status.lastSyncedAt?.toISOString()).toBe('2026-08-20T09:00:00.000Z')
  })

  it('reads an unparseable stamp as never rather than as an invalid date', () => {
    // An Invalid Date reaching syncAgeLabel renders "NaNd ago", which is
    // worse than "never synced" in the one way that matters: it is not a
    // sentence, so a hiker cannot act on it.
    const status = summariseSync(
      EMPTY_STORE,
      { ...CLEAN_TRIPS, since: 'yesterday' },
      CLEAN_PREFS,
    )

    expect(status.lastSyncedAt).toBeNull()
  })
})

describe('what is on this device only', () => {
  it('names a trip that has never reached the account', () => {
    const status = summariseSync(
      storeWith(trip('t1', 'Grayson Highlands')),
      CLEAN_TRIPS,
      CLEAN_PREFS,
    )

    expect(status.neverSent).toEqual(['Grayson Highlands'])
  })

  it('names them, rather than counting them', () => {
    // "3 items pending" tells a hiker nothing they can act on.
    const status = summariseSync(
      storeWith(trip('t1', 'Grayson'), trip('t2', 'Roan'), trip('t3', 'Katahdin')),
      CLEAN_TRIPS,
      CLEAN_PREFS,
    )

    expect(status.neverSent).toEqual(['Grayson', 'Katahdin', 'Roan'])
  })

  it('does not call a trip the account already holds "on this device only"', () => {
    const status = summariseSync(
      storeWith(trip('t1', 'Grayson')),
      {
        ...CLEAN_TRIPS,
        seen: { t1: '2026-08-20T09:00:00Z' },
      },
      CLEAN_PREFS,
    )

    expect(status.neverSent).toEqual([])
  })

  it('keeps unsent EDITS separate from trips that were never sent', () => {
    // Different sentences. A trip the account holds in an older form is
    // recoverable; one that has never been sent exists only here. Adding
    // them up would lose the distinction that decides whether to worry.
    const status = summariseSync(
      storeWith(trip('t1', 'Held by the account'), trip('t2', 'Only here')),
      { ...CLEAN_TRIPS, seen: { t1: '2026-08-20T09:00:00Z' }, dirty: ['t1', 't2'] },
      CLEAN_PREFS,
    )

    expect(status.unsentEdits).toEqual(['Held by the account'])
    expect(status.neverSent).toEqual(['Only here'])
  })

  it('does not warn twice about one trip', () => {
    const status = summariseSync(
      storeWith(trip('t1', 'Grayson')),
      {
        ...CLEAN_TRIPS,
        dirty: ['t1'],
      },
      CLEAN_PREFS,
    )

    expect(status.neverSent).toEqual(['Grayson'])
    expect(status.unsentEdits).toEqual([])
  })

  it('reports unsent settings and an unsent planned hike separately', () => {
    const status = summariseSync(
      EMPTY_STORE,
      { ...CLEAN_TRIPS, hikeDirty: true },
      { dirty: true, syncedAt: null },
    )

    expect(status.preferencesUnsent).toBe(true)
    expect(status.hikeUnsent).toBe(true)
  })
})

describe('whether everything is safe', () => {
  const safe: SyncStatus = {
    lastSyncedAt: new Date('2026-08-21T09:00:00Z'),
    neverSent: [],
    unsentEdits: [],
    preferencesUnsent: false,
    hikeUnsent: false,
  }

  it('is true when nothing anywhere is waiting', () => {
    expect(everythingIsSafe(safe)).toBe(true)
  })

  it.each([
    ['a trip that has never been sent', { neverSent: ['Grayson'] }],
    ['an unsent edit', { unsentEdits: ['Grayson'] }],
    ['unsent settings', { preferencesUnsent: true }],
    ['an unsent planned hike', { hikeUnsent: true }],
  ])('is false for %s', (_what, over) => {
    expect(everythingIsSafe({ ...safe, ...over })).toBe(false)
  })

  it('is true on a device with nothing to sync at all', () => {
    // A fresh install that has never synced has also never lost anything,
    // and telling it something is at risk would be inventing an alarm.
    expect(everythingIsSafe({ ...safe, lastSyncedAt: null })).toBe(true)
  })
})
