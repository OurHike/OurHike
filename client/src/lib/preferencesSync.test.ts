import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { get, set } from 'idb-keyval'
import {
  planPreferencesSync,
  pushPreferencesIfChanged,
  syncPreferences,
} from './preferencesSync'
import {
  loadPreferences,
  preferencesSyncState,
  recordPreferencesPush,
  savePreferences,
} from './preferences'
import { ApiError, ApiNotConfiguredError, NotSignedInError } from './api'

import { fetchSyncedPreferences, pushPreferences } from './api'
import { DEFAULT_PREFERENCES } from './userPreferences'

// Preferences following the account (#891).
//
// The rule is four lines of code and the reason it is worth this many tests
// is that three of its branches are only ever exercised on somebody's second
// device - which is exactly the situation nobody develops in. The one that
// matters most is the FIRST sync: a device that has never synced pulls even
// when it has local changes, because signing in is a hiker asking for their
// account's settings, and getting that backwards means a hiker who onboards
// on a new phone overwrites their own account with the defaults they just
// clicked through.

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), update: vi.fn() }))
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  fetchSyncedPreferences: vi.fn(),
  pushPreferences: vi.fn(),
}))

const store = new Map<string, unknown>()

const REMOTE_AT = '2026-08-21T10:00:00Z'
const LATER_AT = '2026-08-21T11:00:00Z'

function synced(over: Record<string, unknown> = {}) {
  return { ...DEFAULT_PREFERENCES, updated_at: REMOTE_AT, ...over }
}

// One console spy for the whole file, cleared per test. `vi.spyOn` on an
// already-spied method hands back the SAME mock with its calls still on it,
// so installing it per test is how a later assertion ends up reading an
// earlier test's output.
let logged: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  store.clear()
  logged = vi.spyOn(console, 'error').mockImplementation(() => {})
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(fetchSyncedPreferences).mockReset()
  vi.mocked(pushPreferences).mockReset()
  vi.mocked(pushPreferences).mockResolvedValue(synced({ updated_at: LATER_AT }))
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the rule', () => {
  it('pushes when the account has no preferences yet', () => {
    // Nothing to overwrite, and until some device establishes the row every
    // other device's first sync has nothing to adopt.
    expect(planPreferencesSync(null, { dirty: false, syncedAt: null })).toBe('push')
  })

  it('pulls on a device that has never synced, even holding local changes', () => {
    // #891's opening case, and the one that is easy to get backwards.
    expect(planPreferencesSync(REMOTE_AT, { dirty: true, syncedAt: null })).toBe('pull')
  })

  it('pushes a local change', () => {
    expect(planPreferencesSync(REMOTE_AT, { dirty: true, syncedAt: REMOTE_AT })).toBe(
      'push',
    )
  })

  it('pushes when BOTH moved, resolving toward the device in the hand', () => {
    // The one case the bookkeeping genuinely cannot separate. It resolves
    // toward the phone whose settings the hiker can see being wrong.
    expect(planPreferencesSync(LATER_AT, { dirty: true, syncedAt: REMOTE_AT })).toBe(
      'push',
    )
  })

  it('pulls when the account moved and this device did not', () => {
    expect(planPreferencesSync(LATER_AT, { dirty: false, syncedAt: REMOTE_AT })).toBe(
      'pull',
    )
  })

  it('spends no request when neither side moved', () => {
    // The ordinary launch. An `idle` that answered `push` would mean a PUT
    // every time the app opens, for nothing.
    expect(planPreferencesSync(REMOTE_AT, { dirty: false, syncedAt: REMOTE_AT })).toBe(
      'idle',
    )
  })
})

describe('reconciling for real', () => {
  it('hands back the account’s preferences on a first sign-in', async () => {
    vi.mocked(fetchSyncedPreferences).mockResolvedValue(synced({ theme: 'dark' }))

    const adopted = await syncPreferences(DEFAULT_PREFERENCES)

    expect(adopted?.theme).toBe('dark')
    expect(await preferencesSyncState()).toEqual({ dirty: false, syncedAt: REMOTE_AT })
    expect(pushPreferences).not.toHaveBeenCalled()
  })

  it('repairs what the account sends before adopting it', async () => {
    // A blob written by a build that offered a background this one does not.
    // Arriving over TLS does not make it renderable.
    vi.mocked(fetchSyncedPreferences).mockResolvedValue(
      synced({ background_source: 'osm_styled_live' }),
    )

    const adopted = await syncPreferences(DEFAULT_PREFERENCES)

    expect(adopted?.background_source).toBe(DEFAULT_PREFERENCES.background_source)
  })

  it('never hands `updated_at` back into the app’s preferences', async () => {
    // It would be pushed straight back as an invented key, which is a 422
    // for every one of this hiker's syncs (#242).
    vi.mocked(fetchSyncedPreferences).mockResolvedValue(synced())

    expect(await syncPreferences(DEFAULT_PREFERENCES)).not.toHaveProperty('updated_at')
  })

  it('establishes the row when the account has none', async () => {
    vi.mocked(fetchSyncedPreferences).mockResolvedValue(null)

    const adopted = await syncPreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    expect(adopted).toBeNull()
    expect(pushPreferences).toHaveBeenCalledWith(
      expect.objectContaining({ theme: 'dark' }),
    )
    expect((await preferencesSyncState()).syncedAt).toBe(LATER_AT)
  })

  it('adopts nothing and sends nothing on a launch where neither side moved', async () => {
    await recordPreferencesPush(REMOTE_AT)
    vi.mocked(fetchSyncedPreferences).mockResolvedValue(synced())

    expect(await syncPreferences(DEFAULT_PREFERENCES)).toBeNull()
    expect(pushPreferences).not.toHaveBeenCalled()
  })

  it('does not push back what it just pulled', async () => {
    // The infinite-loop guard, end to end: an adopt clears dirty, so the
    // next reconciliation finds nothing to send.
    vi.mocked(fetchSyncedPreferences).mockResolvedValue(synced({ theme: 'dark' }))
    await syncPreferences(DEFAULT_PREFERENCES)

    await syncPreferences(DEFAULT_PREFERENCES)

    expect(pushPreferences).not.toHaveBeenCalled()
  })
})

