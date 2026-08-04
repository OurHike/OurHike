import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Session } from '@supabase/supabase-js'
import {
  accountFromSession,
  redirectUrl,
  sendMagicLink,
  signInWithProvider,
  signInWithEmail,
  signUpWithEmail,
  signOut,
  currentAccount,
  subscribeToAccount,
} from './auth'
import { getAuthClient } from './supabase'

vi.mock('./supabase', () => ({ getAuthClient: vi.fn() }))

const mockedGetClient = vi.mocked(getAuthClient)

function sessionWith(email: string | undefined): Session {
  return { user: { email } } as unknown as Session
}

/** Just enough of the client for the calls under test. */
function fakeClient(auth: Record<string, unknown>) {
  return { auth } as unknown as ReturnType<typeof getAuthClient>
}

const NO_ERROR = { error: null }
const FAILED = { error: { message: 'Invalid login credentials' } }

beforeEach(() => {
  vi.clearAllMocks()
})

describe('accountFromSession', () => {
  it('reads the email off a signed-in session', () => {
    expect(accountFromSession(sessionWith('hiker@example.com'))).toEqual({
      email: 'hiker@example.com',
    })
  })

  it('has no account without a session', () => {
    expect(accountFromSession(null)).toBe(null)
  })

  it('treats a session carrying no email as signed out', () => {
    // Rather than rendering an account row with a blank address. Apple is the
    // provider that can withhold one, via private relay; exercising that for
    // real is #92.
    expect(accountFromSession(sessionWith(undefined))).toBe(null)
  })

  it('treats an empty email the same way', () => {
    expect(accountFromSession(sessionWith(''))).toBe(null)
  })
})

