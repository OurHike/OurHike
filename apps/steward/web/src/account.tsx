// Signing in, and the API that comes with it (#1906).
//
// Sign-in is OurHike's Supabase project (apps/steward/PLAN.md §3), by the same
// door OurHike's client uses: a six-digit code by email, typed back. Not a link:
// the shared project's email template sends a code, and client/src/lib/auth.ts
// (#1600) records why asking it for a link fails. A code also means this site
// needs no redirect address registered with Supabase.
//
// Three build-time settings, all public: the project's URL and anon key (what
// every browser client is given) and the steward API's address. A build missing
// any of them has no accounts at all, and says so, rather than offering a
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
import { createApi, type StewardApi } from './api'
import { clearOffline } from './offline'

const SUPABASE_URL: string = import.meta.env.VITE_SUPABASE_URL ?? ''
const SUPABASE_ANON_KEY: string = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''
const API_URL: string = import.meta.env.VITE_STEWARD_API_URL ?? ''

export const ACCOUNTS_CONFIGURED =
  SUPABASE_URL !== '' && SUPABASE_ANON_KEY !== '' && API_URL !== ''

export type Session =
  | { state: 'off' }
  | { state: 'loading' }
  | { state: 'signed_out' }
  | { state: 'signed_in'; userId: string; email: string | null }

export interface Account {
  session: Session
  /** Null unless signed in. */
  api: StewardApi | null
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
export const AUTH_STORAGE_KEY = 'campsite-steward-auth'

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
  try {
    failed = Boolean((await auth.signOut({ scope: 'local' })).error)
  } catch {
    failed = true
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
  const [session, setSession] = useState<Session>(
    ACCOUNTS_CONFIGURED ? { state: 'loading' } : { state: 'off' },
  )

  useEffect(() => {
    if (!ACCOUNTS_CONFIGURED) return
    let unsubscribe = () => {}
    let live = true
    void supabase().then((sb) => {
      if (!live) return
      void sb.auth.getSession().then(({ data }) => {
        if (!live) return
        const user = data.session?.user
        setSession(
          user
            ? { state: 'signed_in', userId: user.id, email: user.email ?? null }
            : { state: 'signed_out' },
        )
      })
      const { data } = sb.auth.onAuthStateChange((_event, next) => {
        const user = next?.user
        setSession(
          user
            ? { state: 'signed_in', userId: user.id, email: user.email ?? null }
            : { state: 'signed_out' },
        )
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
    const token = async () =>
      (await (await supabase()).auth.getSession()).data.session?.access_token ?? null
    return {
      session,
      api: session.state === 'signed_in' ? createApi(API_URL, token) : null,
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
        // Saved claims and queued photos are this person's; a shared phone
        // should not keep them for the next one (src/offline.ts).
        if (session.state === 'signed_in') await clearOffline(session.userId)
        await endSession((await supabase()).auth, window.localStorage)
        // Said here as well as by supabase-js, which says nothing when it failed.
        setSession({ state: 'signed_out' })
      },
    }
  }, [session])

  return <AccountContext.Provider value={account}>{children}</AccountContext.Provider>
}
