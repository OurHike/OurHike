// What sign-out forgets, and what it must not (#1035).
//
// Its own file because these need an ACCOUNT — the sign-out button only
// exists once there is a session — and mocking `lib/useAuth` here keeps every
// other App test running as the signed-out hiker it was written for. That is
// App.identity.test.tsx's reason, applied to the other end of a session.
//
// WHAT THIS PINS, and why it is a wiring test rather than a unit one. Each
// `forget*Sync` already did the right thing in isolation; `forgetDayHikeSync`
// was written, exported, and never called from anywhere, and stayed that way
// for the whole life of the day-hike feature. A unit test of the function
// would have passed throughout. So the assertion here is on the App handler:
// every ledger is cleared, by name, and a test that adds a fourth store
// without wiring its ledger fails on the last case below.
//
// The other half matters as much: the hiker's own records STAY. Settings
// promises that in words ("signing out keeps the map, the outbox and the
// settings"), and a sign-out that quietly emptied somebody's saved walks
// would be this app taking a decision nobody asked of it.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, openMapTab } from './test/appHarness'
import { DAY_HIKES_SYNC_KEY } from './lib/dayHikeSyncState'
import { TRIPS_SYNC_KEY } from './lib/tripSyncState'
import { DAY_HIKES_KEY } from './lib/dayHikes'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./lib/useAuth', () => ({
  useAccount: () => ({ email: 'anna@example.org' }),
}))

const app = appHarness({ navigator: { onLine: true }, objectUrls: true })
const store = app.store

/** A ledger that says "this device has already synced with an account" -
 *  the claim that must not survive into somebody else's session. */
const SYNCED = {
  since: '2026-08-20T10:00:00Z',
  seen: { 'anna-1': '2026-08-20T10:00:00Z' },
  dirty: [],
  deleted: [],
}

/** One saved walk of Anna's, which is hers and stays on this phone. */
const DAY_HIKES = {
  hikes: [
    {
      id: 'anna-1',
      name: 'Pine Meadow loop',
      date: null,
      segments: [
        [
          { coord: [-74.095, 41.25], poiId: null },
          { coord: [-74.085, 41.25], poiId: null },
        ],
      ],
      figures: { miles: 6.4, legs: [] },
      looped: true,
      recorded: 'planned',
    },
  ],
  openId: null,
}

beforeEach(() => {
  app.onboard()
  app.putTrailData({ miles: 20 })
  store.set(TRIPS_SYNC_KEY, SYNCED)
  store.set(DAY_HIKES_SYNC_KEY, SYNCED)
  store.set(DAY_HIKES_KEY, DAY_HIKES)
})

async function signOut(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('tab', { name: 'More' }))
  await user.click(await screen.findByRole('button', { name: /^you/i }))
  await user.click(await screen.findByRole('button', { name: /sign out/i }))
}

/** Whether a ledger still claims to have synced with an account. Cleared is
 *  either the key being gone or its `since` being empty - `forgetDayHikeSync`
 *  writes the never-synced state rather than deleting, and both are honest
 *  answers to "have you synced?". */
function stillClaimsASync(key: string): boolean {
  const ledger = store.get(key) as { since?: string | null } | undefined
  if (ledger === undefined) return false
  return typeof ledger.since === 'string' && ledger.since.length > 0
}

describe('signing out on a shared handset', () => {
  it('forgets the day-hike ledger, which nothing used to clear (#1035)', async () => {
    const user = userEvent.setup()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await signOut(user)

    // The defect: this one was the only ledger with no call site, so Anna's
    // `since` and `seen` were still on the phone when Ben signed in - and the
    // next sync offered her walks to his account as ordinary edits.
    await waitFor(() => expect(stillClaimsASync(DAY_HIKES_SYNC_KEY)).toBe(false))
  })

  it('forgets the trip ledger too, which it always did', async () => {
    const user = userEvent.setup()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await signOut(user)

    await waitFor(() => expect(stillClaimsASync(TRIPS_SYNC_KEY)).toBe(false))
  })

  it('keeps the walks themselves - they are this phone’s, not the account’s', async () => {
    const user = userEvent.setup()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await signOut(user)

    await waitFor(() => expect(stillClaimsASync(DAY_HIKES_SYNC_KEY)).toBe(false))
    const kept = store.get(DAY_HIKES_KEY) as typeof DAY_HIKES | undefined
    expect(kept?.hikes).toHaveLength(1)
    expect(kept?.hikes[0].name).toBe('Pine Meadow loop')
  })

  it('leaves no ledger behind: every sync key is cleared, by name', async () => {
    // The case that catches the NEXT store to arrive with a ledger nobody
    // wired up. If a fifth key joins this list it has to be cleared here too,
    // and a test naming them one by one would not have said so.
    const user = userEvent.setup()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await signOut(user)

    const ledgers = [...store.keys()].filter((key) => key.endsWith(':sync'))
    await waitFor(() => {
      expect(ledgers.filter(stillClaimsASync)).toEqual([])
    })
  })
})
