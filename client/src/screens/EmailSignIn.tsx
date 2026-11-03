// Signing in with an email address: a 6-digit code, typed into the app
// (features/AUTHENTICATION.md, #279).
//
// Google, Apple and GitHub need no screen at all - tapping the button leaves
// for the provider and comes back with a session. Email is the one that has
// to ask for something, which is why it is a screen rather than a branch
// inside SignInPrompt.
//
// A CODE, NOT A LINK AND NOT A PASSWORD. A link sends someone out to a mail
// app and asks them to come back, and on a phone the link opens the browser
// rather than the installed app, so the session can land where the app
// cannot see it. A password is something to set now and recall six weeks up
// the trail, and one reused from a breached site is exactly as safe as that
// site (LAUNCH_CHECKLIST.md 5a). A code has the one property the password
// was kept for - finishing without leaving the app - and none of the costs:
// nothing to remember, nothing to leak, and the session lands in the app's
// own storage because the request that earns it is made from here.
//
// Two steps on one screen: the address, then the code. One screen so the
// address is not typed twice and "send another code" is one tap. Neither
// step claims a sign-in. The session arriving is what closes this screen
// (App.tsx watches the account), so a refusal is the only outcome shown here.

import { useState, type FormEvent } from 'react'
import type { AuthOutcome } from '../lib/auth'
import { signInMessage } from '../lib/authMessages'
import './reporting.css'

export interface EmailSignInProps {
  /** Emails a code to the address, creating the account when it is new. */
  onSendCode: (email: string) => Promise<AuthOutcome>
  /** Signs in with the code that email carried. */
  onVerifyCode: (email: string, code: string) => Promise<AuthOutcome>
  onCancel: () => void
}

/**
 * The code's length, as a RANGE rather than a number, and #1600 is why.
 *
 * This was `CODE_LENGTH = 6` - Supabase's default - and the field was capped
 * at `CODE_LENGTH + 1`. The UA project's length is **8**. So the browser
 * silently dropped the last digit of every code a hiker typed, the truncated
 * value was refused, and the screen told them to check their six digits. It
 * could not be got right by being careful: the eighth character had nowhere
 * to go. Two attempts, both doomed, and the token was never even consumed.
 *
 * THE FIX IS TO STOP ASSUMING. Supabase allows 6 to 10 (Authentication ->
 * Providers -> Email), the setting is not readable from the client, and a
 * project that changes it must not break the app. So the field accepts the
 * whole range with room for a typed separator, the copy stops naming a
 * number it cannot know, and `backend/check_supabase_config.py` enforces the
 * project's setting falls inside this range rather than equalling one value.
 *
 * The old comment said this and the templates "agree by LAUNCH_CHECKLIST.md
 * 4.3d rather than by construction". That was true, and agreement by
 * documentation is exactly what failed here - nobody had run the check that
 * reads them back (#1572 step 3).
 */
export const MIN_CODE_LENGTH = 6
export const MAX_CODE_LENGTH = 10

/** Room for the range's top plus a separator a thumb types: "1234 5678".
 *  Generous on purpose - a cap that is too small loses characters in
 *  silence, which is the whole of #1600. */
export const CODE_FIELD_MAX = MAX_CODE_LENGTH + 2

type Step = 'address' | 'code'

type Status =
  | { kind: 'idle' }
  | { kind: 'working' }
  | { kind: 'error'; message: string }
  /** A second code was asked for from the code step. Said, so a tap on
   *  "Send another code" is not read as nothing having happened. */
  | { kind: 'resent' }

