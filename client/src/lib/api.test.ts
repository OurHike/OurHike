import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  apiUrl,
  apiFetch,
  sendReport,
  accessToken,
  fetchReports,
  fetchClosures,
  permanentFailureReason,
  ApiError,
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

// --- Telling a hiker their report will never send (#243) ------------------
//
// flushOutbox treated every failure the same, so a report the server would
// never accept sat in the queue saying "waiting to send" indefinitely -
// indistinguishable from one simply waiting for signal. The classifier is
// what makes those two different states.

describe('permanentFailureReason', () => {
  const apiError = (status: number) => new ApiError(status, `failed: ${status}`)

  it('names the clock, because that is the likeliest cause of a 422', async () => {
    // The server refuses an authored time more than five minutes ahead, so a
    // phone running fast has EVERY report refused - and that is fixable by
    // the person holding it, if anyone tells them.
    const reason = permanentFailureReason(apiError(422))

    expect(reason).toContain('clock')
  })

  it('reads as a sentence, not a status code', async () => {
    // It is rendered verbatim on the More screen.
    for (const status of [422, 409]) {
      const reason = permanentFailureReason(apiError(status))
      expect(reason).toMatch(/^[A-Z].*[.]$/s)
    }
  })

  it.each([400, 403, 413, 418, 451, 494])(
    'retries a %d rather than stranding the queue on it',
    async (status) => {
      // This assertion used to say the opposite, which is how the bug
      // shipped: every unrecognised 4xx marked the report permanently
      // refused. A captive portal, a WAF or a proxy answering 400/451/494
      // would strand the WHOLE queue, in exactly the network conditions this
      // app exists for - and it contradicted the function's own docstring.
      // Only the two statuses this backend really returns are permanent.
      expect(permanentFailureReason(apiError(status))).toBeNull()
    },
  )

  it('does not promise that fixing the clock sends this report now', async () => {
    // authored_at is never re-derived (a Monday report must still read as
    // Monday on Thursday), so a badly wrong clock leaves an already-queued
    // item unacceptable until real time catches up. "then try again" was a
    // promise the code cannot keep.
    const reason = permanentFailureReason(apiError(422)) ?? ''

    expect(reason).not.toMatch(/then try again/i)
    expect(reason).toMatch(/until that time has passed/i)
  })

  it.each([500, 502, 503])('retries a %d - the server may recover', async (status) => {
    expect(permanentFailureReason(apiError(status))).toBeNull()
  })

  it.each([
    [401, 'the token may refresh'],
    [408, 'a network symptom wearing a 4xx'],
    [429, 'explicitly later'],
  ])('retries a %d, because %s', async (status) => {
    expect(permanentFailureReason(apiError(status))).toBeNull()
  })

  it('retries a network failure, which is the normal case out here', async () => {
    expect(permanentFailureReason(new TypeError('Failed to fetch'))).toBeNull()
  })

  it('retries anything it does not recognise', async () => {
    // Keeping a report that might yet go is cheaper than stranding one that
    // would have.
    expect(permanentFailureReason('a string, somehow')).toBeNull()
    expect(permanentFailureReason(undefined)).toBeNull()
  })
})

describe('sendReport idempotency', () => {
  async function configuredApi() {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.org')
    vi.resetModules()
    return import('./api')
  }

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('sends the outbox id, so a lost response cannot duplicate the report', async () => {
    // The classic trail failure: the request commits, the connection drops
    // before the 201 arrives, the send throws, the item stays queued, and
    // the next flush files it again. The server keys off this to return the
    // stored report instead.
    const api = await configuredApi()
    const spy = mockFetch()

    await api.sendReport(ITEM)

    const body = JSON.parse(String((spy.mock.calls[0][1] as RequestInit).body))
    expect(body.id).toBe('outbox-1')
  })
})

// --- Reading the map (#286) ----------------------------------------------
//
// The client could post a report and never see one - its own included. Two
// properties matter more than the fetch itself.
//
//  1. The token goes WHEN THERE IS ONE, and is never required. Browsing has
//     never needed an account, but a reporter has to be able to see their own
//     unmoderated report, which is what "Waiting" on the More screen means.
//  2. A failed read THROWS. An empty list and a failed fetch draw the same
//     map and mean opposite things on the ground.

describe('reading reports and closures', () => {
  async function configuredApi() {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.org')
    vi.resetModules()
    return import('./api')
  }

  function mockJson(payload: unknown, status = 200) {
    return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => payload,
    } as Response)
  }

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('reads reports without an account', async () => {
    withSession(null)
    const api = await configuredApi()
    const spy = mockJson([{ id: 'r1' }])

    await expect(api.fetchReports()).resolves.toEqual([{ id: 'r1' }])

    const headers = (spy.mock.calls[0][1] as RequestInit).headers as Record<
      string,
      string
    >
    expect(headers.Authorization).toBeUndefined()
  })

  it('sends the token when there is one, so a reporter sees their own', async () => {
    withSession('a-real-token')
    const api = await configuredApi()
    const spy = mockJson([])

    await api.fetchReports()

    const headers = (spy.mock.calls[0][1] as RequestInit).headers as Record<
      string,
      string
    >
    expect(headers.Authorization).toBe('Bearer a-real-token')
  })

  it('reads closures anonymously too', async () => {
    withSession(null)
    const api = await configuredApi()
    const spy = mockJson([{ id: 'c1' }])

    await expect(api.fetchClosures()).resolves.toEqual([{ id: 'c1' }])
    expect(String(spy.mock.calls[0][0])).toBe('https://api.example.org/closures')
  })

  it.each([['fetchReports' as const], ['fetchClosures' as const]])(
    '%s throws on a failed read rather than returning an empty list',
    async (fn) => {
      // The rule this exists for: [] and "could not ask" draw the same map,
      // and the wrong one tells a hiker a closed stretch of trail is open.
      withSession(null)
      const api = await configuredApi()
      mockJson(null, 500)

      await expect(api[fn]()).rejects.toBeInstanceOf(api.ApiError)
    },
  )
})

describe('reading from a build with no backend', () => {
  it.each([[fetchReports], [fetchClosures]])(
    'throws rather than looking like an empty map',
    async (read) => {
      // Uses this file's own unconfigured module, so an absent backend cannot
      // be mistaken for a trail with nothing reported on it.
      withSession(null)

      await expect(read()).rejects.toBeInstanceOf(ApiNotConfiguredError)
    },
  )
})
