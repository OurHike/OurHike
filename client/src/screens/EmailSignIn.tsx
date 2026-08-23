// Signing in with an email address, the provider that needs no external
// registration (features/AUTHENTICATION.md).
//
// Google and Apple need no screen at all - tapping the button leaves for the
// provider and comes back with a session. Email is the one that has to ask
// for something, which is why it is a screen rather than a branch inside
// SignInPrompt.
//
// **A link is the default, a password is the fallback.** A link is one field
// and nothing to remember six weeks up the trail from where it was set, and
// following it proves the address belongs to whoever asked - so it does the
// verification job without a second confirmation step. It also creates the
// account when the address is new, which is why there is no "sign up or sign
// in?" question before the form.
//
// The password path stays because a link has a real cost this app feels more
// than most: it means leaving for an email client and coming back, and on a
// ridge with one bar that round trip is the fragile part. Someone who set a
// password can finish without ever leaving the app.
//
// Neither path signs anyone in from this screen alone. A link has to be
// followed; a created account has to be confirmed. Both end here saying so,
// because reporting either as "signed in" would leave someone waiting to send
// a contribution that never would.

import { useState, type FormEvent } from 'react'
import type { AuthOutcome } from '../lib/auth'
import { signInMessage } from '../lib/authMessages'
import './reporting.css'

export interface EmailSignInProps {
  onMagicLink: (email: string) => Promise<AuthOutcome>
  onSignIn: (email: string, password: string) => Promise<AuthOutcome>
  onSignUp: (email: string, password: string) => Promise<AuthOutcome>
  onCancel: () => void
}

type Mode = 'link' | 'password' | 'create'

type Status =
  | { kind: 'idle' }
  | { kind: 'working' }
  | { kind: 'error'; message: string }
  | { kind: 'sent' }

const TITLES: Record<Mode, string> = {
  link: 'Sign in with email',
  password: 'Sign in with a password',
  create: 'Create an account',
}

const SUBMIT_LABELS: Record<Mode, string> = {
  link: 'Email me a sign-in link',
  password: 'Sign in',
  create: 'Create account',
}

export function EmailSignIn({
  onMagicLink,
  onSignIn,
  onSignUp,
  onCancel,
}: EmailSignInProps) {
  const [mode, setMode] = useState<Mode>('link')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })

  const working = status.kind === 'working'
  const needsPassword = mode !== 'link'

  function switchTo(next: Mode) {
    setMode(next)
    // Otherwise a failure from the path just abandoned reads as the new one
    // having already failed, before it has been tried.
    setStatus({ kind: 'idle' })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setStatus({ kind: 'working' })

    // Wrapped since #315. These three RETURN their failures rather than
    // throwing, so the try existed for nothing — right up until one of them
    // throws, which supabase-js does for a malformed response or a client it
    // could not build. There is no catch above this: the button would say
    // "Working…" for the rest of the session, disabled, with no way to try
    // again short of leaving the screen. A stuck primary button is worse than
    // an error, because an error is a thing a hiker can act on.
    let outcome: AuthOutcome
    try {
      outcome =
        mode === 'link'
          ? await onMagicLink(email)
          : mode === 'create'
            ? await onSignUp(email, password)
            : await onSignIn(email, password)
    } catch (error) {
      // Through the same mapper the RETURNED failures go through, so a thrown
      // one and a returned one read identically to the person in front of it
      // — and a thrown "Failed to fetch", which is what no signal looks like
      // here, still says "no signal" rather than falling to the general case.
      setStatus({
        kind: 'error',
        message: signInMessage(error instanceof Error ? error.message : String(error)),
      })
      return
    }

    if (!outcome.ok) {
      setStatus({ kind: 'error', message: outcome.message })
      return
    }
    // A password sign-in navigates away by itself once the session lands. The
    // other two are waiting on an email, and saying nothing would look like
    // they had failed.
    setStatus(mode === 'password' ? { kind: 'idle' } : { kind: 'sent' })
  }

  if (status.kind === 'sent') {
    return (
      <main className="reporting">
        <h1 className="reporting__title">Check your email</h1>
        <p className="reporting__saved" role="status">
          {mode === 'link'
            ? `A sign-in link is on its way to ${email}. Following it signs you in — you can close this. Anything you have written is still saved on your phone in the meantime.`
            : `A confirmation link is on its way to ${email}. Following it finishes the account. Anything you have written is still saved on your phone in the meantime.`}
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
      <h1 className="reporting__title">{TITLES[mode]}</h1>

      {mode === 'link' && (
        <p className="reporting__saved" role="status">
          No password to set or remember — we email you a link and following it signs you
          in.
        </p>
      )}

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

        {needsPassword && (
          <label className="reporting__field">
            <span className="reporting__field-label">Password</span>
            <input
              className="reporting__input"
              type="password"
              autoComplete={mode === 'create' ? 'new-password' : 'current-password'}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
        )}

        {status.kind === 'error' && (
          <p className="reporting__error" role="alert">
            {status.message}
          </p>
        )}

        <div className="reporting__actions">
          <button type="submit" className="reporting__primary" disabled={working}>
            {working ? 'Working…' : SUBMIT_LABELS[mode]}
          </button>

          {mode === 'link' ? (
            <button
              type="button"
              className="reporting__secondary"
              onClick={() => switchTo('password')}
            >
              Use a password instead
            </button>
          ) : (
            <button
              type="button"
              className="reporting__secondary"
              onClick={() => switchTo('link')}
            >
              Email me a link instead
            </button>
          )}

          {mode === 'password' && (
            <button
              type="button"
              className="reporting__secondary"
              onClick={() => switchTo('create')}
            >
              Create an account with a password
            </button>
          )}

          {mode === 'create' && (
            <button
              type="button"
              className="reporting__secondary"
              onClick={() => switchTo('password')}
            >
              I already have an account
            </button>
          )}

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
