import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { get, set, update } from 'idb-keyval'

import { accountTag } from './accountTag'
import { apiFetch } from './api'
import { noteSignInStarted } from './signInMarker'
import type { TrailIndex } from './trailPosition'
import type { ClubRunLike } from './usageEvents'
import { EMPTY_USAGE, readUsage, type UsageStore } from './usageQueue'
import { type UsageMeasurementInput, useUsageMeasurement } from './useUsageMeasurement'

// The moments usage measurement records (#1902). Each test is one of them
// recording when it should and, as often the point, NOT recording when it
// should not: a restored session is not a sign-in, an old install is not a
// new one, and nothing at all is kept while "Share usage statistics" is off.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), update: vi.fn() }))
vi.mock('./api', () => ({
  accessToken: vi.fn(async () => 'token'),
  apiFetch: vi.fn(async () => new Response(null, { status: 202 })),
  API_CONFIGURED: true,
  ApiError: class ApiError extends Error {},
}))
vi.mock('./tracePlatform', () => ({ traceShell: () => 'web' }))
// Mile 1390 wherever the map is pointed: inside NYNJTC's run in RUNS below.
vi.mock('./trailPosition', () => ({ mileOnTrail: vi.fn(() => 1390) }))

let stored: unknown = undefined
beforeEach(() => {
  stored = undefined
  window.localStorage.clear()
  vi.mocked(get).mockImplementation(async () => stored)
  vi.mocked(set).mockImplementation(async (_key, value) => {
    stored = value
  })
  vi.mocked(update).mockImplementation(async (_key, updater) => {
    stored = updater(stored)
  })
  vi.mocked(apiFetch).mockClear()
})
afterEach(() => {
  vi.useRealTimers()
})

const RUNS: ClubRunLike[] = [
  { startMile: 1380, endMile: 1400, club: { acronym: 'NYNJTC' } },
  { startMile: 1400, endMile: 1450, club: { acronym: 'AMC-NY' } },
]

function input(overrides: Partial<UsageMeasurementInput> = {}): UsageMeasurementInput {
  return {
    ready: true,
    consentSettled: true,
    enabled: true,
    linked: null,
    accountEmail: null,
    newInstall: false,
    version: '1.4.0',
    online: false,
    reportsWaiting: 0,
    screen: 'today',
    mapInView: false,
    gps: { status: 'idle' },
    camera: null,
    trailIndex: null,
    clubRuns: RUNS,
    ...overrides,
  }
}

async function events(): Promise<string[]> {
  return (await readUsage()).rows.map((queued) => queued.row.event)
}

describe('first launch', () => {
  it('records app_installed for an install that had not finished first run', async () => {
    renderHook(() => useUsageMeasurement(input({ newInstall: true })))

    await waitFor(async () => expect(await events()).toContain('app_installed'))
  })

  it('does not count an install that finished first run before measurement existed as new', async () => {
    const { result } = renderHook(() => useUsageMeasurement(input({ newInstall: false })))
    await waitFor(() =>
      expect((stored as UsageStore | undefined)?.initialized).toBe(true),
    )

    result.current.planMade({ miles: 5 })

    await waitFor(async () => expect(await events()).toEqual(['hike_plan_made']))
    expect((await readUsage()).rows[0].row.ever_first).toBe(false)
  })
})

describe('while sharing is off', () => {
  it('records nothing at all', async () => {
    const { result } = renderHook(() =>
      useUsageMeasurement(input({ enabled: false, newInstall: true })),
    )

    result.current.planMade({ miles: 5 })

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(await events()).toEqual([])
  })

  it('empties what was waiting the moment it is switched off', async () => {
    const { result, rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      {
        initialProps: input(),
      },
    )
    result.current.planMade({ miles: 5 })
    await waitFor(async () => expect(await events()).toContain('hike_plan_made'))

    rerender(input({ enabled: false }))

    await waitFor(async () => expect(await events()).toEqual([]))
  })
})

