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
}

const PROVIDERS: Array<{ id: AuthProvider; label: string }> = [
  { id: 'google', label: 'Continue with Google' },
  { id: 'apple', label: 'Continue with Apple' },
  { id: 'email', label: 'Continue with email' },
]

export function SignInPrompt({ onSignIn, onCancel }: SignInPromptProps) {
  return (
    <main className="reporting">
      <h1 className="reporting__title">One thing first</h1>

      <p className="reporting__saved" role="status">
        Your report is already saved on your phone. Signing in is what lets it reach the
        people who can act on it.
      </p>

      <div className="reporting__actions">
        {PROVIDERS.map((provider) => (
          <button
            key={provider.id}
            type="button"
            className="reporting__primary"
            onClick={() => onSignIn(provider.id)}
          >
            {provider.label}
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
