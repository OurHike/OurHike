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

/** An app-failure report waiting in the outbox (#848). */
const FAILURE_ITEM: OutboxItem = {
  id: 'outbox-9',
  authoredAt: '2026-06-01T08:30:00.000Z',
  appFailure: {
    what_happened: 'The map went blank and would not come back.',
    whereabouts: 'the ford below Fontana',
    contact: 'sparrow@example.com',
    harms: ['lost'],
    build: 'OurHike 1.0.0 · commit 6e23f12 · built 2026-06-01 00:00 UTC',
    was_offline: true,
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

  // #412: the status alone cannot say WHY a 422 happened, and the two reasons
  // want opposite handling. Without the body reaching `permanentFailureReason`
  // there is nothing to classify on.
  it('carries the refusal body, so 422 can be told from 422', async () => {
    const api = await configured()
    const body = { detail: [{ loc: ['body', 'authored_at'], type: 'value_error' }] }
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => body,
    } as Response)

    await expect(api.sendReport(ITEM)).rejects.toMatchObject({ detail: body })
  })

  it('still throws when the refusal body is not JSON', async () => {
    // A proxy answering with HTML, or a connection that dies mid-read. The
    // parse failure must not replace a useful ApiError with a parse error -
    // the caller loses the detail and keeps the status.
    const api = await configured()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError('Unexpected token < in JSON at position 0')
      },
    } as unknown as Response)

    await expect(api.sendReport(ITEM)).rejects.toMatchObject({
      status: 502,
      detail: undefined,
    })
  })

  it('resolves on a 201', async () => {
    const api = await configured()
    mockFetch(201)

    await expect(api.sendReport(ITEM)).resolves.toBeUndefined()
  })
})

