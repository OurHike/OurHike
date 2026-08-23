// Sign-in, asked at the first contribution and nowhere else
// (WIREFRAMES.md §6).
//
// Two things this screen has to say, both load-bearing:
//
// 1. What an account is NOT for. This is the only sign-in wall in OurHike,
//    and without naming what stays free it reads as a wall around the whole
//    app - which would be exactly backwards for a map whose premise is that
//    reading it needs nothing from you.
//
// 2. That the report is already saved. Someone asked to authenticate on a
//    ridge with one bar needs to know they can decline, or simply fail, and
//    still have what they wrote. The flow saves before asking (see
//    lib/contributionFlow.ts); this is where that promise gets made out loud.

export type AuthProvider = 'google' | 'apple' | 'email'

export interface SignInPromptProps {
  onSignIn: (provider: AuthProvider) => void
  onCancel: () => void
  /**
   * Which providers this build can actually complete. Defaults to all three,
   * which is what WIREFRAMES.md §6 specifies and what this screen is for.
   *
   * It is narrowable because the three do not cost the same to switch on -
   * Apple needs a $99/yr membership that Google and email do not - and a
   * button for a provider whose credentials do not exist reaches an error
   * page. Which set a given build offers is lib/supabase.ts's
   * ENABLED_PROVIDERS; the wireframe's answer is the default here, not a
   * decision this component makes.
   */
  providers?: AuthProvider[]
  /**
   * Whether a report is waiting in the outbox. True in the flow this screen
   * was drawn for (WIREFRAMES.md §6), so it defaults that way.
   *
   * False when the same screen is reached from the account row in Settings,
   * where there is no report - and saying one is saved would be a promise
   * about something that does not exist.
   */
  reportSaved?: boolean
  /**
   * Whether this phone has signal (#315).
   *
   * Defaults to true, which is what every surface that does not know says -
   * and is the right default: withholding sign-in from somebody who could
   * have used it is the worse of the two mistakes.
   *
   * WHY OFFLINE IS NOT MERELY "IT WILL FAIL"
   *
   * Google and Apple go through `signInWithOAuth`, which is a FULL OFF-ORIGIN
   * NAVIGATION - `lib/auth.ts` hands the browser to the provider. Offline
   * that lands on the browser's own error page, which is outside the service
   * worker's scope, so the hiker is not looking at a failed sign-in: they are
   * out of the app entirely, with no map, and the way back is the back button
   * they have to think of. On a trail that is the app disappearing at the
   * moment somebody reached for it.
   *
   * Email is different in kind and is left enabled: `signInWithOtp` is a
   * fetch, so it fails INSIDE the app with a sentence and the map still
   * behind it. A failure a hiker can read is not the same event as a failure
   * that takes the map away.
   */
  online?: boolean
}

const LABELS: Record<AuthProvider, string> = {
  google: 'Continue with Google',
  apple: 'Continue with Apple',
  email: 'Continue with email',
}

const ALL: AuthProvider[] = ['google', 'apple', 'email']

/** The providers that leave the app to sign in, and so cannot be offered
 *  without signal. See `online` on the props for why email is not one. */
const LEAVES_THE_APP: ReadonlySet<AuthProvider> = new Set(['google', 'apple'])

export function SignInPrompt({
  onSignIn,
  onCancel,
  providers = ALL,
  reportSaved = true,
  online = true,
}: SignInPromptProps) {
  const held = providers.filter((provider) => !online && LEAVES_THE_APP.has(provider))
  return (
    <main className="reporting">
      <h1 className="reporting__title">{reportSaved ? 'One thing first' : 'Sign in'}</h1>

      {reportSaved && (
        <p className="reporting__saved" role="status">
          Your report is already saved on your phone. Signing in is what lets it reach the
          people who can act on it.
        </p>
      )}

      <div className="reporting__actions">
        {providers.map((provider) => (
          <button
            key={provider}
            type="button"
            className="reporting__primary"
            onClick={() => onSignIn(provider)}
            disabled={held.includes(provider)}
          >
            {LABELS[provider]}
          </button>
        ))}
        <button type="button" className="reporting__secondary" onClick={onCancel}>
          Not now
        </button>
      </div>

      {held.length > 0 && (
        /* Said rather than left to be discovered by a dimmed button. The
           sentence names what is true - these two hand you to Google or
           Apple, which needs signal - and what is still available, because a
           hiker who came here to file a report should not conclude that
           signing in is off entirely. */
        <p className="reporting__note" role="note">
          {LABELS[held[0]].replace('Continue with ', '')}
          {held.length > 1
            ? ` and ${LABELS[held[1]].replace('Continue with ', '')}`
            : ''}{' '}
          need signal — they hand you to{' '}
          {held.length > 1 ? 'those services' : 'that service'} and back. Email works from
          here.
        </p>
      )}

      <p className="reporting__reassurance" role="note">
        Reading the map never needs an account — water, shelters, closures and warnings
        are all there whether you sign in or not.
      </p>
    </main>
  )
}
