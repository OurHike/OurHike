// Sign-in: asked at the first contribution, and offered from the account
// button at any time (WIREFRAMES.md §6, as #1596 rewrote it - this line said
// "and nowhere else" until then, which is what §6 said until then too).
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

import { ProviderMark } from '../chrome/ProviderMark'

export type AuthProvider = 'google' | 'apple' | 'github' | 'email'

export interface SignInPromptProps {
  onSignIn: (provider: AuthProvider) => void
  onCancel: () => void
  /**
   * Which providers this build can actually complete. Defaults to all four:
   * WIREFRAMES.md §6's Google / Apple / email, plus GitHub (#1572).
   *
   * It is narrowable because the four do not cost the same to switch on -
   * Google and GitHub each need a free OAuth registration, Apple a $99/yr
   * membership, and email a sender behind the project (LAUNCH_CHECKLIST.md
   * 4.3) - and a button for a provider whose credentials do not exist
   * reaches an error page. Which set a given build offers is
   * lib/supabase.ts's ENABLED_PROVIDERS; the full set is the default here,
   * not a decision this component makes.
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
   * Google, Apple and GitHub go through `signInWithOAuth`, which is a FULL OFF-ORIGIN
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
  /**
   * Why the last attempt did not sign anybody in, when this ask is being
   * shown BECAUSE one did not (#1573).
   *
   * The Google and GitHub buttons are a full off-origin navigation, so a
   * refusal lands back here as a fresh page load with the failure on the URL
   * and no component left alive to have been told about it. `App.tsx` reads
   * it at boot (lib/authRefusal.ts), re-opens this ask, and hands the
   * sentence down here - which is what makes the two paths that leave the
   * app say something, as #397's acceptance requires of all of them.
   *
   * Above the buttons rather than beside the one that failed: which button
   * it was is not in the URL, and putting the sentence under a guess is
   * worse than putting it where the eye already is.
   */
  refusal?: string | null
}

const LABELS: Record<AuthProvider, string> = {
  google: 'Continue with Google',
  apple: 'Continue with Apple',
  github: 'Continue with GitHub',
  email: 'Continue with email',
}

const ALL: AuthProvider[] = ['google', 'apple', 'github', 'email']

/** The providers that leave the app to sign in, and so cannot be offered
 *  without signal. See `online` on the props for why email is not one. */
const LEAVES_THE_APP: ReadonlySet<AuthProvider> = new Set(['google', 'apple', 'github'])

/** The provider names as the offline note reads them out, in the order
 *  `ENABLED_PROVIDERS` gives them, since `held` is a filter over that array:
 *  "GitHub", "GitHub and Google". Those two are the only strings this build
 *  can produce - email never leaves the app, and Apple does not ship (#92).
 *  The examples here were "Google", "Google and Apple", "Google, Apple and
 *  GitHub" until the order changed and none of the three was reachable. */
function namesOf(providers: AuthProvider[]): string {
  const names = providers.map((provider) =>
    LABELS[provider].replace('Continue with ', ''),
  )
  if (names.length <= 1) return names.join('')
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}

export function SignInPrompt({
  onSignIn,
  onCancel,
  providers = ALL,
  reportSaved = true,
  online = true,
  refusal = null,
}: SignInPromptProps) {
  const held = providers.filter((provider) => !online && LEAVES_THE_APP.has(provider))
  return (
    <main className="reporting">
      <h1 className="reporting__title">{reportSaved ? 'One thing first' : 'Sign in'}</h1>

      {refusal !== null && (
        /* `role="alert"` for the same reason EmailSignIn's failures carry
           one: this window opened by itself, so a screen reader that was not
           told would be handed three buttons and no reason for them. First
           in the panel because it is the answer to "why am I looking at
           this", which is the question the hiker arrives with. */
        <p className="reporting__error" role="alert">
          {refusal}
        </p>
      )}

      {reportSaved && (
        <p className="reporting__saved" role="status">
          Your report is already saved on your phone. Signing in is what lets it reach the
          people who can act on it.
        </p>
      )}

      <div className="reporting__actions">
        {/* Each door in its provider's own colours, with its own mark
            (chrome/ProviderMark.tsx, #1572): Google's and GitHub's brand
            pages say what their buttons may look like, and a sign-in button
            that does not look like the provider's is one a hiker hesitates
            over. The label stays the accessible name; the mark is decoration. */}
        {providers.map((provider) => (
          <button
            key={provider}
            type="button"
            className={`reporting__provider reporting__provider--${provider}`}
            onClick={() => onSignIn(provider)}
            disabled={held.includes(provider)}
          >
            <ProviderMark provider={provider} />
            <span>{LABELS[provider]}</span>
          </button>
        ))}
        <button type="button" className="reporting__secondary" onClick={onCancel}>
          Not now
        </button>
      </div>

      {held.length > 0 && (
        /* Said rather than left to be discovered by a dimmed button. The
           sentence names what is true - these hand you to Google, Apple or
           GitHub, which needs signal - and what is still available, because
           a hiker who came here to file a report should not conclude that
           signing in is off entirely. "Email works from here" is only said
           when this build offers email; the code it sends is a fetch, which
           fails inside the app rather than taking the map away. */
        <p className="reporting__note" role="note">
          {namesOf(held)} {held.length > 1 ? 'need' : 'needs'} signal —{' '}
          {held.length > 1 ? 'they hand' : 'it hands'} you to{' '}
          {held.length > 1 ? 'those services' : 'that service'} and back.
          {providers.includes('email') ? ' Email works from here.' : ''}
        </p>
      )}

      <p className="reporting__reassurance" role="note">
        Reading the map never needs an account — water, shelters, closures and warnings
        are all there whether you sign in or not.
      </p>
    </main>
  )
}
