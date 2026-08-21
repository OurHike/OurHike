import { describe, it, expect, vi, afterEach } from 'vitest'
import { getAuthClient } from './supabase'
import type { OutboxItem } from './outbox'

// The outbox's sixth cargo (#832), on the wire. Two properties, both of
// which are about a closure being written where there is no signal:
//
//  1. **The id goes with it.** `POST /closures` takes it as an idempotency
//     key, so the flush that commits and loses its response costs a
//     duplicate request rather than a second closure over the same stretch.
//  2. **The authored time goes with it.** `reported_at` is what the closure
//     sheet ages a closure by, so a closure written on Monday and flushed on
//     Thursday must not arrive claiming to be three days fresher.

vi.mock('./supabase', () => ({ getAuthClient: vi.fn() }))

const mockedGetAuthClient = vi.mocked(getAuthClient)

async function configuredApi() {
  vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.org')
  vi.resetModules()
  return import('./api')
}

function withSession(token: string | null) {
  mockedGetAuthClient.mockReturnValue({
    auth: {
      getSession: async () => ({
        data: { session: token === null ? null : { access_token: token } },
      }),
    },
  } as unknown as ReturnType<typeof getAuthClient>)
}

function mockFetch(status = 201) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => ({}),
  } as Response)
}

function closureItem(over: Partial<OutboxItem> = {}): OutboxItem {
  return {
    id: 'outbox-closure-1',
    authoredAt: '2026-08-17T12:30:00.000Z',
    closure: {
      reason_type: 'storm_damage',
      note: 'Bridge is gone.',
      start_mile_marker: 1408.6,
      end_mile_marker: 1408.6,
      start_lat: 41.0,
      start_lon: -73.9,
      end_lat: 41.0,
      end_lon: -73.9,
    },
    ...over,
  }
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('sendOutboxItem with a closure', () => {
  it('posts it to /closures with its id and the day it was written', async () => {
    const api = await configuredApi()
    withSession('token-1')
    const fetchSpy = mockFetch()

    await api.sendOutboxItem(closureItem())

    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('https://api.example.org/closures')
    const body = JSON.parse(String(init.body))
    expect(body.id).toBe('outbox-closure-1')
    expect(body.reported_at).toBe('2026-08-17T12:30:00.000Z')
    expect(body.reason_type).toBe('storm_damage')
    // The geometry #674 added and nothing has ever written until now.
    expect([body.start_lat, body.start_lon]).toEqual([41.0, -73.9])
  })

  it('is not mistaken for a report by the dispatcher', async () => {
    const api = await configuredApi()
    withSession('token-1')
    const fetchSpy = mockFetch()

    await api.sendOutboxItem(closureItem())

    // The dispatcher's fall-through is `sendReport`, so a cargo it does not
    // know about does not error - it silently posts to /reports, where the
    // fields mean nothing and the closure is lost with a 2xx.
    expect(fetchSpy.mock.calls.every(([url]) => !String(url).endsWith('/reports'))).toBe(
      true,
    )
  })

  it('leaves the item queued when the send is refused', async () => {
    const api = await configuredApi()
    withSession('token-1')
    mockFetch(503)

    // Thrown, not swallowed: `flushOutbox` reads a throw as "still waiting",
    // which for a closure written at a washout is the ordinary outcome.
    await expect(api.sendOutboxItem(closureItem())).rejects.toBeInstanceOf(api.ApiError)
  })
})
