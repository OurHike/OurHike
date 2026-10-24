// What a hiker chose to give OurHike, and when the app asks (#1876).
//
// THE DECISIONS THIS ENCODES are the maintainer's, by poll on 2026-10-23,
// each answered against a drawn mock:
//
//   - On the 5th distinct day of use in a calendar year (lib/activeDays.ts)
//     the app asks every hiker to choose $0, $1, $10 or $100 a year. The
//     choice is required, and **$0 is a choice**: it keeps everything
//     working, and nothing anywhere is locked by not paying.
//   - $0 stays on this phone and needs no account. A paid choice is
//     verified through a signed-in account: the backend matches Buy Me a
//     Coffee's signed membership webhooks to the account's email.
//   - Picking $0 brings one more screen, at most once a year: a nudge
//     toward $1 or $10 in a hiker-trash voice, with a line that rotates
//     (`nudgeFor`). "Keep it at $0" stays on that screen and readable.
//   - Payment never happens inside the app. The website app continues to
//     Buy Me a Coffee; the iOS and Android apps send the setup link by email
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

/** The four answers, in cents a year. Yearly, the maintainer's choice over
 *  monthly: one card charge a year instead of twelve, and $100 lands on the
 *  all-access ceiling PRICING_MODEL.md already sketched. */
export const TIERS = [100, 1000, 10000] as const
export type PaidTier = (typeof TIERS)[number]
export type Tier = 0 | PaidTier

/** How long a paid choice waits for Buy Me a Coffee to confirm before the
 *  app asks again. @unvalidated - long enough for somebody to open the
 *  email on a town day, short enough that a choice nobody completed does
 *  not silence the ask for most of a season. What would settle it: how long
 *  real completions take, which nobody has measured. */
export const PENDING_GRACE_DAYS = 30

/** `$1`, `$10`, `$100`. */
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
 *     `active`, not `pending` within `PENDING_GRACE_DAYS`, and not stopped
 *     or stop-requested this year (a hiker who just pressed Stop is not
 *     asked again until next year).
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
    if (server.status === 'active') return false
    if (server.status === 'pending' && server.chosen_at !== null) {
      const waited = (now.getTime() - new Date(server.chosen_at).getTime()) / 86_400_000
      if (waited < PENDING_GRACE_DAYS) return false
    }
    if (
      (server.status === 'stop_requested' || server.status === 'stopped') &&
      (sameYear(server.stop_requested_at, year) || sameYear(server.ended_at, year))
    ) {
      return false
    }
  }
  return true
}

// ---- The $0 nudge ----

/**
 * One screen of the nudge: a headline, a line under it, and the labels on
 * its three controls. Every label still names its amount, so a joke never
 * hides what a button does.
 */
export interface Nudge {
  title: string
  body: string
  one: string
  ten: string
  zero: string
}

/**
 * The lines the maintainer kept from eight candidates (poll, 2026-10-23:
 * 1, 4, 5, 7 and 8), plus two button labels of their own, "If you're forcing
 * me…" and "Less money, less problems", worked into the rotation.
 *
 * NONE OF THEM PUTS A NUMBER ON WHAT A HIKER COSTS. #393 measured a hiker
 * who never signs in at about $0 a year to serve, so "your dollar covers
 * your share" would be false, and a line built on it would be the
 * confidently wrong claim CLAUDE.md's first section exists to stop.
 */
export const NUDGES: readonly Nudge[] = [
  {
    title: 'Taking a zero? Respect.',
    body: "Every hiker needs one. But this map hasn't taken a day off all season. How about a nero instead: $1 a year.",
    one: 'Nero it: $1 a year',
    ten: 'Full send: $10 a year',
    zero: 'Keep it at $0',
  },
  {
    title: 'The hiker box giveth.',
    body: "You've been pulling from it all season. $1 a year puts something back for the next hiker who rolls in hungry.",
    one: 'Put in $1 a year',
    ten: 'Put in $10 a year',
    zero: 'Keep it at $0',
  },
  {
    title: 'Ramen-bomb budget?',
    body: "Totally fine; $0 is a real answer. But if there's a buck left after resupply, the next edition's on you.",
    one: "If you're forcing me… $1 a year",
    ten: '$10 a year',
    zero: 'Less money, less problems: keep it at $0',
  },
  {
    title: 'Hike your own hike. Pay your own way?',
    body: 'Even a dollar a year says "this map matters to me," and that\'s what keeps it free for the hiker behind you.',
    one: '$1 a year',
    ten: '$10 a year',
    zero: 'Keep it at $0',
  },
  {
    title: 'Hiker trash has standards.',
    body: 'Low ones, sure. But we always pack out what we pack in, and that includes a dollar for the map.',
    one: 'Pack out $1 a year',
    ten: 'Pack out $10 a year',
    zero: 'Less money, less problems: keep it at $0',
  },
]

/** A per-phone number, minted once, so two hikers in the same year see
 *  different lines. Not an identifier: it never leaves the phone. */
export const NUDGE_SEED_KEY = 'ourhike:support-nudge-seed'

function nudgeSeed(): number {
  try {
    const stored = localStorage.getItem(NUDGE_SEED_KEY)
    const parsed = stored === null ? NaN : Number.parseInt(stored, 10)
    if (Number.isInteger(parsed) && parsed >= 0) return parsed
    const minted = Math.floor(Math.random() * NUDGES.length)
    localStorage.setItem(NUDGE_SEED_KEY, String(minted))
    return minted
  } catch {
    return 0
  }
}

/** This year's line for this phone. The year steps it on by one, so a hiker
 *  who keeps answering $0 sees a different line each year. */
export function nudgeFor(now: Date, seed: number = nudgeSeed()): Nudge {
  const index =
    (((now.getFullYear() + seed) % NUDGES.length) + NUDGES.length) % NUDGES.length
  return NUDGES[index]
}
