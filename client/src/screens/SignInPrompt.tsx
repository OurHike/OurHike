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
}

const LABELS: Record<AuthProvider, string> = {
  google: 'Continue with Google',
  apple: 'Continue with Apple',
  email: 'Continue with email',
}

const ALL: AuthProvider[] = ['google', 'apple', 'email']

export function SignInPrompt({
  onSignIn,
  onCancel,
  providers = ALL,
  reportSaved = true,
}: SignInPromptProps) {
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
          >
            {LABELS[provider]}
          </button>
        ))}
        <button type="button" className="reporting__secondary" onClick={onCancel}>
          Not now
        </button>
      </div>

      <p className="reporting__reassurance" role="note">
        Reading the map never needs an account — water, shelters, closures and warnings
        are all there whether you sign in or not.
      </p>
    </main>
  )
}
