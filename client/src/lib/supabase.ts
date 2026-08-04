// The Supabase project this build authenticates against.
//
// Same build-time shape as lib/config.ts's data bucket, and for the same
// reason: which project a build talks to is not knowable from the source
// tree. Vite inlines VITE_-prefixed variables at build time, so changing
// either value is a rebuild, not a restart.
//
// An unconfigured build gets a null client rather than a half-built one.
// createClient() accepts a blank URL without complaint and only fails at the
// first request, which would reach a hiker as a sign-in that hangs - the same
// failure DATA_CONFIGURED exists to prevent for downloads.

import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import type { AuthProvider } from '../screens/SignInPrompt'

const PROJECT_URL: string = import.meta.env.VITE_SUPABASE_URL ?? ''
const ANON_KEY: string = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''

/** False when no Supabase project was configured at build time, so the UI can
 *  say so instead of offering a sign-in that cannot complete. */
export const AUTH_CONFIGURED = PROJECT_URL !== '' && ANON_KEY !== ''

// Which providers this build offers. Configurable because the three do not
// cost the same to switch on: email needs nothing, Google needs a Cloud
// Console registration, and Apple needs a $99/yr Developer Program membership
// and a Services ID (LAUNCH_CHECKLIST.md 4.3, which already says "nothing in
// the code assumes all three").
//
// This is about what a *build* offers, not what a hiker prefers - a button for
// a provider whose credentials do not exist yet is a button that reaches an
// error page, which is worse than an absent option.
const ALL_PROVIDERS: readonly AuthProvider[] = ['google', 'apple', 'email']

/**
 * Parses the configured provider list, keeping ALL_PROVIDERS' order rather
 * than the order they were written in - so the buttons cannot be reshuffled
 * by a typo in an env var, and two builds that enable the same set present it
 * the same way.
 *
 * Unknown names are dropped rather than thrown on: this value arrives from a
 * host's build settings, where a stray comma should cost one button, not the
 * whole app's boot.
 */
export function parseProviders(raw: string): AuthProvider[] {
  const named = new Set(
    raw
      .split(',')
      .map((name) => name.trim().toLowerCase())
      .filter((name) => name !== ''),
  )
  return ALL_PROVIDERS.filter((provider) => named.has(provider))
}

/** Defaults to Google and email: the two whose setup costs nothing beyond a
 *  console registration. Apple is opt-in for the membership fee. */
export const ENABLED_PROVIDERS = parseProviders(
  import.meta.env.VITE_AUTH_PROVIDERS ?? 'google,email',
)

let client: SupabaseClient | null | undefined

/**
 * The Supabase client, or null when this build has no project configured.
 *
 * Memoised rather than built at module scope so that importing anything in
 * this file - `AUTH_CONFIGURED`, `parseProviders` - does not construct a
 * client as a side effect. Several screens read the flag without ever needing
 * the client.
 */
export function getAuthClient(): SupabaseClient | null {
  if (client === undefined) {
    client = AUTH_CONFIGURED
      ? createClient(PROJECT_URL, ANON_KEY, {
          auth: {
            // Both default to true; named here because this app depends on
            // them in a way a reader should not have to infer.
            //
            // persistSession keeps a signed-in hiker signed in across the app
            // being killed and relaunched, which on a phone in a pocket is
            // routine rather than exceptional.
            persistSession: true,
            autoRefreshToken: true,
            // The OAuth redirect comes back to the app's own origin carrying
            // the code. There is no router (App.tsx), so nothing else is
            // watching the URL for it.
            detectSessionInUrl: true,
          },
        })
      : null
  }
  return client
}
