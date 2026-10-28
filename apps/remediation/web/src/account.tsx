// Signing in, and the remediation data that comes with it (#1906).
//
// Sign-in is OurHike's Supabase project (apps/remediation/PLAN.md §3), by the same
// door OurHike's client uses: a six-digit code by email, typed back. Not a link:
// the shared project's email template sends a code, and client/src/lib/auth.ts
// (#1600) records why asking it for a link fails. A code also means this site
// needs no redirect address registered with Supabase.
//
// Two build-time settings, both public: the project's URL and anon key (what
// every browser client is given). The data is in the same project, in its
// `remediation` schema (apps/remediation/db), so there is no other address. A build
// missing either has no accounts at all, and says so, rather than offering a
// sign-in that cannot finish.
//
// Everything a screen needs goes through AccountContext, so tests hand screens
// a fake instead of a Supabase project.

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { SupabaseClient } from '@supabase/supabase-js'
import { createApi, type DataClient, type RemediationApi } from './api'
import { PHOTO_CACHE } from './photoCache'
import { SIGNAL_BACK, clearOffline } from './offline'

const SUPABASE_URL: string = import.meta.env.VITE_SUPABASE_URL ?? ''
const SUPABASE_ANON_KEY: string = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''

export const ACCOUNTS_CONFIGURED = SUPABASE_URL !== '' && SUPABASE_ANON_KEY !== ''

export type Session =
  | { state: 'off' }
  | { state: 'loading' }
  | { state: 'signed_out' }
  | { state: 'signed_in'; userId: string; email: string | null }

export interface Account {
  session: Session
  /** Null unless signed in. */
  api: RemediationApi | null
  sendCode(email: string): Promise<string | null>
  verifyCode(email: string, code: string): Promise<string | null>
  signOut(): Promise<void>
}

const OFF: Account = {
  session: { state: 'off' },
  api: null,
  sendCode: async () => 'Sign-in is not set up on this site.',
  verifyCode: async () => 'Sign-in is not set up on this site.',
  signOut: async () => {},
}

export const AccountContext = createContext<Account>(OFF)

export function useAccount(): Account {
  return useContext(AccountContext)
}

let client: Promise<SupabaseClient> | null = null

/** Where supabase-js keeps the session in localStorage: named, so endSession
 *  can remove it when supabase-js does not. */
export const AUTH_STORAGE_KEY = 'site-remediation-auth'

/** Loaded on first use, so a visitor who never signs in never downloads it. */
function supabase(): Promise<SupabaseClient> {
  client ??= import('@supabase/supabase-js').then(({ createClient }) =>
    createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: false,
        storageKey: AUTH_STORAGE_KEY,
      },
    }),
  )
  return client
}

/**
 * A second client, for the `remediation` schema and the photo bucket only.
 *
 * Its token comes from accessToken() below rather than from supabase-js's own
 * session read, which with no signal and an expired token waits about 25 s
 * and then sends the request as nobody (auth-js 2.118). accessToken() answers
 * at once with no network, and throws what fetch throws with no connection,
 * which a screen and the photo queue read as no signal.
 */
function loadData() {
  return import('@supabase/supabase-js').then(({ createClient }) =>
    createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      accessToken: async () => accessToken((await supabase()).auth, window.localStorage),
      db: { schema: 'remediation' },
    }),
  )
}

let dataClient: ReturnType<typeof loadData> | null = null

const data = () => (dataClient ??= loadData())

