// What a signed-in hiker's app sends on its conditions reads (#1916 - A
// signed-in hiker's app sends its token on the three edge-cached reads, so
// they either skip the cache or hide the hiker's own queued report).
//
// Held at the hook rather than only at the three fetchers in api.test.ts,
// because the hook is what decides which fetcher each read goes through: a
// later edit that read `/closures` through `readFetch` again would pass every
// test over there.

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { getAuthClient } from './supabase'

vi.mock('./supabase', () => ({ getAuthClient: vi.fn() }))

const API = 'https://api.example.org'

/** A verified serious warning on the shared list. */
const HAZARD = { id: 'hazard-1', status: 'verified', severity: 'serious' }
/** The hiker's own report, waiting for a moderator. */
const OWN = { id: 'own-1', status: 'submitted', severity: 'normal' }

/** Signs this phone in with `token`, or out with null, from the next read on. */
function signIn(token: string | null) {
  vi.mocked(getAuthClient).mockReturnValue({
    auth: {
      getSession: async () => ({
        data: { session: token === null ? null : { access_token: token } },
      }),
    },
  } as unknown as ReturnType<typeof getAuthClient>)
}

/** A JSON answer, shaped the way `apiFetch` reads one. */
function answer(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response
}

/**
 * Answers each API path in `routes` with what its function returns at the
 * moment of the request, and any other API path with `[]`. Anything else
 * this hook reads (the published baselines) is "not there", which every one
 * of them survives.
 */
function serve(routes: Record<string, () => Response | Promise<Response>>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'https://app.example.org')
    if (url.origin !== API) return answer(null, 404)
    return (routes[url.pathname] ?? (() => answer([])))()
  })
}

/** How many requests went to `path` on the API. */
function requestsTo(spy: ReturnType<typeof serve>, path: string) {
  return spy.mock.calls.filter(([input]) => String(input) === `${API}${path}`).length
}

/** `useConditions` from a module graph built with the API configured. */
async function configuredHook() {
  vi.stubEnv('VITE_API_BASE_URL', API)
  vi.resetModules()
  return (await import('./useConditions')).useConditions
}

/** Lets every API read already started settle. Each is a promise chain over
 *  the fetch above with no timer in it, so one macrotask turn drains it. */
async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
  vi.restoreAllMocks()
})

it('sends no token on /closures, /reports or /disputes when signed in, and asks /reports/mine with one', async () => {
  signIn('a-real-token')
  const useConditions = await configuredHook()
  const fetchSpy = serve({ '/reports/mine': () => answer([OWN]) })

  const { result } = renderHook(() => useConditions(true))

  // The hiker's own waiting report is on the map, from /reports/mine.
  await waitFor(() => expect(result.current.reports).toEqual([OWN]))
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

it('reports carries a /reports warning while /reports/mine has not answered, and keeps it when the phone goes offline first', async () => {
  // When fetchReports also read /reports/mine and awaited both, this warning
  // waited for the private read, and the hook's offline cleanup dropped it
  // with that read: the map kept showing the baseline.
  signIn('a-real-token')
  const useConditions = await configuredHook()
  let answerMine: (response: Response) => void = () => {}
  const spy = serve({
    '/reports': () => answer([HAZARD]),
    '/reports/mine': () => new Promise<Response>((resolve) => (answerMine = resolve)),
  })

  const { result, rerender } = renderHook(({ online }) => useConditions(online), {
    initialProps: { online: true },
  })
  await waitFor(() => expect(result.current.reports).toEqual([HAZARD]))
  await waitFor(() => expect(requestsTo(spy, '/reports/mine')).toBe(1))

  rerender({ online: false })
  await act(async () => answerMine(answer([OWN])))
  await settle()

  expect(result.current.reports).toEqual([HAZARD])
})

it("reports puts the hiker's own copy of a report in place of the shared copy, and their other reports after the shared list", async () => {
  // The shared copy is what a stranger may see of a report; the reporter's
  // own is the one `ReportOut.for_viewer` fills in for them.
  signIn('a-real-token')
  const useConditions = await configuredHook()
  serve({
    '/reports': () =>
      answer([
        { id: 'r1', reporter_id: null },
        { id: 'r2', reporter_id: null },
      ]),
    '/reports/mine': () =>
      answer([
        { id: 'own-1', reporter_id: 'p-1' },
        { id: 'r1', reporter_id: 'p-1' },
      ]),
  })

  const { result } = renderHook(() => useConditions(true))

  await waitFor(() =>
    expect(result.current.reports).toEqual([
      { id: 'r1', reporter_id: 'p-1' },
      { id: 'r2', reporter_id: null },
      { id: 'own-1', reporter_id: 'p-1' },
    ]),
  )
})
