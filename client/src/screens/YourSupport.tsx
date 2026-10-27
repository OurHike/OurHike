// More → Your support (#1876): what this hiker gives, and the Stop button.
//
// STOP IS ONE TAP AND ONE CONFIRM, and then it is our job. The maintainer
// chose "we stop it for you" (frame A, poll 2026-10-23) over sending a
// hiker into the payment provider's own account pages. The backend asks
// Stripe to stop renewing (or the founder, by email, if Stripe cannot be
// reached), and emails the hiker once Stripe confirms it; until then the page
// says it is being cancelled rather than claiming it already is.
//
// WHAT THE PAGE OFFERS IS THE SERVER'S ANSWER: `can_stop` and `can_choose`
// on SupportSummary, so this file keeps no copy of the state machine (the
// #1885 architecture review). The provider is named on the website only;
// the store apps never name one.
//
// No reason is asked and no "are you sure you want to leave" is shown. The
// confirm says what stopping does - no more charges - and that $0 is fine.

import { useState } from 'react'
import { Capacitor } from '@capacitor/core'
import { stopSupport } from '../lib/supportApi'
import { useSupport } from '../lib/useSupport'
import { dollars, type LocalChoice, type SupportSummary } from '../lib/support'
import './support.css'

export interface YourSupportProps {
  /** False when this build has no backend: nothing to show but that. */
  apiConfigured: boolean
  signedIn: boolean
  server: SupportSummary | null
  local: LocalChoice | null
  /** The fetch failed; the last answer, if any, is still shown. */
  error: boolean
  now: Date
  onSignIn: () => void
  /** Open the ask at its choice, to pick or change a paid amount. */
  onChoose: () => void
  onStopped: (support: SupportSummary) => void
  /** Injected for tests. */
  stop?: typeof stopSupport
  native?: boolean
}