/** The data client, loaded on its first call. */
const lazyData: DataClient = {
  rpc: async (fn, args) => await (await data()).rpc(fn, args),
  storage: {
    from: (bucket) => ({
      upload: async (path, body, options) =>
        await (await data()).storage.from(bucket).upload(path, body, options),
      remove: async (paths) => await (await data()).storage.from(bucket).remove(paths),
      createSignedUrls: async (paths, expiresIn) =>
        await (await data()).storage.from(bucket).createSignedUrls(paths, expiresIn),
    }),
  },
}
/**
 * The account of the session supabase-js keeps in storage, read directly.
 *
 * supabase-js answers "no session" once the access token has expired and it
 * cannot reach Supabase to renew it, though it keeps the session stored: it
 * removes a stored session only when Supabase refuses it, or when this
 * browser signs out (auth-js 2.118, GoTrueClient's refresh: a retryable fetch
 * error leaves it in place). So a session still stored is a person still
 * signed in, whose sign-in waits for signal. Before the adversarial review's
 * fourth pass (A, 2026-10-27), that person was shown as signed out about an
 * hour after the signal went: their saved claims would not open and new
 * photos were not queued, which is the whole of what offline is for.
 */
export function storedUser(
  storage: Pick<Storage, 'getItem'>,
): { id: string; email: string | null } | null {
  const stored = storedSession(storage)
  return stored ? { id: stored.userId, email: stored.email } : null
}

function storedSession(
  storage: Pick<Storage, 'getItem'>,
): { userId: string; email: string | null; expiresAt: number } | null {
  try {
    const raw = storage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as {
      expires_at?: unknown
      user?: { id?: unknown; email?: unknown }
    }
    const user = parsed.user
    if (typeof user?.id !== 'string') return null
    return {
      userId: user.id,
      email: typeof user.email === 'string' ? user.email : null,
      expiresAt: typeof parsed.expires_at === 'number' ? parsed.expires_at : 0,
    }
  } catch {
    return null
  }
}

/** How long a request waits for supabase-js to renew an expired sign-in
 *  before counting as no signal. supabase-js itself retries for about 25 s
 *  (measured 2026-10-27: 25.4 s and eight attempts, auth-js 2.118, every
 *  request failing), and a photo taken on the trail should be queued well
 *  before that. `@unvalidated`: a renewal with signal takes one round trip,
 *  which nobody has timed on a weak trailhead signal. */
export const RENEW_WAIT_MS = 5000

/**
 * The access token for the API, or null when nobody is signed in.
 *
 * With a session stored that cannot be renewed for lack of signal, a
 * TypeError, which is what fetch throws with no connection: offline.isOffline
 * reads it as no signal, so a claim opens from its saved copy and a photo is
 * queued, rather than the volunteer being told to sign in on the trail. With
 * no network at all, supabase-js is not asked; with some, it gets
 * RENEW_WAIT_MS to renew, and carries on renewing after that.
 */
export async function accessToken(
  auth: { getSession(): Promise<{ data: { session: { access_token: string } | null } }> },
  storage: Pick<Storage, 'getItem'>,
  waitMs = RENEW_WAIT_MS,
): Promise<string | null> {
  const stored = storedSession(storage)
  const expired = stored !== null && stored.expiresAt * 1000 <= Date.now()
  const noSignal = () => new TypeError('No signal to renew the sign-in.')
  if (expired && navigator.onLine === false) throw noSignal()
  let timer: ReturnType<typeof setTimeout> | undefined
  const stalled = new Promise<'stalled'>((resolve) => {
    timer = setTimeout(() => resolve('stalled'), waitMs)
  })
  const answer = await Promise.race([auth.getSession(), stalled])
  clearTimeout(timer)
  if (answer === 'stalled') throw noSignal()
  if (answer.data.session) return answer.data.session.access_token
  if (storedSession(storage)) throw noSignal()
  return null
}

/** Who is signed in: the session supabase-js gives, or else the one it keeps stored. */
function sessionOf(user: { id: string; email?: string } | null | undefined): Session {
  const who = user
    ? { id: user.id, email: user.email ?? null }
    : storedUser(window.localStorage)
  return who
    ? { state: 'signed_in', userId: who.id, email: who.email }
    : { state: 'signed_out' }
}

/**
 * Signs this browser out, signal or none.
 *
 * Only this browser ('local'): the Supabase project is OurHike's, and the
 * default ('global') would also sign the person out of OurHike, on every
 * device they use it on.
 *
 * supabase-js removes the stored session only once it has told Supabase. With
 * an expired access token and no signal it cannot refresh, returns an error,
 * and leaves the session and its refresh token where they were, so the next
 * person to pick up a shared phone was signed in as the last one when signal
 * came back (the adversarial review's third pass, P3, 2026-10-27, against
 * supabase-js 2.118). On any error, the session is removed here instead.
 */
