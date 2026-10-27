// The day-5 ask (#1876): choose what you give, $0 included.
//
// THREE VIEWS IN ONE WINDOW, chrome/SignInWindow.tsx's own pattern: the
// choice, then either the $0 nudge or the paid confirmation, then where a
// paid choice goes next. The window stays put and its contents change.
//
// REQUIRED, AND STILL ONE TAP FROM THE MAP. The maintainer chose a choice
// that cannot be skipped (frame B, poll 2026-10-23), so the first two views
// have no "Not now" and Escape does nothing on them. What keeps that from
// standing between a hiker and the water source they opened the app for is
// that $0 is one of the answers: "$0", then "Keep it at $0", and the map is
// back. That is two taps at worst, once a year.
//
// THE $0 NUDGE IS FORCEFUL BY DESIGN AND NEVER A TRAP. Its paid buttons are
// big; "Keep it at $0" is an underlined link under them, always on screen
// and readable - the maintainer's choice over a full button and over a
// second confirm step, which would have read as a dark pattern. Every
// button label names its amount, whatever the joke around it.
//
// NO PAYMENT IN THE APP. The website app sends a paid choice on to the
// payment provider's page, and only to an https one; in the store apps
// (`native`) the last button is "Email me how to set it up", and the link
// travels by email, which Apple's 3.1.3 allows and its 3.1.1(a) and Google's
// Payments policy do not allow in the app. See lib/support.ts for the sources.
//
// NO PROVIDER IS NAMED HERE. Which provider takes the money is the backend's
// setting (app/core/support_providers/), and copy that named one would turn
// a provider move into a release - the #1885 architecture review.

import { useState } from 'react'
import { Capacitor } from '@capacitor/core'
import { SignInWindow } from '../chrome/SignInWindow'
import { chooseSupport, type SupportChoiceReceipt } from '../lib/supportApi'
import { nudgeFor } from '../lib/supportNudges'
import {
  dollars,
  TIERS,
  writeZeroChoice,
  type PaidTier,
  type SupportSummary,
  type Tier,
} from '../lib/support'
import './support.css'

export type AskView =
  | { kind: 'choose' }
  | { kind: 'nudge' }
  | { kind: 'confirm'; tier: PaidTier }
  | { kind: 'sent'; tier: PaidTier }

export interface SupportAskProps {
  /** Days counted this year, for the opening line. */
  days: number
  /** The signed-in account's email, or null when signed out. */
  accountEmail: string | null
  /** Where to start - 'confirm' when a hiker returns from signing in with a
   *  paid tier already picked. */
  initial?: AskView
  /** Signed out with a paid tier picked: remember it and open sign-in. */
  onSignIn: (tier: PaidTier) => void
  /** The backend's answer to a paid choice, so the shell can stop asking. */
  onChosen: (support: SupportSummary) => void
  /** The window is done: $0 kept, a paid choice sent on, or emailed. */
  onClose: () => void
  /** Injected for tests; the store apps are `true`. */
  native?: boolean
  now?: () => Date
  /** Injected for tests: where the website app goes to pay. */
  navigate?: (url: string) => void
  choose?: typeof chooseSupport
}

const TIER_LINES: Record<Tier, string> = {
  100: 'Pay what you can.',
  1000: 'Pay what you want.',
  10000: 'Pay it forward.',
  0: "I can't right now. Trails are for everyone, and so is this map.",
}