describe('sign-in', () => {
  it('records one login, and asks the question, when a sign-in this app started finishes', async () => {
    noteSignInStarted()
    const onSignIn = vi.fn()

    renderHook(() =>
      useUsageMeasurement(input({ accountEmail: 'alice@example.org', onSignIn })),
    )

    await waitFor(async () => expect(await events()).toContain('user_login'))
    expect(onSignIn).toHaveBeenCalledTimes(1)
  })

  it('does not count an account restored at launch as a sign-in', async () => {
    const onSignIn = vi.fn()

    renderHook(() =>
      useUsageMeasurement(input({ accountEmail: 'alice@example.org', onSignIn })),
    )

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(await events()).not.toContain('user_login')
    expect(onSignIn).not.toHaveBeenCalled()
  })
})

describe('the map coming into view', () => {
  it('records one view per arrival, with the club at the map’s centre', async () => {
    const at = {
      trailIndex: {} as TrailIndex,
      camera: { center: [-74.1, 41.3] as const },
    }
    const { rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      { initialProps: input(at) },
    )

    rerender(input({ ...at, mapInView: true }))
    rerender(input({ ...at, mapInView: true, screen: 'map' }))

    await waitFor(async () => expect(await events()).toEqual(['map_screen_viewed']))
    expect((await readUsage()).rows[0].row.clubs).toEqual({ NYNJTC: 1 })
  })
})

describe('plans', () => {
  it('splits a plan across the clubs it crosses by its miles in each', async () => {
    const { result } = renderHook(() => useUsageMeasurement(input()))

    result.current.planMade({ fromMile: 1380, toMile: 1410 })

    await waitFor(async () => expect(await events()).toEqual(['hike_plan_made']))
    const row = (await readUsage()).rows[0].row
    expect(row.miles).toBe(30)
    expect(row.clubs?.NYNJTC).toBeCloseTo(2 / 3, 3)
    expect(row.club_firsts.sort()).toEqual(['AMC-NY', 'NYNJTC'])
  })

  it('links a row to the account only while the hiker said yes and is signed in', async () => {
    const { result } = renderHook(() =>
      useUsageMeasurement(input({ linked: true, accountEmail: 'alice@example.org' })),
    )

    result.current.planCompleted({ miles: 8 })

    await waitFor(async () => expect((await readUsage()).rows).toHaveLength(1))
    const [queued] = (await readUsage()).rows
    expect(queued.linkedTo).toBe(accountTag('alice@example.org'))
    expect(queued.row.signed_in).toBe(true)
  })

  it('unlinks what is waiting when a signed-in hiker says no', async () => {
    const { result, rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      { initialProps: input({ linked: true, accountEmail: 'alice@example.org' }) },
    )
    result.current.planMade({ miles: 4 })
    await waitFor(async () =>
      expect((await readUsage()).rows[0]?.linkedTo).toBe(accountTag('alice@example.org')),
    )

    rerender(input({ linked: false, accountEmail: 'alice@example.org' }))

    await waitFor(async () => expect((await readUsage()).rows[0]?.linkedTo).toBeNull())
    expect(await events()).toEqual(['hike_plan_made'])
  })

  it('unlinks what is waiting when the answer turns from yes, even with nobody signed in', async () => {
    const { result, rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      { initialProps: input({ linked: true, accountEmail: 'alice@example.org' }) },
    )
    result.current.planMade({ miles: 4 })
    await waitFor(async () =>
      expect((await readUsage()).rows[0]?.linkedTo).toBe(accountTag('alice@example.org')),
    )

    // Signed out: the row must not keep the tag of the account that left.
    rerender(input({ linked: true, accountEmail: null }))

    await waitFor(async () => expect((await readUsage()).rows[0]?.linkedTo).toBeNull())
  })

  it('records nothing once another tab switches sharing off, though this tab still holds on', async () => {
    const { result } = renderHook(() => useUsageMeasurement(input()))
    await waitFor(() => expect((stored as UsageStore | undefined)?.session).toBeTruthy())

    // The other tab's switch, as it reaches the store they share.
    stored = { ...(stored as UsageStore), rows: [], off: true }
    result.current.planMade({ miles: 4 })

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(await events()).toEqual([])
  })

  it('never throws into the hiker’s own save when a plan cannot be read', () => {
    const { result } = renderHook(() => useUsageMeasurement(input()))
    const unreadable = {
      get fromMile(): number {
        throw new Error('no extent')
      },
    }

    expect(() => result.current.planMade(unreadable)).not.toThrow()
  })
})

