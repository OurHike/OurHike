// Signing in, signing out, and knowing which of the two is currently true.
//
// Supabase Auth owns the hard parts (features/AUTHENTICATION.md): password
// hashing, the OAuth token exchange, refresh, and email verification all
// happen there, and the backend only ever verifies the JWT that comes back
// (backend/app/core/auth.py). Nothing in this file implements authentication;
// it adapts Supabase's session to the one shape the screens need.
//
// The app stays usable signed out. Reading the map, the downloads, the
// outbox and the preferences are all local-first, so every operation here can
// fail and leave a hiker exactly where they were.

import type { Session } from '@supabase/supabase-js'
import { getAuthClient } from './supabase'
import type { AuthProvider } from '../screens/SignInPrompt'

/** What the screens show. Matches Settings' account row. */
export interface Account {
  email: string
}

/**
 * The account a session represents, or null for no account.
 *
 * A session carrying no email is treated as signed out rather than shown as a
 * blank account row. With Google and email - the two providers a default build
 * enables - a session always carries one, so this is a guard rather than a
 * routine path. Apple is the provider that can withhold it, via private relay,
 * and exercising that is #92.
 */
export function accountFromSession(session: Session | null): Account | null {
  const email = session?.user?.email
  return typeof email === 'string' && email !== '' ? { email } : null
}

/**
 * Where an OAuth provider sends the hiker back to.
 *
 * `origin` alone is wrong here: Pages serves this app from a subpath
 * (`/OurHike/app/`, see .github/workflows/pages.yml), so a redirect to the
 * bare origin lands on the project site with the code in its URL and no app
 * to read it. BASE_URL is the same value Vite built the asset paths from, so
 * this cannot drift from where the app actually lives.
 *
 * Whatever this returns has to also be listed in the Supabase project's
 * allowed redirect URLs, or the provider round trip ends in a redirect
 * mismatch (LAUNCH_CHECKLIST.md 4.3).
 */
export function redirectUrl(): string {
  return new URL(import.meta.env.BASE_URL, window.location.origin).href
}

export type AuthOutcome = { ok: true } | { ok: false; message: string }

const NOT_CONFIGURED: AuthOutcome = {
  ok: false,
  message:
    'This build has no Supabase project configured, so signing in is not possible.',
}

/**
 * Starts an OAuth round trip. Resolves only if it fails - on success the
 * browser has already navigated away to the provider.
 */
export async function signInWithProvider(
  provider: Exclude<AuthProvider, 'email'>,
): Promise<AuthOutcome> {
  const client = getAuthClient()
  if (client === null) return NOT_CONFIGURED

  const { error } = await client.auth.signInWithOAuth({
    provider,
    options: { redirectTo: redirectUrl() },
  })
  return error === null ? { ok: true } : { ok: false, message: error.message }
}

export async function signInWithEmail(
  email: string,
  password: string,
): Promise<AuthOutcome> {
  const client = getAuthClient()
  if (client === null) return NOT_CONFIGURED

  const { error } = await client.auth.signInWithPassword({ email, password })
  return error === null ? { ok: true } : { ok: false, message: error.message }
}

/**
 * Creates an account. Supabase sends the verification email itself; until it
 * is confirmed there is no session, which is why this reports back rather
 * than assuming the caller is now signed in.
 */
export async function signUpWithEmail(
  email: string,
  password: string,
): Promise<AuthOutcome> {
  const client = getAuthClient()
  if (client === null) return NOT_CONFIGURED

  const { error } = await client.auth.signUp({
    email,
    password,
    options: { emailRedirectTo: redirectUrl() },
  })
  return error === null ? { ok: true } : { ok: false, message: error.message }
}

export async function signOut(): Promise<AuthOutcome> {
  const client = getAuthClient()
  if (client === null) return NOT_CONFIGURED

  const { error } = await client.auth.signOut()
  return error === null ? { ok: true } : { ok: false, message: error.message }
}

/** The account restored from storage at startup, if any. */
export async function currentAccount(): Promise<Account | null> {
  const client = getAuthClient()
  if (client === null) return null

  const { data } = await client.auth.getSession()
  return accountFromSession(data.session)
}

/**
 * Calls back whenever the signed-in account changes, and returns an
 * unsubscribe. Sign-in finishes by returning from a provider redirect rather
 * than by a promise resolving in the tab that started it, so this - not the
 * result of signInWithProvider - is what tells the app it worked.
 */
export function subscribeToAccount(
  listener: (account: Account | null) => void,
): () => void {
  const client = getAuthClient()
  if (client === null) return () => {}

  const {
    data: { subscription },
  } = client.auth.onAuthStateChange((_event, session) => {
    listener(accountFromSession(session))
  })
  return () => subscription.unsubscribe()
}
