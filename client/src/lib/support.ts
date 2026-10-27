// What a hiker chose to give OurHike, and when the app asks (#1876).
//
// THE DECISIONS THIS ENCODES are the maintainer's, by poll on 2026-10-23,
// each answered against a drawn mock:
//
//   - On the 5th distinct day of use in a calendar year (lib/activeDays.ts)
//     the app asks every hiker to choose $0, $12, $60 or $120 a year. The
//     choice is required, and **$0 is a choice**: it keeps everything
//     working, and nothing anywhere is locked by not paying.
//   - $0 stays on this phone and needs no account. A paid choice is
//     verified through a signed-in account: the backend matches the payment
//     provider's signed webhooks to it (Stripe's, since 2026-10-27).
//   - Picking $0 brings one more screen, at most once a year: a nudge
//     toward $12 or $60 in a hiker-trash voice, with a line that rotates
//     (lib/supportNudges.ts). "Keep it at $0" stays on that screen and
//     readable.
//   - Payment never happens inside the app. The website app continues to
//     the provider's page; the iOS and Android apps send the setup link by email
//     instead, because Apple's 3.1.1(a) bars buttons and links to a
//     non-in-app purchase outside the US and Google's Payments policy bars
//     leading users to another payment method (read 2026-10-23).
//   - Backend first: with no API configured the ask never appears
//     (`shouldAsk`), so a paid choice is verified from its first day live.
//
// NOTHING HERE GATES ANYTHING. This module decides whether to ASK; no
// feature in the app reads a support state to decide what a hiker may see.
// That is OurHikeValues.md #5 and PRICING_MODEL.md's pricing value #1.

import { activeDaysThisYear } from './activeDays'
import type { SupportSummary } from './api'

/** The fifth distinct day of use in a calendar year. The maintainer's
 *  number, not a measured one. */
export const ASK_ON_DAY = 5

/** The four answers, in cents a year: $12, $60 and $120, which are $1, $5 and
 *  $10 a month (the maintainer's tiers, 2026-10-27, replacing $1, $10 and
 *  $100). Yearly, the maintainer's choice over monthly: one card charge a
 *  year instead of twelve, so the 30¢ card fee is paid once. */
export const TIERS = [1200, 6000, 12000] as const
export type PaidTier = (typeof TIERS)[number]
export type Tier = 0 | PaidTier

/** How long a paid choice waits for the provider to confirm before the
 *  app asks again. @unvalidated - long enough for somebody to open the
 *  email on a town day, short enough that a choice nobody completed does
 *  not silence the ask for most of a season. What would settle it: how long
 *  real completions take, which nobody has measured. */
export const PENDING_GRACE_DAYS = 30

/** `$12`, `$60`, `$120`. */
export function dollars(cents: number): string {
  return `$${(cents / 100).toLocaleString('en-US')}`
}

// ---- The $0 choice, on this phone ----

export const LOCAL_CHOICE_KEY = 'ourhike:support'

/** Fired on this window when the local record changes. */
const CHANGED = 'ourhike:support-changed'

export interface LocalChoice {
  /** The calendar year the $0 answer covers. */
  year: number
  /** When the hiker answered, ISO. */
  chosenAt: string
}

export function readLocalChoice(): LocalChoice | null {
  try {
    const raw = localStorage.getItem(LOCAL_CHOICE_KEY)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      typeof (parsed as LocalChoice).year === 'number' &&
      typeof (parsed as LocalChoice).chosenAt === 'string'
    ) {
      return parsed as LocalChoice
    }
    return null
  } catch {
    return null
  }
}

/** Record "$0 this year". The only choice this phone keeps by itself. */
export function writeZeroChoice(now: Date): void {
  try {
    localStorage.setItem(
      LOCAL_CHOICE_KEY,
      JSON.stringify({ year: now.getFullYear(), chosenAt: now.toISOString() }),
    )
  } catch {
    // Storage refused: the answer holds for this page load, and the ask
    // returns next launch. An extra question, never a wrong charge.
  }
  window.dispatchEvent(new Event(CHANGED))
}

