import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { Session } from '@supabase/supabase-js'
import {
  accountFromSession,
  redirectUrl,
  sendEmailCode,
  verifyEmailCode,
  signInWithProvider,
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
/** A refusal in wording lib/authMessages.ts does not recognise, so what
 *  reaches the screen is its general case. */
const FAILED = { error: { message: 'Unexpected failure' } }

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
    mockedGetClient.mockResolvedValue(null)
  })

  it.each([
    ['a Google sign-in', () => signInWithProvider('google')],
    ['a GitHub sign-in', () => signInWithProvider('github')],
    ['sending an email code', () => sendEmailCode('a@b.c')],
    ['checking an email code', () => verifyEmailCode('a@b.c', '123456')],
    ['a sign-out', () => signOut()],
  ])('%s says so rather than throwing', async (_label, call) => {
    const outcome = await call()

    expect(outcome.ok).toBe(false)
    // #315: the old wording named Supabase, which tells a hiker the name of
    // a vendor they have no relationship with. What replaced it says the
    // thing they can act on - the map still works.
    expect(outcome.ok === false && outcome.message).toMatch(/cannot sign in/i)
    expect(outcome.ok === false && outcome.message).not.toMatch(/supabase/i)
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
      // Mapped at the boundary since #315 - see lib/authMessages.ts.
      message: 'Sign-in did not go through. Nothing was lost — you can try again.',
    })
  })

  it('passes github through as its own provider name, which is what Supabase keys on', async () => {
    const signInWithOAuth = vi.fn().mockResolvedValue(NO_ERROR)
    mockedGetClient.mockReturnValue(fakeClient({ signInWithOAuth }))

    await signInWithProvider('github')

    expect(signInWithOAuth).toHaveBeenCalledWith({
      provider: 'github',
      options: { redirectTo: redirectUrl() },
    })
  })
})

describe('sendEmailCode', () => {
  it('asks signInWithOtp for a code and NOT a link, by sending no emailRedirectTo (#1600)', async () => {
    const signInWithOtp = vi.fn().mockResolvedValue(NO_ERROR)
    mockedGetClient.mockReturnValue(fakeClient({ signInWithOtp }))

    await sendEmailCode('hiker@example.com')

    // THE ABSENCE IS THE ASSERTION, and it is here because the presence of
    // that one option broke the whole door while every test stayed green.
    // Supplying a redirect URL is what lets `{{ .ConfirmationURL }}` resolve,
    // and Supabase's rule is that the variable's presence in the template
    // makes it send a magic LINK. GoTrue then minted a link token instead of
    // an OTP, and the six digits the email showed hashed to nothing the
    // server held - checked on UA against every candidate code at 5, 6 and 7
    // digits, zero matches. The client cannot see any of that: `signInWithOtp`
    // returned no error, the screen said "a code is on its way", and it was
    // the hiker who found out.
    //
    // The version of this test that shipped asserted `emailRedirectTo` was
    // PASSED, with a comment explaining it as "for a template that still
    // carries a link" - a rationalisation of the defect, holding it in place.
    expect(signInWithOtp).toHaveBeenCalledWith({
      email: 'hiker@example.com',
      options: { shouldCreateUser: true },
    })
    // Said twice deliberately: a future `options` gaining a key would keep
    // the equality above honest, and this line is what a reader greps for.
    const [{ options }] = signInWithOtp.mock.calls[0] as [{ options: object }]
    expect(options).not.toHaveProperty('emailRedirectTo')
    // shouldCreateUser stays explicit: one path serving a returning hiker and
    // a new one is the reason this replaced two others.
    expect(options).toHaveProperty('shouldCreateUser', true)
  })

  it('reports a rate limit rather than claiming a code is on its way', async () => {
    // Supabase rate-limits these. Saying "check your email" when nothing was
    // sent leaves someone waiting on a message that is not coming.
    mockedGetClient.mockReturnValue(
      fakeClient({
        signInWithOtp: vi
          .fn()
          .mockResolvedValue({ error: { message: 'Email rate limit exceeded' } }),
      }),
    )

    expect(await sendEmailCode('hiker@example.com')).toEqual({
      ok: false,
      message: 'That was just sent. Give it a minute before asking again.',
    })
  })

  it('says "Email address not authorized" means this build has no sender, not that the hiker did anything', async () => {
    // What a project still on Supabase's built-in mailer answers for any
    // address outside its own team (LAUNCH_CHECKLIST.md 4.3c).
    mockedGetClient.mockReturnValue(
      fakeClient({
        signInWithOtp: vi
          .fn()
          .mockResolvedValue({ error: { message: 'Email address not authorized' } }),
      }),
    )

    const outcome = await sendEmailCode('hiker@example.com')

    expect(outcome.ok).toBe(false)
    expect(outcome.ok === false && outcome.message).toMatch(/not switched on/i)
    expect(outcome.ok === false && outcome.message).toMatch(/map still works/i)
  })
})

describe('verifyEmailCode', () => {
  it("calls verifyOtp with type 'email', which covers a new address's code and a returning one's alike", async () => {
    const verifyOtp = vi.fn().mockResolvedValue(NO_ERROR)
    mockedGetClient.mockReturnValue(fakeClient({ verifyOtp }))

    const outcome = await verifyEmailCode('hiker@example.com', '123456')

    expect(verifyOtp).toHaveBeenCalledWith({
      email: 'hiker@example.com',
      token: '123456',
      type: 'email',
    })
    expect(outcome).toEqual({ ok: true })
  })

  it('strips the space a thumb puts in "123 456" rather than refusing it as a wrong code', async () => {
    const verifyOtp = vi.fn().mockResolvedValue(NO_ERROR)
    mockedGetClient.mockReturnValue(fakeClient({ verifyOtp }))

    await verifyEmailCode('hiker@example.com', ' 123 456 ')

    expect(verifyOtp).toHaveBeenCalledWith(expect.objectContaining({ token: '123456' }))
  })

  it('maps "Token has expired or is invalid" to a sentence with the way out in it', async () => {
    mockedGetClient.mockReturnValue(
      fakeClient({
        verifyOtp: vi
          .fn()
          .mockResolvedValue({ error: { message: 'Token has expired or is invalid' } }),
      }),
    )

    expect(await verifyEmailCode('hiker@example.com', '000000')).toEqual({
      ok: false,
      message: 'That code was not accepted. Ask for a new one and use the newest email.',
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

    // Falls through to the general case: 'Network request failed' is not
    // one of the patterns lib/authMessages.ts recognises, and a vaguer true
    // sentence is the intended failure mode of matching on text.
    expect(await signOut()).toEqual({
      ok: false,
      message: 'Sign-in did not go through. Nothing was lost — you can try again.',
    })
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
  it('reports the account whenever the session changes', async () => {
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
    // The client is awaited before the listener is attached (#1302).
    await new Promise((resolve) => setTimeout(resolve, 0))
    emit?.('SIGNED_IN', sessionWith('hiker@example.com'))
    emit?.('SIGNED_OUT', null)

    expect(seen).toEqual([{ email: 'hiker@example.com' }, null])

    stop()
    expect(unsubscribe).toHaveBeenCalled()
  })
})
