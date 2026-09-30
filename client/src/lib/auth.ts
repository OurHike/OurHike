// Signing in, signing out, and knowing which of the two is currently true.
//
// Supabase Auth owns the hard parts (features/AUTHENTICATION.md): the OAuth
// token exchange with Google and GitHub, the 6-digit code it emails and
// checks, refresh, and email verification all happen there, and the backend
// only ever verifies the JWT that comes back (backend/app/core/auth.py).
// Nothing in this file implements authentication; it adapts Supabase's
// session to the one shape the screens need.
//
// The app stays usable signed out. Reading the map, the downloads, the
// outbox and the preferences are all local-first, so every operation here can
// fail and leave a hiker exactly where they were.

import type { Session } from '@supabase/supabase-js'
import { getAuthClient } from './supabase'
import { NOT_CONFIGURED_MESSAGE, signInMessage } from './authMessages'
import type { AuthProvider } from '../screens/SignInPrompt'

/** What the screens show. Matches Settings' account row. */
export interface Account {
  email: string
}

/**
 * The account a session represents, or null for no account.
 *
 * A session carrying no email is treated as signed out rather than shown as a
 * blank account row. With Google, GitHub and email a session always carries
 * one - Supabase refuses a GitHub account with no verified address rather
 * than minting a user without one (#1573) - so this is a guard rather than a
 * routine path. Apple is the provider that can withhold it, via private
 * relay, and exercising that is #92.
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

// Mapped at the boundary rather than rendered raw (#315). See
// lib/authMessages.ts for why the vendor's name and its library's exception
// classes are not a hiker's business.
const NOT_CONFIGURED: AuthOutcome = { ok: false, message: NOT_CONFIGURED_MESSAGE }

/** One supabase-js failure as an outcome a screen can show. */
function failed(message: string): AuthOutcome {
  return { ok: false, message: signInMessage(message) }
}

/**
 * Starts an OAuth round trip. Resolves only if it fails - on success the
 * browser has already navigated away to the provider.
 */
export async function signInWithProvider(
  provider: Exclude<AuthProvider, 'email'>,
): Promise<AuthOutcome> {
  const client = await getAuthClient()
  if (client === null) return NOT_CONFIGURED

  const { error } = await client.auth.signInWithOAuth({
    provider,
    options: { redirectTo: redirectUrl() },
  })
  return error === null ? { ok: true } : failed(error.message)
}

/**
 * Emails a 6-digit sign-in code (#279). One call covers both a returning
 * hiker and a new one: Supabase creates the user when the address is
 * unknown, so there is no separate sign-up to choose between first, and no
 * password to forget on a trail six weeks from the place it was set.
 *
 * This is the same `signInWithOtp` call that used to send a link. Whether
 * the email carries a link or a code is the project's email template -
 * `{{ .Token }}` in both "Magic Link" and "Confirm sign up", because a new
 * address gets the second (LAUNCH_CHECKLIST.md 4.3d) - so nothing here can
 * tell which the hiker will receive; backend/check_supabase_config.py reads
 * the templates back and says. `emailRedirectTo` stays set for a template
 * that still carries a link: it then comes back to the app rather than to
 * the project's Site URL.
 *
 * `shouldCreateUser` is passed explicitly rather than left to its default,
 * because "this also creates accounts" is the whole reason this path can
 * replace two others and should not be something a reader has to know the
 * library's defaults to discover.
 *
 * Typing the code back is itself the proof the address belongs to whoever
 * asked, so this satisfies features/AUTHENTICATION.md's verification
 * requirement directly rather than by a second confirmation step.
 */
