import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  apiUrl,
  apiFetch,
  sendReport,
  accessToken,
  ApiNotConfiguredError,
  NotSignedInError,
  API_CONFIGURED,
} from './api'
import { getAuthClient } from './supabase'
import type { OutboxItem } from './outbox'

// #231: the app had no way to reach its own backend at all. These tests hold
// the two properties that make the difference between an outbox and a way to
// lose someone's report.
//
//  1. A non-2xx must THROW. `flushOutbox` tells sent from failed purely by
//     whether the send rejects, and `fetch` resolves happily on a 500 - so
//     without this a server error deletes a report from the queue and reports
//     success.
//  2. `authored_at` must travel. The server falls back to its own clock when
//     the field is missing, so dropping it produces plausible data rather than
//     a visible failure: every report written offline silently becomes fresh.

vi.mock('./supabase', () => ({ getAuthClient: vi.fn() }))

const mockedGetAuthClient = vi.mocked(getAuthClient)

/** A Supabase client stub that returns whatever session is asked for. */
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

const ITEM: OutboxItem = {
  id: 'outbox-1',
  authoredAt: '2026-06-01T08:30:00.000Z',
  payload: {
    type: 'blowdown',
    reporter_type: 'thru',
    note: 'Large tree across the trail.',
    lat: 35.6,
    lon: -83.5,
  },
}

beforeEach(() => {
  withSession('a-real-token')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('API_CONFIGURED', () => {
  it('is false in a test build, which has no backend URL', () => {
    // Guards the guard: every test below that expects ApiNotConfiguredError
    // depends on this being the default, and a stray .env would flip it.
    expect(API_CONFIGURED).toBe(false)
  })
})

describe('apiUrl', () => {
  it('joins a path whether or not it carries a leading slash', () => {
    expect(apiUrl('/reports')).toBe(apiUrl('reports'))
  })
})

describe('apiFetch', () => {
  it('refuses before spending a request when no backend is configured', async () => {
    const spy = mockFetch()

    await expect(apiFetch('/reports')).rejects.toBeInstanceOf(ApiNotConfiguredError)
    expect(spy).not.toHaveBeenCalled()
  })
})

describe('sendReport', () => {
  it('refuses when signed out, without spending a request', async () => {
    withSession(null)
    const spy = mockFetch()

    await expect(sendReport(ITEM)).rejects.toBeInstanceOf(NotSignedInError)
    expect(spy).not.toHaveBeenCalled()
  })

  it('refuses when this build has no backend', async () => {
    await expect(sendReport(ITEM)).rejects.toBeInstanceOf(ApiNotConfiguredError)
  })
})

// The behaviours above stop at the configuration guard, which is the honest
// thing for a build with no backend URL to do - but it means the request
// itself is never inspected. These reach past it, so the body and headers a
// real deployment would receive are actually asserted.
describe('the request a configured build sends', () => {
  /** Re-imports the module with a backend URL inlined, the way a real build
   *  has one. `import.meta.env` is stamped at build time, so this is the only
   *  way to exercise the configured path. */
  async function configured() {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.org/')
    vi.resetModules()
    return import('./api')
  }

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('strips a trailing slash from the base, so paths do not double up', async () => {
    const api = await configured()

    expect(api.apiUrl('/reports')).toBe('https://api.example.org/reports')
  })

  it('sends authored_at, so a report written Monday is not read as Thursday', async () => {
    const api = await configured()
    const spy = mockFetch()

    await api.sendReport(ITEM)

    const body = JSON.parse(String((spy.mock.calls[0][1] as RequestInit).body))
    expect(body.authored_at).toBe('2026-06-01T08:30:00.000Z')
  })

  it('sends the report itself alongside it', async () => {
    const api = await configured()
    const spy = mockFetch()

    await api.sendReport(ITEM)

    const body = JSON.parse(String((spy.mock.calls[0][1] as RequestInit).body))
    expect(body.type).toBe('blowdown')
    expect(body.reporter_type).toBe('thru')
    expect(body.note).toBe('Large tree across the trail.')
  })

  it('attaches the bearer token the backend verifies', async () => {
    const api = await configured()
    const spy = mockFetch()

    await api.sendReport(ITEM)

    const headers = (spy.mock.calls[0][1] as RequestInit).headers as Record<
      string,
      string
    >
    expect(headers.Authorization).toBe('Bearer a-real-token')
    expect(headers['Content-Type']).toBe('application/json')
  })

  // `api.ApiError`, not the one imported at the top of this file:
  // vi.resetModules() gives the re-imported module its own class objects, so
  // the top-level import is a different constructor that nothing here throws.
  it('throws on a 500 rather than resolving, so the report stays queued', async () => {
    const api = await configured()
    mockFetch(500)

    await expect(api.sendReport(ITEM)).rejects.toBeInstanceOf(api.ApiError)
  })

  it('throws on a 422 too - a refused report is not a sent one', async () => {
    const api = await configured()
    mockFetch(422)

    await expect(api.sendReport(ITEM)).rejects.toBeInstanceOf(api.ApiError)
  })

  it('carries the status, so a caller can tell 401 from 500', async () => {
    const api = await configured()
    mockFetch(401)

    await expect(api.sendReport(ITEM)).rejects.toMatchObject({ status: 401 })
  })

  it('resolves on a 201', async () => {
    const api = await configured()
    mockFetch(201)

    await expect(api.sendReport(ITEM)).resolves.toBeUndefined()
  })
})

describe('accessToken', () => {
  it('is null when this build has no Supabase project', async () => {
    mockedGetAuthClient.mockReturnValue(null)

    expect(await accessToken()).toBeNull()
  })

  it('is null when signed out', async () => {
    withSession(null)

    expect(await accessToken()).toBeNull()
  })
})
