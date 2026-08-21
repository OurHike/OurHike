import { describe, it, expect, vi, afterEach } from 'vitest'
import { getAuthClient } from './supabase'
import { DEFAULT_PREFERENCES, PREFERENCE_KEYS } from './userPreferences'

// Preferences on the wire (#891). The harness is api.fieldNotePhoto.test.ts's,
// duplicated for the same documented reason: API_CONFIGURED is read at import
// time, so each of these files stubs the env and imports the module fresh.
//
// The two assertions here are the ones the endpoint's own history argues for.
// A 404 is a routine answer and must not throw, because a hiker who has never
// synced is not an error - and what is sent must be exactly the schema's keys
// and nothing else, because `extra="forbid"` turns one stray key into a 422
// for that hiker's every sync rather than a dropped field (#242).

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

function mockFetch(status: number, body: unknown = {}) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response)
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

describe('reading the account’s preferences', () => {
  it('answers null on a 404, because never-synced is not a failure', async () => {
    const { fetchSyncedPreferences } = await configuredApi()
    withSession('token')
    mockFetch(404)

    expect(await fetchSyncedPreferences()).toBeNull()
  })

  it('still throws on a real refusal', async () => {
    // 404 is the only status this endpoint reads as news. A 500 answered
    // with null would look to the reconciliation like an account with no
    // preferences, and it would push over one that has some.
    const { fetchSyncedPreferences, ApiError } = await configuredApi()
    withSession('token')
    mockFetch(500)

    await expect(fetchSyncedPreferences()).rejects.toThrow(ApiError)
  })

  it('refuses before spending a request when signed out', async () => {
    const { fetchSyncedPreferences, NotSignedInError } = await configuredApi()
    withSession(null)
    const fetchSpy = mockFetch(200)

    await expect(fetchSyncedPreferences()).rejects.toThrow(NotSignedInError)
    expect(fetchSpy).not.toHaveBeenCalled()
  })
})

describe('sending this device’s preferences', () => {
  it('sends exactly the keys the schema knows, and no others', async () => {
    // The #242 guard, at the wire. `extra="forbid"` means a stray key is a
    // 422 for every sync this hiker ever makes, wholesale.
    const { pushPreferences } = await configuredApi()
    withSession('token')
    const fetchSpy = mockFetch(200, { ...DEFAULT_PREFERENCES, updated_at: 'now' })

    await pushPreferences({
      ...DEFAULT_PREFERENCES,
      show_closures: true,
    } as never)

    const body = JSON.parse(
      (fetchSpy.mock.calls[0]?.[1]?.body as string) ?? '{}',
    ) as Record<string, unknown>
    expect(Object.keys(body).sort()).toEqual([...PREFERENCE_KEYS].sort())
  })

  it('PUTs, with the bearer token', async () => {
    const { pushPreferences } = await configuredApi()
    withSession('token')
    const fetchSpy = mockFetch(200, { ...DEFAULT_PREFERENCES, updated_at: 'now' })

    await pushPreferences(DEFAULT_PREFERENCES)

    const [url, init] = fetchSpy.mock.calls[0] ?? []
    expect(url).toBe('https://api.example.org/preferences/me')
    expect(init?.method).toBe('PUT')
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer token')
  })

  it('hands back the server’s stamp, which is the only place it exists', async () => {
    const { pushPreferences } = await configuredApi()
    withSession('token')
    mockFetch(200, { ...DEFAULT_PREFERENCES, updated_at: '2026-08-21T10:00:00Z' })

    expect((await pushPreferences(DEFAULT_PREFERENCES)).updated_at).toBe(
      '2026-08-21T10:00:00Z',
    )
  })
})