describe('redirectUrl', () => {
  it('includes the path the app is served from, not just the origin', () => {
    // Pages serves this app from a subpath. A redirect to the bare origin
    // lands on the project site carrying the code, with no app there to read
    // it - which is the redirect mismatch #92 warns about.
    expect(redirectUrl()).toBe(
      new URL(import.meta.env.BASE_URL, window.location.origin).href,
    )
  })

  it('is absolute, because a provider cannot redirect to a relative path', () => {
    expect(redirectUrl()).toMatch(/^https?:\/\//)
  })
})

describe('with no project configured', () => {
  beforeEach(() => {
    mockedGetClient.mockReturnValue(null)
  })

  it.each([
    ['a provider sign-in', () => signInWithProvider('google')],
    ['a magic link', () => sendMagicLink('a@b.c')],
    ['an email sign-in', () => signInWithEmail('a@b.c', 'pw')],
    ['a sign-up', () => signUpWithEmail('a@b.c', 'pw')],
    ['a sign-out', () => signOut()],
  ])('%s says so rather than throwing', async (_label, call) => {
    const outcome = await call()

    expect(outcome.ok).toBe(false)
    expect(outcome.ok === false && outcome.message).toMatch(/no supabase project/i)
  })

  it('has no account', async () => {
    expect(await currentAccount()).toBe(null)
  })

  it('subscribing is a no-op that can still be unsubscribed', () => {
    // The caller is an effect cleanup; handing it back nothing to call would
    // make the absence of a project a crash on unmount.
    const unsubscribe = subscribeToAccount(() => {})

    expect(() => unsubscribe()).not.toThrow()
  })
})

describe('signInWithProvider', () => {
  it('sends the hiker back to where the app is actually served from', async () => {
    const signInWithOAuth = vi.fn().mockResolvedValue(NO_ERROR)
    mockedGetClient.mockReturnValue(fakeClient({ signInWithOAuth }))

    await signInWithProvider('google')

    expect(signInWithOAuth).toHaveBeenCalledWith({
      provider: 'google',
      options: { redirectTo: redirectUrl() },
    })
  })

  it('reports a refusal instead of leaving the caller to guess', async () => {
    mockedGetClient.mockReturnValue(
      fakeClient({ signInWithOAuth: vi.fn().mockResolvedValue(FAILED) }),
    )

    expect(await signInWithProvider('google')).toEqual({
      ok: false,
      message: 'Invalid login credentials',
    })
  })
})

describe('sendMagicLink', () => {
  it('asks for the link to come back to the app, and to create the user if new', async () => {
    const signInWithOtp = vi.fn().mockResolvedValue(NO_ERROR)
    mockedGetClient.mockReturnValue(fakeClient({ signInWithOtp }))

    await sendMagicLink('hiker@example.com')

    // shouldCreateUser is what lets one path serve both a returning hiker and
    // a new one, so it is asserted rather than left to the library default.
    expect(signInWithOtp).toHaveBeenCalledWith({
      email: 'hiker@example.com',
      options: { emailRedirectTo: redirectUrl(), shouldCreateUser: true },
    })
  })

  it('reports a refusal rather than claiming an email is on its way', async () => {
    // Supabase rate-limits these. Saying "check your email" when nothing was
    // sent leaves someone waiting on a message that is not coming.
    mockedGetClient.mockReturnValue(
      fakeClient({
        signInWithOtp: vi
          .fn()
          .mockResolvedValue({ error: { message: 'Email rate limit exceeded' } }),
      }),
    )

    expect(await sendMagicLink('hiker@example.com')).toEqual({
      ok: false,
      message: 'Email rate limit exceeded',
    })
  })
})

describe('signInWithEmail', () => {
  it('passes the credentials through unchanged', async () => {
    const signInWithPassword = vi.fn().mockResolvedValue(NO_ERROR)
    mockedGetClient.mockReturnValue(fakeClient({ signInWithPassword }))

    const outcome = await signInWithEmail('hiker@example.com', 'a good password')

    expect(signInWithPassword).toHaveBeenCalledWith({
      email: 'hiker@example.com',
      password: 'a good password',
    })
    expect(outcome).toEqual({ ok: true })
  })

  it("surfaces the provider's wording on a bad password", async () => {
    mockedGetClient.mockReturnValue(
      fakeClient({ signInWithPassword: vi.fn().mockResolvedValue(FAILED) }),
    )

    expect(await signInWithEmail('hiker@example.com', 'wrong')).toEqual({
      ok: false,
      message: 'Invalid login credentials',
    })
  })
})

describe('signUpWithEmail', () => {
  it('asks for the confirmation email to come back to the app', async () => {
    const signUp = vi.fn().mockResolvedValue(NO_ERROR)
    mockedGetClient.mockReturnValue(fakeClient({ signUp }))

    await signUpWithEmail('hiker@example.com', 'a good password')

    expect(signUp).toHaveBeenCalledWith({
      email: 'hiker@example.com',
      password: 'a good password',
      options: { emailRedirectTo: redirectUrl() },
    })
  })

  it('reports a refusal, so a known address is not read as a new account', async () => {
    mockedGetClient.mockReturnValue(
      fakeClient({
        signUp: vi
          .fn()
          .mockResolvedValue({ error: { message: 'User already registered' } }),
      }),
    )

    expect(await signUpWithEmail('hiker@example.com', 'pw')).toEqual({
      ok: false,
      message: 'User already registered',
    })
  })
})

describe('signOut', () => {
  it('reports a failure rather than letting the app assume it worked', async () => {
    // Claiming a sign-out that did not happen is the wrong way round to be
    // wrong: a shared phone would look signed out while the session was still
    // live.
    mockedGetClient.mockReturnValue(
      fakeClient({
        signOut: vi
          .fn()
          .mockResolvedValue({ error: { message: 'Network request failed' } }),
      }),
    )

    expect(await signOut()).toEqual({ ok: false, message: 'Network request failed' })
  })

  it('reports success', async () => {
    mockedGetClient.mockReturnValue(
      fakeClient({ signOut: vi.fn().mockResolvedValue(NO_ERROR) }),
    )

    expect(await signOut()).toEqual({ ok: true })
  })
})

describe('currentAccount', () => {
  it('restores the account from a stored session', async () => {
    mockedGetClient.mockReturnValue(
      fakeClient({
        getSession: vi.fn().mockResolvedValue({
          data: { session: sessionWith('hiker@example.com') },
        }),
      }),
    )

    expect(await currentAccount()).toEqual({ email: 'hiker@example.com' })
  })

  it('is null when nothing was stored', async () => {
    mockedGetClient.mockReturnValue(
      fakeClient({ getSession: vi.fn().mockResolvedValue({ data: { session: null } }) }),
    )

    expect(await currentAccount()).toBe(null)
  })
})

describe('subscribeToAccount', () => {
  it('reports the account whenever the session changes', () => {
    let emit: ((event: string, session: Session | null) => void) | undefined
    const unsubscribe = vi.fn()
    mockedGetClient.mockReturnValue(
      fakeClient({
        onAuthStateChange: (
          handler: (event: string, session: Session | null) => void,
        ) => {
          emit = handler
          return { data: { subscription: { unsubscribe } } }
        },
      }),
    )
    const seen: Array<{ email: string } | null> = []

    const stop = subscribeToAccount((account) => seen.push(account))
    emit?.('SIGNED_IN', sessionWith('hiker@example.com'))
    emit?.('SIGNED_OUT', null)

    expect(seen).toEqual([{ email: 'hiker@example.com' }, null])

    stop()
    expect(unsubscribe).toHaveBeenCalled()
  })
})
