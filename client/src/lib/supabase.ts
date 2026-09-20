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

import type { SupabaseClient } from '@supabase/supabase-js'
import type { AuthProvider } from '../screens/SignInPrompt'

const PROJECT_URL: string = import.meta.env.VITE_SUPABASE_URL ?? ''
const ANON_KEY: string = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''

/** False when no Supabase project was configured at build time, so the UI can
 *  say so instead of offering a sign-in that cannot complete. */
export const AUTH_CONFIGURED = PROJECT_URL !== '' && ANON_KEY !== ''

/**
 * The sign-in doors this app ships, in the order the screen lays them out.
 *
 * IN CODE RATHER THAN CONFIGURATION, decided 2026-09-20 (#1572). This was
 * the `AUTH_PROVIDERS` repository variable until then, on the reasoning that
 * the providers do not cost the same to switch on and that a build must not
 * offer a button whose credentials do not exist. That reasoning still holds.
 * The mechanism did not, on four counts measured the day it was removed:
 *
 *   - IT BOUGHT NO PER-DEPLOYMENT DIFFERENCE. pages.yml, ua.yml and
 *     pr-preview.yml all read the same variable, so production, UA and every
 *     preview were always offering the same set anyway.
 *   - IT BOUGHT NO LIVE SWITCH. Production builds from a `v*` tag, so
 *     changing the variable still cost a build either way.
 *   - UNSET MEANT GOOGLE ALONE, SILENTLY. Nothing on screen and nothing in
 *     the build log named the cause. That is what it cost: half an hour on
 *     2026-09-20 hunting for buttons this code already had, because the
 *     variable had never been created.
 *   - IT PUT THE LIST WHERE NO TEST COULD SEE IT.
 *     `.github/tests/test_privacy_policy.py` asserts the privacy policy
 *     discloses every provider that ships. Its fixture could only read the
 *     code default, and its own docstring conceded the variable could widen
 *     the real set - so the policy was being checked against a list the
 *     deployed build did not use.
 *
 * What the variable did buy was one incident lever: `pages.yml` takes a
 * manual dispatch, so a provider could be dropped from production without a
 * merge. That was traded away deliberately. It is worth about ten minutes in
 * a bad hour, against a silently wrong answer on every ordinary day.
 *
 * SO CHANGING THIS LIST IS A COMMIT, and the review that comes with it is
 * the point rather than the cost. Every name here must be enabled in BOTH
 * Supabase projects with its credentials in place, or its button reaches an
 * error page instead of an account. `backend/check_supabase_config.py` reads
 * this very line and compares it against the live project, which is the
 * check that catches that before a hiker does.
 *
 * Apple is absent rather than forgotten: it needs a $99/yr Developer Program
 * membership and a Services ID, and is deferred to v2 (#92). Email is here
 * only because a sender is (LAUNCH_CHECKLIST.md 4.3c and 4.3d); without one,
 * Supabase's built-in mailer refuses every address outside the project's own
 * team, which lib/authMessages.ts says out loud rather than leaving a hiker
 * waiting for a code that was never sent.
 */
export const ENABLED_PROVIDERS: AuthProvider[] = ['google', 'github', 'email']

let client: Promise<SupabaseClient | null> | undefined

/**
 * The Supabase client, or null when this build has no project configured.
 *
 * Memoised rather than built at module scope so that importing anything in
 * this file - `AUTH_CONFIGURED`, `ENABLED_PROVIDERS` - does not construct a
 * client as a side effect. Several screens read the flag without ever needing
 * the client.
 *
 * ASYNC, AND THE LIBRARY ARRIVES THROUGH import() (#1302). `@supabase/*` is
 * some 200 KB raw in the built shell - auth, realtime, storage, postgrest,
 * a Phoenix socket - and it was parsed before the first frame of every launch
 * so that a session could be looked up on a Today screen that needs no
 * account. Nothing that calls this is on the first frame: sign-in is a tap
 * away, the moderator check and the outbox flush wait for an account, and
 * lib/useAuth.ts already renders signed-out until the stored session is read.
 * So the library loads when the first of them asks - from the service
 * worker's precache on the web, from the binary in the shells - and the
 * promise is shared so it loads once.
 */
export function getAuthClient(): Promise<SupabaseClient | null> {
  if (client === undefined) {
    client = AUTH_CONFIGURED
      ? import('@supabase/supabase-js').then(
          ({ createClient }) =>
            createClient(PROJECT_URL, ANON_KEY, {
              auth: {
                // Both default to true; named here because this app depends on
                // them in a way a reader should not have to infer.
                //
                // persistSession keeps a signed-in hiker signed in across the
                // app being killed and relaunched, which on a phone in a pocket
                // is routine rather than exceptional.
                persistSession: true,
                autoRefreshToken: true,
                // The OAuth redirect comes back to the app's own origin
                // carrying the code. There is no router (App.tsx), so nothing
                // else is watching the URL for it.
                detectSessionInUrl: true,
              },
            }),
          (error: unknown) => {
            // A CHUNK THAT DID NOT ARRIVE IS NOT AN ANSWER. Memoising the
            // rejection would make one dropped request - a deploy swapping
            // the assets mid-session, a tunnel at a trailhead - the state of
            // this app until it is relaunched: no sign-in, no outbox flush,
            // no live conditions, for the rest of the walk. Forgotten here,
            // so the next ask starts a fresh import; the caller still sees
            // this attempt fail.
            client = undefined
            throw error
          },
        )
      : Promise.resolve(null)
  }
  return client
}
