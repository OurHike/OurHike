// The $0 nudge's lines, and which one this phone sees this year (#1876).
//
// Apart from lib/support.ts because only the deferred day-5 window reads
// them: the shell imports lib/support.ts for `shouldAsk` on every launch, and
// these strings would otherwise ride in the eager closure LAUNCH_BUDGET.md §3
// measures, for a screen most launches never show.

/**
 * One screen of the nudge: a headline, a line under it, and the labels on
 * its three controls. Every label still names its amount, so a joke never
 * hides what a button does.
 */
export interface Nudge {
  title: string
  body: string
  /** The lowest paid tier's button, $12 a year. */
  low: string
  /** The middle tier's, $60 a year. */
  mid: string
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
    body: "Every hiker needs one. But this map hasn't taken a day off all season. How about a nero instead: $12 a year.",
    low: 'Nero it: $12 a year',
    mid: 'Full send: $60 a year',
    zero: 'Keep it at $0',
  },
  {
    title: 'The hiker box giveth.',
    body: "You've been pulling from it all season. $12 a year puts something back for the next hiker who rolls in hungry.",
    low: 'Put in $12 a year',
    mid: 'Put in $60 a year',
    zero: 'Keep it at $0',
  },
  {
    title: 'Ramen-bomb budget?',
    body: "Totally fine; $0 is a real answer. But if there's a buck a month left after resupply, the next edition's on you.",
    low: "If you're forcing me… $12 a year",
    mid: '$60 a year',
    zero: 'Less money, less problems: keep it at $0',
  },
  {
    title: 'Hike your own hike. Pay your own way?',
    body: 'Even a dollar a month says "this map matters to me," and that\'s what keeps it free for the hiker behind you.',
    low: '$12 a year',
    mid: '$60 a year',
    zero: 'Keep it at $0',
  },
  {
    title: 'Hiker trash has standards.',
    body: 'Low ones, sure. But we always pack out what we pack in, and that includes a dollar a month for the map.',
    low: 'Pack out $12 a year',
    mid: 'Pack out $60 a year',
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
