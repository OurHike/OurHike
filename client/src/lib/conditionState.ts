// Where the conditions on screen came from, and how old they are.
//
// This replaces `T[] | null`, which could not tell a hiker the difference
// between "nothing is reported on this stretch" and "we could not ask" - both
// rendered as no warnings at all. That ambiguity is #249, applied to the reads
// App.tsx calls "the half a hiker walks into", and removing it is the point of
// features/CONDITIONS_DELIVERY.md's steps 2 and 3.
//
// Generic over the payload because closures and reports have exactly the same
// delivery story - a live endpoint that needs the backend up, a published
// baseline that needs only the bucket, and an honest word for having neither
// (#436). One state machine, two instantiations, so the overlay rule below
// cannot drift between them.
//
// Three states, because there are three genuinely different things to say:
//
//   live         asked the backend just now              items, no caveat
//   baseline     the published artifact, up to a day old items, "as of X"
//   unavailable  neither could be reached                say so, explicitly
//
// The order matters and is enforced here rather than by whichever fetch
// happens to land last: **live always wins, and a baseline never displaces
// it.** Both reads are fired independently, so a slow baseline resolving after
// a fast live one is ordinary rather than exceptional - and letting it
// overwrite would replace fresh data with day-old data and label the result
// stale, which is worse than either input.

export type ConditionState<T> =
  | { kind: 'live'; items: T[] }
  | { kind: 'baseline'; items: T[]; generatedAt: Date }
  | { kind: 'unavailable' }

/** The starting state, and the honest one whenever neither read has landed.
 *  Typed `never` so the one constant serves every payload. */
export const UNAVAILABLE: ConditionState<never> = { kind: 'unavailable' }

/** A live read landed. Always wins - it is the freshest thing available. */
export function withLive<T>(items: T[]): ConditionState<T> {
  return { kind: 'live', items }
}

/**
 * The published baseline landed.
 *
 * Returns `current` untouched when live data is already held, which is the
 * whole reason this is a function rather than a `setState` call at the call
 * site: the two reads race, and the loser must not win by arriving second.
 */
export function withBaseline<T>(
  current: ConditionState<T>,
  items: T[],
  generatedAt: Date,
): ConditionState<T> {
  if (current.kind === 'live') return current
  return { kind: 'baseline', items, generatedAt }
}

/**
 * The items to draw, or `null` when there are none to draw.
 *
 * `null` still means "do not render", exactly as before, so every existing
 * consumer - the banner, the map bands, the warning pins - keeps working
 * unchanged. What changed is that `null` no longer has to carry the *reason*
 * as well; `ConditionState` does that now.
 */
export function itemsOf<T>(state: ConditionState<T>): T[] | null {
  return state.kind === 'unavailable' ? null : state.items
}

/**
 * The state whose caveat the one status line has to carry, out of several.
 *
 * Closures and reports each hold their own state, but the strip has one line
 * for "how current is the safety picture", and that line is only as good as
 * the weakest source: a live closures read next to unreachable reports is a
 * map silently missing its warning pins, and no caveat at all would claim a
 * completeness the screen does not have. So the worst state wins -
 * unavailable over baseline over live - and between two baselines, the older
 * one, since the staleness being confessed is the staleness of the whole
 * picture.
 *
 * In practice the sources almost always agree: both live reads target the
 * same backend and both baselines come from the same bake, so a mixed state
 * is one dropped request, transient and rare. Being conservative for that
 * moment costs a caveat; being generous would cost the claim the caveat
 * exists to keep honest.
 */
export function worstOf(
  first: ConditionState<unknown>,
  ...rest: ConditionState<unknown>[]
): ConditionState<unknown> {
  let worst = first
  for (const state of rest) {
    if (state.kind === 'unavailable') {
      worst = state
    } else if (state.kind === 'baseline' && worst.kind !== 'unavailable') {
      if (worst.kind !== 'baseline' || state.generatedAt < worst.generatedAt) {
        worst = state
      }
    }
  }
  return worst
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
export function conditionsAgeLabel(
  state: ConditionState<unknown>,
  now: Date,
): string | null {
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