describe('sending', () => {
  it('sends what is waiting when the app is put away, not only every five minutes', async () => {
    // Online from the start, so the launch's own flush has already found an
    // empty queue by the time the plan below is recorded.
    const { result } = renderHook(() => useUsageMeasurement(input({ online: true })))
    result.current.planMade({ miles: 3 })
    await waitFor(async () => expect(await events()).toContain('hike_plan_made'))
    vi.mocked(apiFetch).mockClear()

    Object.defineProperty(document, 'visibilityState', {
      value: 'hidden',
      configurable: true,
    })
    document.dispatchEvent(new Event('visibilitychange'))

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/usage-events', expect.anything()),
    )
    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      configurable: true,
    })
  })

  it('waits while a hiker’s report is still queued, and sends once it is gone', async () => {
    const { result, rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      {
        initialProps: input({ online: true, reportsWaiting: 1 }),
      },
    )
    result.current.planMade({ miles: 3 })
    await waitFor(async () => expect(await events()).toEqual(['hike_plan_made']))
    expect(apiFetch).not.toHaveBeenCalled()

    rerender(input({ online: true, reportsWaiting: 0 }))

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/usage-events', expect.anything()),
    )
  })

  it('sends nothing for a signed-in launch until the account’s answers have arrived', async () => {
    const { result, rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      {
        initialProps: input({
          online: true,
          accountEmail: 'alice@example.org',
          consentSettled: false,
        }),
      },
    )
    result.current.planMade({ miles: 3 })
    await waitFor(async () => expect(await events()).toContain('hike_plan_made'))
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(apiFetch).not.toHaveBeenCalled()

    rerender(
      input({ online: true, accountEmail: 'alice@example.org', consentSettled: true }),
    )

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/usage-events', expect.anything()),
    )
  })
})

describe('visits', () => {
  it('continues a visit last seen within the idle gap when the app is launched again', async () => {
    const now = Date.now()
    stored = {
      ...EMPTY_USAGE,
      initialized: true,
      session: { startedAt: now - 60_000, lastSeenAt: now - 30_000, pageviews: 3 },
    }

    renderHook(() => useUsageMeasurement(input()))

    await waitFor(() => expect((stored as UsageStore).session?.pageviews).toBe(4))
    expect(await events()).toEqual([])
    expect((stored as UsageStore).session?.startedAt).toBe(now - 60_000)
  })

  it('ends a visit as the hiker it belonged to, not as whoever signed in since', async () => {
    const now = Date.now()
    stored = {
      ...EMPTY_USAGE,
      initialized: true,
      session: {
        startedAt: now - 3 * 60 * 60_000,
        lastSeenAt: now - 2 * 60 * 60_000,
        pageviews: 2,
        linkedTo: null,
        signedIn: false,
      },
    }

    renderHook(() =>
      useUsageMeasurement(input({ linked: true, accountEmail: 'alice@example.org' })),
    )

    await waitFor(async () => expect(await events()).toContain('session'))
    const visit = (await readUsage()).rows.find(
      (queued) => queued.row.event === 'session',
    )
    expect(visit?.linkedTo).toBeNull()
    expect(visit?.row.signed_in).toBe(false)
  })

  it('keeps the fix the map held during the visit for the visit’s row, with its club', async () => {
    const located: UsageMeasurementInput['gps'] = {
      status: 'located',
      at: { lon: -74.1, lat: 41.3 },
      accuracyFeet: 39,
      accuracyM: 12,
      fixedAt: new Date(),
    }
    const { rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      { initialProps: input({ trailIndex: {} as TrailIndex }) },
    )
    await waitFor(() => expect((stored as UsageStore | undefined)?.session).toBeTruthy())

    rerender(
      input({
        trailIndex: {} as TrailIndex,
        gps: located,
        screen: 'map',
      }),
    )

    await waitFor(() => expect((stored as UsageStore).session?.fix).toBeDefined())
    expect((stored as UsageStore).session?.clubs).toEqual({ NYNJTC: 1 })
  })
})
