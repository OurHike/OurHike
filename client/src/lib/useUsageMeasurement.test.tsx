import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { get, set, update } from 'idb-keyval'

import { apiFetch } from './api'
import { noteSignInStarted } from './signInMarker'
import type { ClubRunLike } from './usageEvents'
import { readUsage, type UsageStore } from './usageQueue'
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
    enabled: true,
    linkedAccount: null,
    newInstall: false,
    signedIn: false,
    online: false,
    reportsWaiting: 0,
    screen: 'today',
    mapInView: false,
    heldFix: null,
    mapCentre: null,
    clubAtPoint: () => null,
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

    renderHook(() => useUsageMeasurement(input({ signedIn: true, onSignIn })))

    await waitFor(async () => expect(await events()).toContain('user_login'))
    expect(onSignIn).toHaveBeenCalledTimes(1)
  })

  it('does not count an account restored at launch as a sign-in', async () => {
    const onSignIn = vi.fn()

    renderHook(() => useUsageMeasurement(input({ signedIn: true, onSignIn })))

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(await events()).not.toContain('user_login')
    expect(onSignIn).not.toHaveBeenCalled()
  })
})

describe('the map coming into view', () => {
  it('records one view per arrival, with the club at the map’s centre', async () => {
    const clubAtPoint = vi.fn(() => 'NYNJTC')
    const { rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      {
        initialProps: input({ clubAtPoint, mapCentre: [-74.1, 41.3] }),
      },
    )

    rerender(input({ clubAtPoint, mapCentre: [-74.1, 41.3], mapInView: true }))
    rerender(
      input({ clubAtPoint, mapCentre: [-74.1, 41.3], mapInView: true, screen: 'map' }),
    )

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
      useUsageMeasurement(input({ linkedAccount: 'tag-alice', signedIn: true })),
    )

    result.current.planCompleted({ miles: 8 })

    await waitFor(async () => expect((await readUsage()).rows).toHaveLength(1))
    const [queued] = (await readUsage()).rows
    expect(queued.linkedTo).toBe('tag-alice')
    expect(queued.row.signed_in).toBe(true)
  })

  it('unlinks what is waiting when a signed-in hiker says no', async () => {
    const { result, rerender } = renderHook(
      (props: UsageMeasurementInput) => useUsageMeasurement(props),
      { initialProps: input({ linkedAccount: 'tag-alice', signedIn: true }) },
    )
    result.current.planMade({ miles: 4 })
    await waitFor(async () =>
      expect((await readUsage()).rows[0]?.linkedTo).toBe('tag-alice'),
    )

    rerender(input({ linkedAccount: null, signedIn: true }))

    await waitFor(async () => expect((await readUsage()).rows[0]?.linkedTo).toBeNull())
    expect(await events()).toEqual(['hike_plan_made'])
  })
})

describe('sending', () => {
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
})
