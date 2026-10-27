// What a signed-in hiker's app sends on its conditions reads (#1916 - A
// signed-in hiker's app sends its token on the three edge-cached reads, so
// they either skip the cache or hide the hiker's own queued report).
//
// Held at the hook rather than only at the three fetchers in api.test.ts,
// because the hook is what decides which fetcher each read goes through: a
// later edit that read `/closures` through `readFetch` again would pass every
// test over there.

import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { getAuthClient } from './supabase'

vi.mock('./supabase', () => ({ getAuthClient: vi.fn() }))

const API = 'https://api.example.org'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
  vi.restoreAllMocks()
})

it('sends no token on /closures, /reports or /disputes when signed in, and asks /reports/mine with one', async () => {
  vi.mocked(getAuthClient).mockReturnValue({
    auth: {
      getSession: async () => ({ data: { session: { access_token: 'a-real-token' } } }),
    },
  } as unknown as ReturnType<typeof getAuthClient>)
  vi.stubEnv('VITE_API_BASE_URL', API)
  vi.resetModules()
  // The API answers its own paths; anything else this hook reads (the
  // published baselines) is "not there", which every one of them survives.
  const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'https://app.example.org')
    const mine = [{ id: 'mine-1', status: 'submitted' }]
    if (url.origin !== API)
      return { ok: false, status: 404, json: async () => null } as Response
    return {
      ok: true,
      status: 200,
      json: async () => (url.pathname === '/reports/mine' ? mine : []),
    } as Response
  })
  const { useConditions } = await import('./useConditions')

  const { result } = renderHook(() => useConditions(true))

  // The hiker's own waiting report is on the map, from /reports/mine.
  await waitFor(() =>
    expect(result.current.reports).toEqual([{ id: 'mine-1', status: 'submitted' }]),
  )
  await waitFor(() =>
    expect(fetchSpy.mock.calls.map(([input]) => String(input))).toEqual(
      expect.arrayContaining([`${API}/closures`, `${API}/disputes`]),
    ),
  )
  const authorization = (path: string) => {
    const call = fetchSpy.mock.calls.find(([input]) => String(input) === `${API}${path}`)
    expect(call, `no request to ${path}`).toBeDefined()
    const headers = (call?.[1] as RequestInit | undefined)?.headers as
      Record<string, string> | undefined
    return headers?.Authorization
  }
  expect(authorization('/closures')).toBeUndefined()
  expect(authorization('/reports')).toBeUndefined()
  expect(authorization('/disputes')).toBeUndefined()
  expect(authorization('/reports/mine')).toBe('Bearer a-real-token')
})