export async function endSession(
  auth: { signOut(options: { scope: 'local' }): Promise<{ error: unknown }> },
  storage: Pick<Storage, 'removeItem'>,
): Promise<void> {
  let failed: boolean
  if (navigator.onLine === false) {
    // supabase-js would spend about 25 s retrying before it gave up.
    failed = true
  } else {
    try {
      failed = Boolean((await auth.signOut({ scope: 'local' })).error)
    } catch {
      failed = true
    }
  }
  if (!failed) return
  for (const suffix of ['', '-code-verifier', '-user']) {
    try {
      storage.removeItem(AUTH_STORAGE_KEY + suffix)
    } catch {
      // Storage refused: nothing more this page can do.
    }
  }
}

/** Supabase's messages are for developers; these are for a volunteer. */
function plain(message: string): string {
  if (/rate limit|too many/i.test(message))
    return 'Too many tries. Wait a minute and try again.'
  if (/expired|invalid/i.test(message))
    return 'That code is wrong or has expired. Ask for a new one.'
  return 'Sign-in did not work. Try again.'
}

export function AccountProvider({ children }: { children: ReactNode }) {
  // The stored account straight away, when there is one: supabase-js can take
  // 25 s to say anything with no signal (RENEW_WAIT_MS), and the phone is
  // signed in all along.
  const [session, setSession] = useState<Session>(() => {
    if (!ACCOUNTS_CONFIGURED) return { state: 'off' }
    const who = storedUser(window.localStorage)
    return who
      ? { state: 'signed_in', userId: who.id, email: who.email }
      : { state: 'loading' }
  })

  useEffect(() => {
    if (!ACCOUNTS_CONFIGURED) return
    let unsubscribe = () => {}
    let live = true
    void supabase().then((sb) => {
      if (!live) return
      void sb.auth.getSession().then(({ data }) => {
        if (live) setSession(sessionOf(data.session?.user))
      })
      const { data } = sb.auth.onAuthStateChange((event, next) => {
        setSession(
          event === 'SIGNED_OUT' ? { state: 'signed_out' } : sessionOf(next?.user),
        )
        // A renewed sign-in means the signal is back: photos waiting can go.
        if (event === 'TOKEN_REFRESHED') window.dispatchEvent(new Event(SIGNAL_BACK))
      })
      unsubscribe = () => data.subscription.unsubscribe()
    })
    return () => {
      live = false
      unsubscribe()
    }
  }, [])

  const account = useMemo<Account>(() => {
    if (!ACCOUNTS_CONFIGURED) return OFF
    return {
      session,
      api: session.state === 'signed_in' ? createApi(lazyData) : null,
      async sendCode(email) {
        const { error } = await (
          await supabase()
        ).auth.signInWithOtp({
          email,
          options: { shouldCreateUser: true },
        })
        return error ? plain(error.message) : null
      },
      async verifyCode(email, code) {
        const { error } = await (
          await supabase()
        ).auth.verifyOtp({
          email,
          token: code.replace(/\s+/g, ''),
          type: 'email',
        })
        return error ? plain(error.message) : null
      },
      async signOut() {
        // Saved claims, queued photos and the photos shown are this person's;
        // a shared phone should not keep them for the next one
        // (src/offline.ts, src/photoCache.ts).
        if (session.state === 'signed_in') await clearOffline(session.userId)
        await globalThis.caches?.delete(PHOTO_CACHE).catch(() => false)
        await endSession((await supabase()).auth, window.localStorage)
        // Said here as well as by supabase-js, which says nothing when it failed.
        setSession({ state: 'signed_out' })
      },
    }
  }, [session])

  return <AccountContext.Provider value={account}>{children}</AccountContext.Provider>
}
