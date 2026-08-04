// Email and password, the provider that needs no external registration
// (features/AUTHENTICATION.md, "Email + password. The plain option
// requested").
//
// Google and Apple need no screen at all - tapping the button leaves for the
// provider and comes back with a session. Email is the one that has to ask
// for something, which is why it is a screen rather than a branch inside
// SignInPrompt.
//
// Creating an account does not sign anyone in. Supabase sends a confirmation
// email and withholds the session until the link is followed, so this screen
// has a third outcome besides success and failure: "made, now go and confirm
// it". Collapsing that into "signed in" would leave someone waiting to send a
// contribution that never would.

import { useState, type FormEvent } from 'react'
import type { AuthOutcome } from '../lib/auth'
import './reporting.css'

export interface EmailSignInProps {
  onSignIn: (email: string, password: string) => Promise<AuthOutcome>
  onSignUp: (email: string, password: string) => Promise<AuthOutcome>
  onCancel: () => void
}

type Mode = 'sign-in' | 'create'

type Status =
  | { kind: 'idle' }
  | { kind: 'working' }
  | { kind: 'error'; message: string }
  | { kind: 'check-email' }

export function EmailSignIn({ onSignIn, onSignUp, onCancel }: EmailSignInProps) {
  const [mode, setMode] = useState<Mode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })

  const creating = mode === 'create'
  const working = status.kind === 'working'

  async function submit(event: FormEvent) {
    event.preventDefault()
    setStatus({ kind: 'working' })

    const outcome = creating
      ? await onSignUp(email, password)
      : await onSignIn(email, password)

    if (!outcome.ok) {
      setStatus({ kind: 'error', message: outcome.message })
      return
    }
    // Signing in navigates away by itself once the session lands. Creating an
    // account does not, and saying nothing would look like it had failed.
    setStatus(creating ? { kind: 'check-email' } : { kind: 'idle' })
  }

  if (status.kind === 'check-email') {
    return (
      <main className="reporting">
        <h1 className="reporting__title">Check your email</h1>
        <p className="reporting__saved" role="status">
          A confirmation link is on its way to {email}. Following it finishes the account.
          Anything you have written is still saved on your phone in the meantime.
        </p>
        <div className="reporting__actions">
          <button type="button" className="reporting__secondary" onClick={onCancel}>
            Done
          </button>
        </div>
      </main>
    )
  }

  return (
    <main className="reporting">
      <h1 className="reporting__title">
        {creating ? 'Create an account' : 'Sign in with email'}
      </h1>

      <form className="reporting__form" onSubmit={(event) => void submit(event)}>
        <label className="reporting__field">
          <span className="reporting__field-label">Email</span>
          <input
            className="reporting__input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label className="reporting__field">
          <span className="reporting__field-label">Password</span>
          <input
            className="reporting__input"
            type="password"
            autoComplete={creating ? 'new-password' : 'current-password'}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        {status.kind === 'error' && (
          <p className="reporting__error" role="alert">
            {status.message}
          </p>
        )}

        <div className="reporting__actions">
          <button type="submit" className="reporting__primary" disabled={working}>
            {working ? 'Working…' : creating ? 'Create account' : 'Sign in'}
          </button>
          <button
            type="button"
            className="reporting__secondary"
            onClick={() => {
              setMode(creating ? 'sign-in' : 'create')
              setStatus({ kind: 'idle' })
            }}
          >
            {creating ? 'I already have an account' : 'Create an account instead'}
          </button>
          <button type="button" className="reporting__secondary" onClick={onCancel}>
            Not now
          </button>
        </div>
      </form>

      <p className="reporting__reassurance" role="note">
        Reading the map never needs an account — water, shelters, closures and warnings
        are all there whether you sign in or not.
      </p>
    </main>
  )
}