export function onLocalChoiceChanged(listener: () => void): () => void {
  window.addEventListener(CHANGED, listener)
  window.addEventListener('storage', listener)
  return () => {
    window.removeEventListener(CHANGED, listener)
    window.removeEventListener('storage', listener)
  }
}

// ---- A paid choice, as the backend holds it ----

// The account's paid choice is `SupportSummary`, declared in lib/api.ts
// beside the other server shapes so backend/tests/test_client_response_
// contract.py can hold it to what `GET /support/me` sends.
export type { SupportStatus, SupportSummary } from './api'

// ---- Whether to ask ----

export interface AskInputs {
  now: Date
  /** `API_CONFIGURED` - false keeps the ask dormant (backend first). */
  apiConfigured: boolean
  /**
   * Whether the phone has signal. NO SIGNAL MOSTLY MEANS ON TRAIL, and the
   * ask covers the map until it is answered - so it waits, rather than
   * standing between a hiker and the water source or the way off they
   * opened the app for (maintainer, poll 2026-10-24, over also waiting on a
   * running hike and over asking regardless). A paid choice cannot complete
   * offline either way. It asks at the next launch with signal.
   */
  online: boolean
  /** The account's support, when signed in and fetched; null otherwise. */
  server: SupportSummary | null
  /** Days counted this year. Defaults to lib/activeDays.ts's. */
  days?: number
  /** The local $0 record. Defaults to this phone's. */
  local?: LocalChoice | null
}

function sameYear(iso: string | null, year: number): boolean {
  return iso !== null && new Date(iso).getFullYear() === year
}

/**
 * Whether the day-5 ask should open now.
 *
 * Asks when every one of these holds:
 *   - a backend is configured (a paid choice could be verified);
 *   - the phone has signal (see `AskInputs.online`);
 *   - this phone has counted `ASK_ON_DAY` days this year;
 *   - no $0 answer on this phone for this year;
 *   - the account (when there is one) holds no live paid choice: not
 *     `supporting` (the server's answer), not `pending` within
 *     `PENDING_GRACE_DAYS`, and not stopped this year (a hiker who just
 *     pressed Stop is not asked again until next year).
 */
export function shouldAsk(inputs: AskInputs): boolean {
  const { now, apiConfigured, online, server } = inputs
  if (!apiConfigured || !online) return false

  const days = inputs.days ?? activeDaysThisYear(now)
  if (days < ASK_ON_DAY) return false

  const year = now.getFullYear()
  const local = inputs.local === undefined ? readLocalChoice() : inputs.local
  if (local !== null && local.year === year) return false

  if (server !== null) {
    if (server.supporting) return false
    if (server.status === 'pending' && server.chosen_at !== null) {
      const waited = (now.getTime() - new Date(server.chosen_at).getTime()) / 86_400_000
      if (waited < PENDING_GRACE_DAYS) return false
    }
    if (
      server.status === 'stopped' &&
      (sameYear(server.stop_requested_at, year) || sameYear(server.ended_at, year))
    ) {
      return false
    }
  }
  return true
}

/**
 * The More row's second line - here rather than beside the screen it
 * summarises, so the shell can print it without loading that screen
 * (screens/deferred.ts, LAUNCH_BUDGET.md §3).
 */
export function supportSummaryLine(
  server: SupportSummary | null,
  local: LocalChoice | null,
  now: Date,
): string {
  if (server !== null && server.amount_cents !== null) {
    const amount = `${dollars(server.amount_cents)} a year`
    if (server.status === 'active') return amount
    if (server.status === 'pending') return `${amount}, waiting to be confirmed`
    if (server.status === 'paused') return `${amount}, paused`
    if (server.status === 'cancel_scheduled') return `${amount}, ending`
    if (server.status === 'stop_requested') return 'Stopping'
    if (server.status === 'stopped') return 'Stopped'
  }
  if (local !== null && local.year === now.getFullYear()) return '$0 this year'
  return 'Pay what you want, $0 included'
}