export async function sendEmailCode(email: string): Promise<AuthOutcome> {
  const client = await getAuthClient()
  if (client === null) return NOT_CONFIGURED

  // NO `emailRedirectTo`, AND THAT IS THE POINT OF THIS CALL (#1600).
  //
  // It was here until 2026-09-21 and it is what asks Supabase for a magic
  // LINK. Their own reference splits the two: the magic-link example passes
  // `emailRedirectTo`, the OTP example deliberately does not, and the
  // passwordless guide states the rule one-directionally - "if the
  // `{{ .ConfirmationURL }}` variable is specified in the email template, a
  // magiclink will be sent". A redirect URL is what makes that variable
  // resolve to anything.
  //
  // What it cost, measured on UA the night #1576 merged: GoTrue minted a
  // magic-link token (`auth.one_time_tokens.token_type = 'recovery_token'`,
  // a 56-hex SHA-224) rather than a six-digit OTP, so the code the email
  // displayed hashed to nothing the server held. Every candidate code at 5,
  // 6 and 7 digits was checked against that stored hash, under four
  // formulations, and none matched - the hiker's two attempts could not have
  // succeeded, and the token was still sitting there unconsumed afterwards.
  //
  // screens/EmailSignIn.tsx asks for six digits and this app has no screen
  // that a returning link could land on, so there is nothing to redirect TO.
  // `shouldCreateUser` stays, and stays explicit: "this also creates
  // accounts" is the whole reason this path replaced two others.
  const { error } = await client.auth.signInWithOtp({
    email,
    options: { shouldCreateUser: true },
  })
  return error === null ? { ok: true } : failed(error.message)
}

/**
 * Signs in with the code that email carried.
 *
 * `type: 'email'` is what Supabase's own OTP example passes, for a new
 * address and a returning one alike - a distinction the hiker never sees and
 * this function should not have to make. Confirmed against their
 * passwordless guide 2026-09-21 rather than assumed, which is how the
 * sibling `sendEmailCode` above was found to be asking for the wrong thing
 * entirely (#1600).
 *
 * Whitespace is stripped because a code read off a phone's notification and
 * typed with a thumb arrives as "123 456" often enough, and refusing it
 * would read as a wrong code.
 *
 * On success supabase-js stores the session and fires the account
 * subscription (subscribeToAccount), which is how the app learns it worked -
 * the same event a provider redirect produces, so App.tsx closes the flow on
 * one signal for every door. The outcome here is for the screen to show a
 * refusal.
 */
export async function verifyEmailCode(email: string, code: string): Promise<AuthOutcome> {
  const client = await getAuthClient()
  if (client === null) return NOT_CONFIGURED

  const { error } = await client.auth.verifyOtp({
    email,
    token: code.replace(/\s+/g, ''),
    type: 'email',
  })
  return error === null ? { ok: true } : failed(error.message)
}

export async function signOut(): Promise<AuthOutcome> {
  const client = await getAuthClient()
  if (client === null) return NOT_CONFIGURED

  const { error } = await client.auth.signOut()
  return error === null ? { ok: true } : failed(error.message)
}

/** The account restored from storage at startup, if any. */
export async function currentAccount(): Promise<Account | null> {
  const client = await getAuthClient()
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
  // The client arrives asynchronously since #1302 (lib/supabase.ts), so the
  // subscription is attached when it does and the unsubscribe handed back
  // covers both moments: called before the client lands it cancels the
  // attach, called after it detaches.
  let live = true
  let detach: (() => void) | null = null
  void Promise.resolve(getAuthClient())
    .then((client) => {
      if (!live || client === null || client === undefined) return
      const {
        data: { subscription },
      } = client.auth.onAuthStateChange((_event, session) => {
        listener(accountFromSession(session))
      })
      detach = () => subscription.unsubscribe()
    })
    .catch(() => {
      // The auth chunk did not arrive (lib/supabase.ts, which forgets the
      // failure so a later ask retries). Signed out is the state this whole
      // app is built to work in, so there is nothing to report and nobody to
      // report it to - but the rejection has to be taken, or it surfaces as
      // an unhandled rejection on every launch that hits it.
    })
  return () => {
    live = false
    detach?.()
  }
}
