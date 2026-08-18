// How far the hiker's own days actually reach (#791).
//
// NOT THE SAME INSTRUMENT AS NAISMITH, and the two must never be swapped
// for one another. `lib/naismith.ts` estimates MOVING TIME over a stretch of
// ground from its distance and climb - a comparative figure about the
// terrain, available on a fresh install because it needs nothing from the
// hiker. What is here is the opposite: the miles a hiker's OWN days have
// covered, read off their own log, unavailable until they have one. A day
// that covered 14 miles took as long as it took, including the two hours at
// the shelter; that is the point, because "which piece fits the five days I
// have" is a question about days, not about walking speed.
//
// features/PERSONALIZED_PACE.md governs the shape of the answer, and its
// rules are followed here rather than re-argued:
//
//   - "A model that pretends otherwise is worse than one that admits it,
//     which is why the output below is a range rather than a number." So
//     every figure here is a range, and the spread IS the information.
//   - On device, never synced. Nothing here leaves the phone - it is
//     derived from the trip store on read and stored nowhere.
//   - "Not a fitness tracker. No streaks, no personal bests, no 'you were
//     faster last Tuesday'." Nothing here compares two periods, and nothing
//     ranks a day against another day.
//
// What that document specifies and this deliberately does NOT implement:
// grade buckets, moving-time observations, stop detection, exponential
// recency decay. Those need a GPS observation store that does not exist
// yet. This reads what the planner already records - walked days and their
// miles - which is enough for the question #791 asks and honest about
// being less than the full model.

import { walkedSpans, type Span } from './hikes'
import type { Trip } from './trips'

/** A figure the hiker's own log supports, low to high. Never a single
 *  number: the spread is what the app cannot see - weather, mood, pack,
 *  sleep - reported rather than hidden. */
export interface Reach {
  lowMi: number
  highMi: number
  /** How many samples it rests on, so the screen can say "from your own 41
   *  days" rather than presenting a two-sample fit as a personal law. */
  samples: number
}

/**
 * How many walked days there must be before any of this is shown.
 *
 * @unvalidated 5 is picked, not measured. The requirement is #791's and it
 * is not a soft one - "withheld entirely until there is enough history…
 * instead of borrowing Naismith's estimate and calling it yours" - but
 * nobody has checked where the floor should sit. Below a handful of days a
 * quartile is really just "one of your days", and calling that a range
 * would be the display outrunning its source.
 *
 * What would settle it: the spread of the middle-half estimate against the
 * full-log estimate as a real log grows, across a few real logs. Until
 * then this errs toward showing nothing, which is the direction that
 * cannot mislead somebody into biting off five days of trail on the
 * evidence of one.
 */
export const MIN_REACH_DAYS = 5

/** And how many finished trips before "trips your size" means anything.
 *  @unvalidated for the same reason and settled by the same measurement. */
export const MIN_REACH_TRIPS = 3

/**
 * The middle half of a set of samples - the 25th and 75th percentiles, by
 * linear interpolation.
 *
 * The middle half rather than the full min-to-max, because one exceptional
 * day (a 4-mile afternoon start, a 26-mile push) would otherwise widen the
 * range until it said nothing. Robust to exactly the outliers a hiking log
 * is full of, and it needs no assumption about the shape of the
 * distribution - which is good, because nobody knows what shape a hiker's
 * day lengths have.
 */
export function middleHalf(samples: readonly number[]): { low: number; high: number } {
  const sorted = [...samples].sort((a, b) => a - b)
  return { low: percentile(sorted, 0.25), high: percentile(sorted, 0.75) }
}

function percentile(sorted: readonly number[], fraction: number): number {
  if (sorted.length === 0) return 0
  const position = fraction * (sorted.length - 1)
  const below = Math.floor(position)
  const above = Math.ceil(position)
  if (below === above) return sorted[below]
  return sorted[below] + (sorted[above] - sorted[below]) * (position - below)
}

/**
 * The miles a day of this hiker's walking has covered, as a range.
 *
 * RECORDED STRETCHES ARE EXCLUDED (#789). A remembered "Springer to
 * Damascus" is one walked "day" of 470 miles as far as the plan model is
 * concerned, because its boundaries are what somebody could recall years
 * later rather than days anybody walked as days. Feeding that in would
 * teach the app that this hiker covers 470 miles a day, which is the
 * clearest possible case of a display outrunning its source.
 *
 * Null until there is enough history - deliberately, and see MIN_REACH_DAYS.
 */
export function dayReach(trips: readonly Trip[]): Reach | null {
  const samples = walkedDayMiles(trips)
  if (samples.length < MIN_REACH_DAYS) return null
  const { low, high } = middleHalf(samples)
  return { lowMi: low, highMi: high, samples: samples.length }
}

/**
 * The miles one of this hiker's trips has covered, as a range - what "≈ 3-4
 * trips the size you have been walking" is counted in.
 *
 * Recorded stretches are excluded here too, for a different reason: a
 * remembered stretch says what ground was covered but not in how many
 * outings. Ten years of section hikes entered as one "Springer → Damascus"
 * would read as a single 470-mile trip and put every gap at "≈ 1 trip your
 * size", which is worse than saying nothing.
 */
export function tripReach(trips: readonly Trip[]): Reach | null {
  const samples = walkedTripMiles(trips)
  if (samples.length < MIN_REACH_TRIPS) return null
  const { low, high } = middleHalf(samples)
  return { lowMi: low, highMi: high, samples: samples.length }
}

/** The samples themselves, exported so a screen saying "only 3 days walked
 *  so far" counts exactly what the refusal counted. Two answers to that
 *  question would be one too many. */
export function walkedDayMiles(trips: readonly Trip[]): number[] {
  return trips
    .filter((trip) => trip.recorded !== true)
    .flatMap((trip) => walkedSpans(trip.plan).map(spanMiles))
}

export function walkedTripMiles(trips: readonly Trip[]): number[] {
  return trips
    .filter((trip) => trip.recorded !== true)
    .map((trip) => walkedSpans(trip.plan).reduce((sum, span) => sum + spanMiles(span), 0))
    .filter((miles) => miles > 0)
}

function spanMiles(span: Span): number {
  return span.to - span.from
}

/**
 * How much trail `days` days of this hiker's own walking reach, as a range.
 *
 * The arithmetic is deliberately the simplest thing that could work - the
 * day range times the number of days - and it carries one assumption that
 * has to be said out loud wherever it is printed: **these are walking
 * days**. Zeros are not in the samples (`walkedSpans` drops them), so five
 * days here means five days of walking, not five days away from home with a
 * rest in the middle.
 */
export function reachOver(reach: Reach, days: number): { lowMi: number; highMi: number } {
  return { lowMi: reach.lowMi * days, highMi: reach.highMi * days }
}