export function SupportAsk({
  days,
  accountEmail,
  initial = { kind: 'choose' },
  onSignIn,
  onChosen,
  onClose,
  native = Capacitor.isNativePlatform(),
  now = () => new Date(),
  navigate = (url) => window.location.assign(url),
  choose = chooseSupport,
}: SupportAskProps) {
  const [view, setView] = useState<AskView>(initial)
  const [picked, setPicked] = useState<Tier | null>(
    initial.kind === 'confirm' ? initial.tier : null,
  )
  const [accounting, setAccounting] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function keepZero() {
    writeZeroChoice(now())
    onClose()
  }

  async function submit(tier: PaidTier) {
    if (accountEmail === null) {
      onSignIn(tier)
      return
    }
    setBusy(true)
    setError(null)
    let receipt: SupportChoiceReceipt
    try {
      receipt = await choose({
        amount_cents: tier,
        accounting_email: accounting,
        delivery: native ? 'email' : 'redirect',
      })
    } catch {
      setBusy(false)
      setError(
        "That didn't go through. Check your signal and try again; nothing was charged.",
      )
      return
    }
    onChosen(receipt.support)
    if (!native) {
      // Only ever a payment page over https: the URL comes from the server,
      // and `javascript:` or plain http is not somewhere a payment goes.
      if (receipt.checkout_url?.startsWith('https://')) {
        navigate(receipt.checkout_url)
        return
      }
      setBusy(false)
      setError(
        "Payments aren't available just now. Your choice is saved; nothing was charged.",
      )
      return
    }
    setBusy(false)
    if (receipt.emailed) {
      setView({ kind: 'sent', tier })
    } else {
      setError(
        "We couldn't send the email just now. Your choice is saved; try again from More → Your support.",
      )
    }
  }

  // Escape and a tap outside go back one step from the confirmation, and do
  // nothing on the two views a hiker must answer.
  function onWindowClose() {
    if (view.kind === 'confirm') setView({ kind: 'choose' })
    else if (view.kind === 'sent') onClose()
  }

  const label =
    view.kind === 'nudge'
      ? 'Before you pick $0'
      : view.kind === 'confirm'
        ? 'Confirm your choice'
        : view.kind === 'sent'
          ? 'Check your email'
          : 'Choose what you give'

  return (
    <SignInWindow label={label} onClose={onWindowClose}>
      {view.kind === 'choose' && (
        <section className="support-ask">
          <h1 className="support-ask__title">
            OurHike runs on what hikers choose to give
          </h1>
          <p className="support-ask__body">
            You&rsquo;ve used OurHike on {days} {days === 1 ? 'day' : 'days'} this year.
            Once a year we ask everyone to choose.{' '}
            <strong>Any choice, including $0, keeps everything working.</strong>
          </p>
          <div
            className="support-ask__tiers"
            role="radiogroup"
            aria-label="Choose an amount"
          >
            {([...TIERS, 0] as const).map((tier) => (
              <button
                key={tier}
                type="button"
                role="radio"
                aria-checked={picked === tier}
                // Spelled out: read from the spans, the amount and its
                // period run together ("$1a year") for a screen reader.
                aria-label={`${dollars(tier)}${tier === 0 ? '' : ' a year'}: ${TIER_LINES[tier]}`}
                className={`support-ask__tier${tier === 0 ? ' support-ask__tier--zero' : ''}`}
                onClick={() => setPicked(tier)}
              >
                <span className="support-ask__amount">
                  {dollars(tier)}
                  {tier !== 0 && <small> a year</small>}
                </span>
                <span className="support-ask__what">{TIER_LINES[tier]}</span>
              </button>
            ))}
          </div>
          <button
            type="button"
            className="support-ask__primary"
            disabled={picked === null}
            onClick={() => {
              if (picked === null) return
              if (picked === 0) setView({ kind: 'nudge' })
              else setView({ kind: 'confirm', tier: picked })
            }}
          >
            Continue
          </button>
          <p className="support-ask__fine">
            {native
              ? 'Nothing is paid in this app. A paid choice is set up by email.'
              : 'Payments happen on a payment page, never in the app.'}{' '}
            Stopping takes two taps: More → Your support → Stop.
          </p>
        </section>
      )}

      {view.kind === 'nudge' && (
        <ZeroNudge
          now={now()}
          onPick={(tier) => {
            setPicked(tier)
            setView({ kind: 'confirm', tier })
          }}
          onKeepZero={keepZero}
        />
      )}

      {view.kind === 'confirm' && (
        <section className="support-ask">
          <h1 className="support-ask__title">{dollars(view.tier)} a year</h1>
          <p className="support-ask__body">
            Recurring once a year. Stop any time: More → Your support → Stop, and we
            cancel it for you.
          </p>
          {accountEmail !== null ? (
            <p className="support-ask__email">
              {native ? 'The setup link goes to ' : 'The payment page will know you as '}
              <strong>{accountEmail}</strong>. Use that same address when you pay, so the
              app can tell it&rsquo;s you.
            </p>
          ) : (
            <p className="support-ask__email">
              Sign in first, so your choice follows you to every phone you use and the app
              stops asking. Browsing the map never needs an account; only a paid choice
              does.
            </p>
          )}
          <p className="support-ask__term">
            If OurHike ever changes payment provider, we&rsquo;ll email you once to move
            it. Nothing moves without you.
          </p>
          <label className="support-ask__check">
            <input
              type="checkbox"
              checked={accounting}
              onChange={(event) => setAccounting(event.target.checked)}
            />
            <span>Email me the yearly accounting of where the money went.</span>
          </label>
          {error !== null && (
            <p className="support-ask__error" role="alert">
              {error}
            </p>
          )}
          <button
            type="button"
            className="support-ask__primary"
            disabled={busy}
            onClick={() => void submit(view.tier)}
          >
            {accountEmail === null
              ? 'Sign in to continue'
              : native
                ? 'Email me how to set it up'
                : 'Continue to payment'}
          </button>
          <button
            type="button"
            className="support-ask__secondary"
            onClick={() => setView({ kind: 'choose' })}
          >
            Back
          </button>
          <p className="support-ask__fine">
            Not tax-deductible: OurHike isn&rsquo;t a nonprofit yet.
          </p>
        </section>
      )}

      {view.kind === 'sent' && (
        <section className="support-ask">
          <h1 className="support-ask__title">Check your email</h1>
          <p className="support-ask__body">
            We sent the link to set up {dollars(view.tier)} a year to{' '}
            <strong>{accountEmail}</strong>. The app stops asking now.
          </p>
          <p className="support-ask__fine">
            No link here on purpose: app stores don&rsquo;t allow one.
          </p>
          <button type="button" className="support-ask__primary" onClick={onClose}>
            Back to the map
          </button>
        </section>
      )}
    </SignInWindow>
  )
}

interface ZeroNudgeProps {
  now: Date
  onPick: (tier: PaidTier) => void
  onKeepZero: () => void
}

/** The once-a-year screen after "$0" - this year's line for this phone. */
function ZeroNudge({ now, onPick, onKeepZero }: ZeroNudgeProps) {
  const nudge = nudgeFor(now)
  return (
    <section className="support-nudge">
      <p className="support-nudge__eyebrow">Day five · you picked $0</p>
      <h1 className="support-nudge__title">{nudge.title}</h1>
      <p className="support-nudge__body">{nudge.body}</p>
      <button type="button" className="support-nudge__one" onClick={() => onPick(100)}>
        {nudge.one}
      </button>
      <button type="button" className="support-nudge__ten" onClick={() => onPick(1000)}>
        {nudge.ten}
      </button>
      <button type="button" className="support-nudge__zero" onClick={onKeepZero}>
        {nudge.zero}
      </button>
      <p className="support-nudge__fine">
        $0 is a real answer. Everything keeps working either way.
      </p>
    </section>
  )
}