// The one write in the app that goes without an account (#848). Every
// assertion here is about that difference: the report a hiker files when the
// app failed them on the trail must not wait for a sign-in they may never do.
describe('sending an app-failure report', () => {
  async function configured() {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.org/')
    vi.resetModules()
    return import('./api')
  }

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('sends while signed out, rather than refusing the way a report does', async () => {
    withSession(null)
    const api = await configured()
    const spy = mockFetch()

    await api.sendAppFailure(FAILURE_ITEM)

    expect(spy).toHaveBeenCalledTimes(1)
    const headers = (spy.mock.calls[0][1] as RequestInit).headers as Record<
      string,
      string
    >
    expect(headers.Authorization).toBeUndefined()
  })

  it('attaches the token when there is one, so a reply has a second route', async () => {
    const api = await configured()
    const spy = mockFetch()

    await api.sendAppFailure(FAILURE_ITEM)

    const headers = (spy.mock.calls[0][1] as RequestInit).headers as Record<
      string,
      string
    >
    expect(headers.Authorization).toBe('Bearer a-real-token')
  })

  it('carries the report, the id and the time it was written', async () => {
    const api = await configured()
    const spy = mockFetch()

    await api.sendAppFailure(FAILURE_ITEM)

    const call = spy.mock.calls[0]
    expect(String(call[0])).toBe('https://api.example.org/app-failures')
    const body = JSON.parse(String((call[1] as RequestInit).body))
    expect(body.what_happened).toBe('The map went blank and would not come back.')
    expect(body.contact).toBe('sparrow@example.com')
    expect(body.harms).toEqual(['lost'])
    // The idempotency key, and the authored time - days old is the ordinary
    // case here, because the failure happens where there is no signal.
    expect(body.id).toBe('outbox-9')
    expect(body.authored_at).toBe('2026-06-01T08:30:00.000Z')
  })

  it('throws on a refusal, so the report stays queued', async () => {
    const api = await configured()
    mockFetch(500)

    await expect(api.sendAppFailure(FAILURE_ITEM)).rejects.toBeInstanceOf(api.ApiError)
  })

  it('is what sendOutboxItem picks for an item carrying one', async () => {
    // The dispatch, not the transport: an item with an appFailure must not
    // fall through to sendReport, which would POST it to /reports and be
    // refused for having no type.
    const api = await configured()
    const spy = mockFetch()

    await api.sendOutboxItem(FAILURE_ITEM)

    expect(String(spy.mock.calls[0][0])).toContain('/app-failures')
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
  const apiError = (status: number, detail?: unknown) =>
    new ApiError(status, `failed: ${status}`, detail)

  /** What FastAPI sends when the `authored_at` rule refuses a report. Its
   *  shape is pinned server-side by
   *  backend/tests/test_report_authored_at_contract.py. */
  const clockRefusal = {
    detail: [
      {
        type: 'value_error',
        loc: ['body', 'authored_at'],
        msg: 'Value error, authored_at cannot be in the future',
      },
    ],
  }

  /** What an older client's request looks like to a newer API: validation
   *  failing on a field that has nothing to do with the clock. */
  const skewRefusal = {
    detail: [
      {
        type: 'missing',
        loc: ['body', 'a_field_added_after_this_build'],
        msg: 'Field required',
      },
    ],
  }

  it('names the clock when the server named authored_at', async () => {
    // The server refuses an authored time more than five minutes ahead, so a
    // phone running fast has EVERY report refused - and that is fixable by
    // the person holding it, if anyone tells them.
    const reason = permanentFailureReason(apiError(422, clockRefusal))

    expect(reason).toContain('clock')
  })

  it('blames the app, not the clock, when some other field was refused', async () => {
    // #412: version skew and a wrong clock are both 422, and the clock
    // message sends somebody to check a setting that is fine - after six
    // months on trail, about a report they can no longer file.
    const reason = permanentFailureReason(apiError(422, skewRefusal)) ?? ''

    expect(reason).not.toMatch(/clock/i)
    expect(reason).toMatch(/too old/i)
    expect(reason).toMatch(/update/i)
  })

  it('promises the report is kept, because that is the fear', async () => {
    const reason = permanentFailureReason(apiError(422, skewRefusal)) ?? ''

    expect(reason).toMatch(/kept/i)
  })

  it('blames the app for a 422 with no readable body', async () => {
    // FastAPI always sends a JSON body for a validation failure, so a 422
    // without one came from something else - a proxy, a gateway. Attributing
    // that to the hiker's phone clock is a guess dressed as a diagnosis, and
    // the app-version message is the one that is harmless when wrong: it
    // keeps the report and asks for an update rather than accusing a setting.
    const reason = permanentFailureReason(apiError(422)) ?? ''

    expect(reason).not.toMatch(/clock/i)
    expect(reason).toMatch(/too old/i)
  })

  it('reads as a sentence, not a status code', async () => {
    // It is rendered verbatim on the More screen.
    for (const error of [
      apiError(422, clockRefusal),
      apiError(422, skewRefusal),
      apiError(409),
    ]) {
      const reason = permanentFailureReason(error)
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
    const reason = permanentFailureReason(apiError(422, clockRefusal)) ?? ''

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

  it('passes an abort signal through, so a screen leaving can drop its read', async () => {
    const api = await configuredApi()
    const spy = mockJson([])
    const controller = new AbortController()

    await api.fetchReports(controller.signal)

    expect((spy.mock.calls[0][1] as RequestInit).signal).toBe(controller.signal)
  })
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

// --- The photo, sent second (#234) ---------------------------------------
//
// `PUT /reports/{id}/photo` needs the row to exist, so the upload is a second
// request after the report lands. That makes `sendReport` two calls where it
// was one, and three properties decide whether that is safe:
//
//  1. It happens ONLY when there is a photo. Most reports have none, and a
//     wasted round trip out here is a wasted minute of radio.
//  2. A retryable failure keeps the whole item queued. The re-POST is
//     idempotent (#243), so re-sending costs a duplicate request rather than
//     a duplicate report - and the alternative loses the photo of every hiker
//     whose signal died between the two calls.
//  3. A refusal retrying cannot fix does NOT fail the item. The report is
//     already filed by then, and marking it unsendable would tell a hiker
//     their report is waiting while a moderator is already looking at it.

describe('sending a report that has a photo', () => {
  async function configuredApi() {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.org')
    vi.resetModules()
    return import('./api')
  }

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  const PHOTO = { size: 1234, type: 'image/jpeg' } as Blob
  const WITH_PHOTO: OutboxItem = { ...ITEM, photo: PHOTO }

  /** Answers the POST, then the PUT, with the statuses given in order. */
  function mockSequence(...statuses: number[]) {
    const spy = vi.spyOn(globalThis, 'fetch')
    for (const status of statuses) {
      spy.mockResolvedValueOnce({
        ok: status >= 200 && status < 300,
        status,
        json: async () => ({}),
      } as Response)
    }
    return spy
  }

  it('sends nothing extra for a report with no photo', async () => {
    const api = await configuredApi()
    const spy = mockSequence(201)

    await api.sendReport(ITEM)

    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('puts the bytes at the report it belongs to, after the report', async () => {
    const api = await configuredApi()
    const spy = mockSequence(201, 200)

    await api.sendReport(WITH_PHOTO)

    expect(spy).toHaveBeenCalledTimes(2)
    // Order matters and is the reason this is a sequence rather than two
    // independent assertions: the endpoint 404s if the row is not there yet.
    expect(spy.mock.calls[0][0]).toBe('https://api.example.org/reports')
    expect(spy.mock.calls[1][0]).toBe('https://api.example.org/reports/outbox-1/photo')

    const put = spy.mock.calls[1][1] as RequestInit
    expect(put.method).toBe('PUT')
    expect(put.body).toBe(PHOTO)
    const headers = put.headers as Record<string, string>
    // Stated explicitly rather than inherited from the Blob: the server
    // refuses anything that is not this, so it cannot be left to chance.
    expect(headers['Content-Type']).toBe('image/jpeg')
    expect(headers.Authorization).toBe('Bearer a-real-token')
  })

  it('does not attempt the photo when the report itself failed', async () => {
    // There would be no row to attach it to, and the 404 that came back
    // would look like a missing report rather than a failed send.
    const api = await configuredApi()
    const spy = mockSequence(500)

    await expect(api.sendReport(WITH_PHOTO)).rejects.toBeInstanceOf(api.ApiError)

    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('keeps the item queued when the photo upload is worth retrying', async () => {
    // The ordinary trail case: the report got through and the connection died
    // before the photo did. Throwing is what leaves it in the outbox.
    const api = await configuredApi()
    mockSequence(201, 500)

    await expect(api.sendReport(WITH_PHOTO)).rejects.toBeInstanceOf(api.ApiError)
  })

  it('keeps it queued when the server has no photo bucket yet', async () => {
    // 503 is "not configured on this deployment", which is precisely the
    // case worth waiting out - the photo becomes sendable when a bucket does.
    const api = await configuredApi()
    mockSequence(201, 503)

    await expect(api.sendReport(WITH_PHOTO)).rejects.toMatchObject({ status: 503 })
  })

  it.each([400, 413, 415])(
    'completes the item when the photo is refused permanently (%i)',
    async (status) => {
      // The report is filed. Failing the item over bytes the server will
      // never accept would strand it in "waiting to send" forever.
      const api = await configuredApi()
      mockSequence(201, status)

      await expect(api.sendReport(WITH_PHOTO)).resolves.toBeUndefined()
    },
  )

  it('refuses before spending the upload when signed out', async () => {
    const api = await configuredApi()
    withSession(null)
    const spy = mockSequence(201, 200)

    await expect(api.sendReport(WITH_PHOTO)).rejects.toBeInstanceOf(api.NotSignedInError)
    expect(spy).not.toHaveBeenCalled()
  })
})

// --- Moderation (#235) ----------------------------------------------------

describe('the moderation calls', () => {
  async function configuredApi() {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.org')
    vi.resetModules()
    return import('./api')
  }

  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  function mockOk(body: unknown = {}) {
    return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => body,
    } as Response)
  }

  it('reads the queue with the token, because the backend gates it on a role', async () => {
    const api = await configuredApi()
    const spy = mockOk({ reports: [], closures: [] })

    await api.fetchModerationQueue()

    expect(spy.mock.calls[0][0]).toBe('https://api.example.org/moderation/queue')
    const headers = (spy.mock.calls[0][1] as RequestInit).headers as Record<
      string,
      string
    >
    expect(headers.Authorization).toBe('Bearer a-real-token')
  })

  it('THROWS on a failed queue read rather than answering with an empty queue', async () => {
    // The property this whole screen rests on: "nothing is waiting" and "I
    // could not ask" must not be the same value.
    const api = await configuredApi()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as Response)

    await expect(api.fetchModerationQueue()).rejects.toBeInstanceOf(api.ApiError)
  })

  it('omits severity entirely when the moderator did not choose one', async () => {
    // #251. An absent field means "said nothing"; `normal` means
    // "de-escalate", and the two must not be the same request.
    const api = await configuredApi()
    const spy = mockOk()

    await api.verifyReport('r-1')

    expect(JSON.parse(String((spy.mock.calls[0][1] as RequestInit).body))).toEqual({})
  })

  it('sends severity when one was chosen', async () => {
    const api = await configuredApi()
    const spy = mockOk()

    await api.verifyReport('r-1', 'serious')

    expect(JSON.parse(String((spy.mock.calls[0][1] as RequestInit).body))).toEqual({
      severity: 'serious',
    })
  })

  it('reads the signed-in profile, which is where a role comes from', async () => {
    const api = await configuredApi()
    const spy = mockOk({ id: 'p-1', role: 'maintainer', display_name: null })

    const profile = await api.fetchMyProfile()

    expect(spy.mock.calls[0][0]).toBe('https://api.example.org/profiles/me')
    expect(profile.role).toBe('maintainer')
  })

  it('refuses to ask who you are when signed out, rather than guessing', async () => {
    const api = await configuredApi()
    withSession(null)
    const spy = mockOk()

    await expect(api.fetchMyProfile()).rejects.toBeInstanceOf(api.NotSignedInError)
    expect(spy).not.toHaveBeenCalled()
  })

  it('asks for a photo URL WITH the token, which is the whole point (#385)', async () => {
    // An `<img>` cannot carry an `Authorization` header, so pointing one at
    // the photo endpoint sends an anonymous request and gets the public
    // answer - a 404 for an `internal_only` photo, rendered as a broken
    // image. The token going on THIS call is what makes the URL it returns
    // one the moderator is actually entitled to.
    const api = await configuredApi()
    const spy = mockOk({ url: 'https://photos.example/signed', expires_in: 300 })

    const link = await api.fetchReportPhotoLink('r-1')

    expect(spy.mock.calls[0][0]).toBe('https://api.example.org/reports/r-1/photo/link')
    const headers = (spy.mock.calls[0][1] as RequestInit).headers as Record<
      string,
      string
    >
    expect(headers.Authorization).toBe('Bearer a-real-token')
    expect(link).toEqual({ url: 'https://photos.example/signed', expiresIn: 300 })
  })

  it('still asks when signed out, because a public photo needs no account', async () => {
    // `readFetch`, not `authedFetch`: browsing has never needed an account
    // here, and the endpoint answers an anonymous caller for a public report.
    const api = await configuredApi()
    withSession(null)
    const spy = mockOk({ url: 'https://photos.example/signed', expires_in: 300 })

    await api.fetchReportPhotoLink('r-1')

    expect(spy).toHaveBeenCalled()
    expect((spy.mock.calls[0][1] as RequestInit).headers).toEqual({})
  })

  it('THROWS on a refused photo rather than returning nothing to draw', async () => {
    // A resolved "no URL" would be indistinguishable from a report with no
    // photo, which is the exact confusion #385 exists to end.
    const api = await configuredApi()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({}),
    } as Response)

    await expect(api.fetchReportPhotoLink('r-1')).rejects.toBeInstanceOf(api.ApiError)
  })
})