function day(iso: string | null): string {
  if (iso === null) return ''
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function YourSupport({
  apiConfigured,
  signedIn,
  server,
  local,
  error,
  now,
  onSignIn,
  onChoose,
  onStopped,
  stop = stopSupport,
  native = Capacitor.isNativePlatform(),
}: YourSupportProps) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [stopError, setStopError] = useState(false)

  async function confirmStop() {
    setBusy(true)
    setStopError(false)
    try {
      onStopped(await stop())
      setConfirming(false)
    } catch {
      setStopError(true)
    } finally {
      setBusy(false)
    }
  }

  const live =
    server !== null &&
    server.amount_cents !== null &&
    (server.status === 'active' ||
      server.status === 'pending' ||
      server.status === 'paused' ||
      server.status === 'cancel_scheduled')
  const via = !native && server?.provider_label ? ` · via ${server.provider_label}` : ''

  function meta(summary: SupportSummary): string {
    if (summary.status === 'pending') {
      return `Chosen ${day(summary.chosen_at)} · waiting for the payment to be confirmed`
    }
    if (summary.status === 'paused') return `Paused · nothing is being charged${via}`
    if (summary.status === 'cancel_scheduled') {
      return `No more charges · ends ${day(summary.period_end ?? summary.ended_at)}${via}`
    }
    return `Since ${day(summary.started_at)}${via}`
  }

  return (
    <section
      className="settings__group your-support"
      aria-labelledby="your-support-title"
    >
      <h2 className="settings__heading" id="your-support-title">
        Your support
      </h2>

      {!apiConfigured ? (
        <p className="settings__note">
          Support isn&rsquo;t switched on in this build yet. Everything in OurHike is free
          for everyone either way.
        </p>
      ) : live && server !== null && server.amount_cents !== null ? (
        <>
          <div className="your-support__card">
            <p className="your-support__amount">{dollars(server.amount_cents)} a year</p>
            <p className="your-support__meta">{meta(server)}</p>
          </div>
          {!server.can_stop ? (
            server.can_choose && (
              <button type="button" className="settings__action" onClick={onChoose}>
                Choose an amount again
              </button>
            )
          ) : confirming ? (
            <div
              className="your-support__confirm"
              role="group"
              aria-label="Stop your support"
            >
              <p className="your-support__confirm-title">
                Stop {dollars(server.amount_cents)} a year?
              </p>
              <p className="settings__note">
                No more charges. Everything in the app keeps working; this is
                pay-what-you-want, and $0 is fine.
              </p>
              {stopError && (
                <p className="support-ask__error" role="alert">
                  That didn&rsquo;t go through. Check your signal and try again.
                </p>
              )}
              <button
                type="button"
                className="your-support__stop your-support__stop--confirm"
                disabled={busy}
                onClick={() => void confirmStop()}
              >
                Yes, stop it
              </button>
              <button
                type="button"
                className="support-ask__secondary"
                onClick={() => setConfirming(false)}
              >
                Keep it
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="your-support__stop"
              onClick={() => setConfirming(true)}
            >
              Stop my support
            </button>
          )}
        </>
      ) : server !== null && server.status === 'stop_requested' ? (
        <div className="your-support__card">
          <p className="your-support__amount">Stop requested</p>
          <p className="your-support__meta">
            {day(server.stop_requested_at)}. We&rsquo;re cancelling it for you, and we
            email you when it&rsquo;s done. If a charge lands after today, reply to that
            email and we refund it.
          </p>
        </div>
      ) : server !== null && server.status === 'stopped' ? (
        <>
          <div className="your-support__card">
            <p className="your-support__amount">Stopped</p>
            <p className="your-support__meta">
              {server.started_at === null
                ? `${day(server.ended_at)}. Nothing was paid, so nothing needed cancelling. If you did pay, it shows up here once it's confirmed.`
                : `${day(server.ended_at)}. No more charges. Thank you for the time you gave.`}
            </p>
          </div>
          {server.can_choose && (
            <button type="button" className="settings__action" onClick={onChoose}>
              Choose an amount again
            </button>
          )}
        </>
      ) : (
        <>
          <p className="settings__note">
            {local !== null && local.year === now.getFullYear()
              ? `You chose $0 for ${local.year}. That's a real answer, and everything keeps working.`
              : "You haven't chosen yet this year. Everything keeps working either way."}
          </p>
          <button type="button" className="settings__action" onClick={onChoose}>
            Choose an amount
          </button>
          {!signedIn && (
            <button type="button" className="settings__action" onClick={onSignIn}>
              Already supporting? Sign in
            </button>
          )}
        </>
      )}

      {error && (
        <p className="settings__note" role="status">
          Couldn&rsquo;t reach our server just now; this may be out of date.
        </p>
      )}

      {/* The ideals page, in the website app only: it describes payment, and
          the store apps keep every road to a payment off their screens. */}
      {!native && (
        <a
          className="settings__link your-support__why"
          href="https://ourhike.org/support/"
          target="_blank"
          rel="noreferrer"
        >
          Why OurHike is pay-what-you-want
          <span className="settings__link-hint">
            The story, and where every dollar goes
          </span>
        </a>
      )}
    </section>
  )
}

export interface YourSupportPageProps {
  apiConfigured: boolean
  signedIn: boolean
  onSignIn: () => void
  onChoose: () => void
}

/**
 * The page as More renders it: `YourSupport` with the account's answer
 * fetched here, so the shell holds none of it (screens/SupportGate.tsx says
 * why the shell is kept out of this).
 */
export function YourSupportPage({
  apiConfigured,
  signedIn,
  onSignIn,
  onChoose,
}: YourSupportPageProps) {
  const support = useSupport(signedIn)
  return (
    <YourSupport
      apiConfigured={apiConfigured}
      signedIn={signedIn}
      server={support.server}
      local={support.local}
      error={support.error}
      now={new Date()}
      onSignIn={onSignIn}
      onChoose={onChoose}
      onStopped={support.replace}
    />
  )
}