describe('the three silences', () => {
  // An unconfigured build, a signed-out hiker and a device with no signal are
  // the ordinary conditions this app is designed around. None of them is a
  // fault, and none may disturb the bookkeeping.

  it('is a no-op when the build has no backend', async () => {
    vi.mocked(fetchSyncedPreferences).mockRejectedValue(new ApiNotConfiguredError())

    expect(await syncPreferences(DEFAULT_PREFERENCES)).toBeNull()
  })

  it('is a no-op when nobody is signed in', async () => {
    vi.mocked(fetchSyncedPreferences).mockRejectedValue(new NotSignedInError())

    expect(await syncPreferences(DEFAULT_PREFERENCES)).toBeNull()
  })

  it('is a no-op with no signal, and stays dirty so the next launch retries', async () => {
    await recordPreferencesPush(REMOTE_AT)
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })
    vi.mocked(fetchSyncedPreferences).mockResolvedValue(synced())
    vi.mocked(pushPreferences).mockRejectedValue(new TypeError('Failed to fetch'))

    expect(await syncPreferences(DEFAULT_PREFERENCES)).toBeNull()
    expect((await preferencesSyncState()).dirty).toBe(true)
  })

  it('says a 422 out loud, because that is the one bug this endpoint has had', async () => {
    // #242: the client sending a key the schema forbids, wholesale, for every
    // hiker on their first sync. Silent would make it invisible twice.
    vi.mocked(fetchSyncedPreferences).mockRejectedValue(
      new ApiError(422, 'PUT /preferences/me failed: 422'),
    )

    await syncPreferences(DEFAULT_PREFERENCES)

    // The message names the guard that should have caught it before release,
    // because the reader who can act on this is not the hiker.
    expect(logged.mock.calls[0]?.[0]).toMatch(/test_preferences_contract\.py/)
  })

  it('never rejects, whatever went wrong', async () => {
    // The defect the first draft shipped: every caller is a background
    // effect, so a throw here became `void promise` with nothing to catch it.
    // An unhandled rejection is QUIETER than a log, while reading in the
    // source like the error was being taken seriously.
    vi.mocked(fetchSyncedPreferences).mockRejectedValue(new ApiError(500, 'boom'))

    await expect(syncPreferences(DEFAULT_PREFERENCES)).resolves.toBeNull()
  })

  it('classifies an error without touching the api module’s exports', async () => {
    // Ten App.*.test.tsx files partially mock ./lib/api, and reading a class
    // off such a mock throws - inside the handler for the error being
    // classified, which is how one failure became two. Matching on `name` is
    // what makes that impossible.
    const fromAPartialMock = new Error('signed out')
    fromAPartialMock.name = 'NotSignedInError'
    vi.mocked(fetchSyncedPreferences).mockRejectedValue(fromAPartialMock)

    await syncPreferences(DEFAULT_PREFERENCES)

    expect(logged).not.toHaveBeenCalled()
  })
})

describe('pushing on change', () => {
  it('spends nothing when this device has changed nothing', async () => {
    await recordPreferencesPush(REMOTE_AT)

    await pushPreferencesIfChanged(DEFAULT_PREFERENCES)

    expect(pushPreferences).not.toHaveBeenCalled()
    expect(fetchSyncedPreferences).not.toHaveBeenCalled()
  })

  it('sends the change and records that this device is level again', async () => {
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    await pushPreferencesIfChanged({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    expect(pushPreferences).toHaveBeenCalledOnce()
    expect(await preferencesSyncState()).toEqual({ dirty: false, syncedAt: LATER_AT })
  })

  it('asks the account nothing, on a connection this app assumes is bad', async () => {
    // The reason this is not just `syncPreferences`: four legend toggles
    // would otherwise be four GETs to ask a question this device has already
    // written down.
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    await pushPreferencesIfChanged({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    expect(fetchSyncedPreferences).not.toHaveBeenCalled()
  })

  it('leaves the change queued when the push cannot land', async () => {
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })
    vi.mocked(pushPreferences).mockRejectedValue(new TypeError('Failed to fetch'))

    await pushPreferencesIfChanged({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    expect((await preferencesSyncState()).dirty).toBe(true)
  })

  it('leaves the change queued when the push is REFUSED, too', async () => {
    // A schema mismatch is somebody's to fix. Clearing the flag would throw
    // the hiker's setting away while they did.
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })
    vi.mocked(pushPreferences).mockRejectedValue(new ApiError(422, 'refused'))

    await expect(
      pushPreferencesIfChanged({ ...DEFAULT_PREFERENCES, theme: 'dark' }),
    ).resolves.toBeUndefined()
    expect((await preferencesSyncState()).dirty).toBe(true)
  })

  it('does not adopt anything, ever', async () => {
    // A push is not a place to learn the account's preferences from: the
    // response is this device's own blob coming back, and treating it as
    // news would be a write echoing itself into the app.
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })
    vi.mocked(pushPreferences).mockResolvedValue(
      synced({ theme: 'light', updated_at: LATER_AT }),
    )

    await pushPreferencesIfChanged({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    // The stamp is taken from the response - it is the only place it exists -
    // and the blob is not.
    expect((await preferencesSyncState()).syncedAt).toBe(LATER_AT)
    expect((await loadPreferences()).theme).toBe('dark')
  })
})
