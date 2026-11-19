import { createClient } from '@supabase/supabase-js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AUTH_STORAGE_KEY,
  RENEW_WAIT_MS,
  accessToken,
  endSession,
  storedUser,
} from './account'
import { isOffline } from './offline'

afterEach(() => window.localStorage.clear())

function storedSession() {
  window.localStorage.setItem(AUTH_STORAGE_KEY, '{"refresh_token":"r"}')
  window.localStorage.setItem(`${AUTH_STORAGE_KEY}-user`, '{"id":"user-1"}')
}

it('signs out everywhere, every time, as decided on 2026-10-28', async () => {
  const signOut = vi.fn(async () => ({ error: null }))
  await endSession({ signOut }, window.localStorage)
  expect(signOut).toHaveBeenCalledWith({ scope: 'global' })
})

it('removes the stored session itself when supabase-js could not sign out for lack of signal', async () => {
  // The third pass's P3: with an expired access token and no signal,
  // supabase-js returned an error and left the session and its refresh token
  // stored, so the next person on a shared phone was signed in as this one.
  storedSession()
  await endSession(
    { signOut: async () => ({ error: new Error('Failed to fetch') }) },
    window.localStorage,
  )
  expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull()
  expect(window.localStorage.getItem(`${AUTH_STORAGE_KEY}-user`)).toBeNull()
})

it('removes it as well when supabase-js throws rather than answering', async () => {
  storedSession()
  await endSession(
    {
      signOut: async () => {
        throw new TypeError('Failed to fetch')
      },
    },
    window.localStorage,
  )
  expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull()
})

describe('with no signal, an hour after the last', () => {
  // The fourth pass's A: once the access token expired with no signal,
  // supabase-js answered "no session", the app called the volunteer signed
  // out, and their saved claims and photo queue were out of reach. This drives
  // the real supabase-js, with every request failing as fetch does offline,
  // and fake timers through the backoff it retries with.
  const memory = new Map<string, string>()
  const storage = {
    getItem: (key: string) => memory.get(key) ?? null,
    setItem: (key: string, value: string) => void memory.set(key, value),
    removeItem: (key: string) => void memory.delete(key),
  }
  const client = () =>
    createClient('https://project.supabase.co', 'anon-key', {
      auth: {
        storage,
        storageKey: AUTH_STORAGE_KEY,
        persistSession: true,
        autoRefreshToken: false,
        detectSessionInUrl: false,
      },
      global: {
        fetch: async () => {
          throw new TypeError('Failed to fetch')
        },
      },
    })
  const store = (expiresAt: number) =>
    memory.set(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        access_token: 'header.payload.signature',
        refresh_token: 'refresh',
        token_type: 'bearer',
        expires_in: 3600,
        expires_at: expiresAt,
        user: { id: 'volunteer', email: 'v@example.com', aud: 'authenticated' },
      }),
    )
  const now = () => Math.floor(Date.now() / 1000)

  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(async () => {
    // Lets supabase-js finish retrying, so it holds no lock into the next test.
    await vi.advanceTimersByTimeAsync(60_000)
    vi.useRealTimers()
    vi.unstubAllGlobals()
    memory.clear()
  })

  it('supabase-js says no session, after retrying for half a minute, but keeps it stored', async () => {
    store(now() - 60)
    const answer = client().auth.getSession()
    await vi.advanceTimersByTimeAsync(60_000)
    expect((await answer).data.session).toBeNull()
    expect(memory.has(AUTH_STORAGE_KEY)).toBe(true)
  })

  it('so the volunteer stays signed in as the stored account', () => {
    store(now() - 60)
    expect(storedUser(storage)).toEqual({ id: 'volunteer', email: 'v@example.com' })
  })

  it('and a token asked for with a weak signal is no signal after RENEW_WAIT_MS, not "sign in first"', async () => {
    store(now() - 60)
    const failure = accessToken(client().auth, storage).catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(RENEW_WAIT_MS)
    const error = await failure
    expect(error).toBeInstanceOf(TypeError)
    expect(isOffline(error)).toBe(true)
  })

  it('with no network at all, supabase-js is not asked, so nothing waits', async () => {
    store(now() - 60)
    vi.stubGlobal('navigator', { ...navigator, onLine: false })
    const auth = { getSession: vi.fn() }
    await expect(accessToken(auth, storage)).rejects.toBeInstanceOf(TypeError)
    expect(auth.getSession).not.toHaveBeenCalled()
  })

  it('while the token is still good, it is used as it is', async () => {
    store(now() + 3000)
    expect(await accessToken(client().auth, storage)).toBe('header.payload.signature')
  })

  it('with nothing stored, nobody is signed in', async () => {
    expect(await accessToken(client().auth, storage)).toBeNull()
    expect(storedUser(storage)).toBeNull()
  })
})

it('signing out with no network at all removes the session without waiting on supabase-js', async () => {
  window.localStorage.setItem(AUTH_STORAGE_KEY, '{"refresh_token":"r"}')
  vi.stubGlobal('navigator', { ...navigator, onLine: false })
  const signOut = vi.fn()
  try {
    await endSession({ signOut }, window.localStorage)
  } finally {
    vi.unstubAllGlobals()
  }
  expect(signOut).not.toHaveBeenCalled()
  expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull()
})