export function EmailSignIn({ onSendCode, onVerifyCode, onCancel }: EmailSignInProps) {
  const [step, setStep] = useState<Step>('address')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [status, setStatus] = useState<Status>({ kind: 'idle' })

  const working = status.kind === 'working'

  /**
   * Runs one of the two calls and turns whatever it does into a status.
   *
   * Wrapped since #315. Both handlers RETURN their failures rather than
   * throwing, so the try existed for nothing - right up until one of them
   * throws, which supabase-js does for a malformed response or a client it
   * could not build. There is no catch above this screen: the button would
   * say "Working…" for the rest of the session, disabled, with no way to try
   * again short of leaving the screen. A stuck primary button is worse than
   * an error, because an error is a thing a hiker can act on.
   *
   * A thrown failure goes through the same mapper the returned ones do, so
   * the two read identically to the person in front of them - and a thrown
   * "Failed to fetch", which is what no signal looks like here, still says
   * "no signal" rather than falling to the general case.
   */
  async function attempt(call: () => Promise<AuthOutcome>): Promise<boolean> {
    setStatus({ kind: 'working' })
    let outcome: AuthOutcome
    try {
      outcome = await call()
    } catch (error) {
      setStatus({
        kind: 'error',
        message: signInMessage(error instanceof Error ? error.message : String(error)),
      })
      return false
    }
    if (!outcome.ok) {
      setStatus({ kind: 'error', message: outcome.message })
      return false
    }
    return true
  }

  async function sendCode(event: FormEvent) {
    event.preventDefault()
    // Only the step moves on success. Saying "check your email" when nothing
    // was sent leaves someone waiting on a message that is not coming.
    if (await attempt(() => onSendCode(email))) {
      setCode('')
      setStatus({ kind: 'idle' })
      setStep('code')
    }
  }

  async function sendAnother() {
    if (await attempt(() => onSendCode(email))) setStatus({ kind: 'resent' })
  }

  async function verify(event: FormEvent) {
    event.preventDefault()
    // On success the session lands and App.tsx closes this screen; nothing
    // to say here. The field keeps its digits on a refusal so a hiker can
    // see what they typed against what the email says.
    if (await attempt(() => onVerifyCode(email, code))) setStatus({ kind: 'idle' })
  }

  function changeAddress() {
    setStep('address')
    setCode('')
    // Otherwise a failure from the step just abandoned reads as the new one
    // having already failed, before it has been tried.
    setStatus({ kind: 'idle' })
  }

  if (step === 'code') {
    return (
      <main className="reporting">
        <h1 className="reporting__title">Check your email</h1>
        <p className="reporting__saved" role="status">
          {status.kind === 'resent'
            ? `Another code is on its way to ${email}. `
            : `A code is on its way to ${email}. `}
          Type it here — no need to leave the app. Anything you have written is still
          saved on your phone in the meantime.
        </p>

        <form className="reporting__form" onSubmit={(event) => void verify(event)}>
          <label className="reporting__field">
            <span className="reporting__field-label">Code</span>
            <input
              className="reporting__input"
              // A numeric keypad, and the OS offering the code straight out
              // of the notification: both come from these two attributes
              // and neither from the type, which stays text so a leading
              // zero survives.
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9 ]*"
              maxLength={CODE_FIELD_MAX}
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
          </label>

          {status.kind === 'error' && (
            <p className="reporting__error" role="alert">
              {status.message}
            </p>
          )}

          <div className="reporting__actions">
            <button type="submit" className="reporting__primary" disabled={working}>
              {working ? 'Working…' : 'Sign in'}
            </button>
            <button
              type="button"
              className="reporting__secondary"
              disabled={working}
              onClick={() => void sendAnother()}
            >
              Send another code
            </button>
            <button
              type="button"
              className="reporting__secondary"
              onClick={changeAddress}
            >
              Use a different address
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

  return (
    <main className="reporting">
      <h1 className="reporting__title">Sign in with email</h1>

      <p className="reporting__saved" role="status">
        No password to set or remember — we email you a code and you type it in here. If
        you are new, that also creates your account.
      </p>

      <form className="reporting__form" onSubmit={(event) => void sendCode(event)}>
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

        {status.kind === 'error' && (
          <p className="reporting__error" role="alert">
            {status.message}
          </p>
        )}

        <div className="reporting__actions">
          <button type="submit" className="reporting__primary" disabled={working}>
            {working ? 'Working…' : 'Email me a code'}
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
