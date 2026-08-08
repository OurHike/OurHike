// Where the closures on screen came from, and how old they are.
//
// This replaces `ClosureSummary[] | null`, which could not tell a hiker the
// difference between "nothing is closed on this stretch" and "we could not
// ask" - both rendered as no warnings at all. That ambiguity is #249, applied
// to the read App.tsx calls "the half a hiker walks into", and removing it is
// the point of features/CONDITIONS_DELIVERY.md's step 2.
//
// Three states, because there are three genuinely different things to say:
//
//   live         asked the backend just now              closures, no caveat
//   baseline     the published artifact, up to a day old closures, "as of X"
//   unavailable  neither could be reached                say so, explicitly
//
// The order matters and is enforced here rather than by whichever fetch
// happens to land last: **live always wins, and a baseline never displaces
// it.** Both reads are fired independently, so a slow baseline resolving after
// a fast live one is ordinary rather than exceptional - and letting it
// overwrite would replace fresh closures with day-old ones and label the
// result stale, which is worse than either input.

import type { ClosureSummary } from './api'
import type { PublishedClosures } from './publishedConditions'

export type ClosureState =
  | { kind: 'live'; closures: ClosureSummary[] }
  | { kind: 'baseline'; closures: ClosureSummary[]; generatedAt: Date }
  | { kind: 'unavailable' }

export const NO_CLOSURES: ClosureState = { kind: 'unavailable' }

/** A live read landed. Always wins - it is the freshest thing available. */
export function withLive(closures: ClosureSummary[]): ClosureState {
  return { kind: 'live', closures }
}

/**
 * The published baseline landed.
 *
 * Returns `current` untouched when live data is already held, which is the
 * whole reason this is a function rather than a `setState` call at the call
 * site: the two reads race, and the loser must not win by arriving second.
 */
export function withBaseline(
  current: ClosureState,
  published: PublishedClosures,
): ClosureState {
  if (current.kind === 'live') return current
  return {
    kind: 'baseline',
    closures: published.closures,
    generatedAt: published.generatedAt,
  }
}

/**
 * The closures to draw, or `null` when there are none to draw.
 *
 * `null` still means "do not render closure warnings", exactly as before, so
 * every existing consumer - the banner, the map bands - keeps working
 * unchanged. What changed is that `null` no longer has to carry the *reason*
 * as well; `ClosureState` does that now.
 */
export function closuresOf(state: ClosureState): ClosureSummary[] | null {
  return state.kind === 'unavailable' ? null : state.closures
}

const MINUTE_MS = 60 * 1000
const HOUR_MS = 60 * MINUTE_MS
const DAY_MS = 24 * HOUR_MS

/**
 * What to show a hiker about the age of what they are looking at, or `null`
 * when there is nothing worth saying.
 *
 * `null` for the live case on purpose. A caveat on data that has none is noise
 * that teaches people to ignore caveats, which costs more than it buys the one
 * time the caveat matters.
 *
 * The unavailable case is a sentence rather than a duration because there is
 * no duration to report - and because saying nothing is what the old
 * behaviour did, which is precisely the bug.
 */
export function closureAgeLabel(state: ClosureState, now: Date): string | null {
  if (state.kind === 'live') return null
  if (state.kind === 'unavailable') return 'Trail conditions unavailable'

  const elapsed = now.getTime() - state.generatedAt.getTime()

  // A negative elapsed means the artifact is stamped in the future - clock
  // skew, near-certainly. Reported as the freshest thing it could honestly be
  // rather than as "in 3 hours", which reads as a bug and undermines the
  // banner it appears in.
  if (elapsed < HOUR_MS) return 'Conditions as of less than an hour ago'
  if (elapsed < DAY_MS) return `Conditions as of ${Math.floor(elapsed / HOUR_MS)}h ago`
  return `Conditions as of ${Math.floor(elapsed / DAY_MS)}d ago`
}
