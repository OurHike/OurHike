// What today is, on the long hike the app is in (#1317).
//
// One module rather than a derivation inside the Today screen, for the
// reason lib/todayText.ts exists: the Today card, the day screen and the
// Plan band all name the same day, and three answers to "which day is it"
// is how two of them come to disagree by one.
//
// DAY NUMBER COMES FROM THE CALENDAR, NEVER FROM A TAP. It is the count of
// days from the hike's first dated day to today, and that is the whole rule
// - a hiker who never opened the app yesterday still has day 7 today. The
// alternative, incrementing on some "finish the day" action, would make the
// number a record of app usage rather than of walking, and would drift the
// first time somebody left their phone off.
//
// NULL IS A REAL ANSWER, TWICE OVER. A hike with no dated day has no day
// number, and the eyebrow then says the date alone - which is true - rather
// than a "DAY 1" nothing supports. A hike with no plan covering today has no
// day card, and Today simply leads with the alerts as it always did. Neither
// is a degraded state: planning as you walk is the ordinary way to walk a
// long trail, and a screen that nagged about it would be inventing an
// obligation the model does not have.

import type { HikePlan } from './plan'
import { daysBetween } from './hikeText'
import type { Trip } from './trips'

/** One day of a hike, located: which trip holds it and where inside it. */
export interface HikeDayAt {
  trip: Trip
  /** Index into `trip.plan.days`, so `stops[index]` and `stops[index + 1]`
   *  are the day's two ends. */
  index: number
}

/** The day a dated plan puts on `today`, or null. */
export function dayOn(plan: HikePlan, today: string): number | null {
  const at = plan.days.findIndex((day) => day.date === today)
  return at === -1 ? null : at
}

/**
 * Today's day across a hike's sections, or null when nothing is planned for
 * it.
 *
 * The FIRST match wins, and a hiker with two sections dated over the same
 * day has a contradiction this module does not try to resolve - picking one
 * is at least stable, where merging them would print a day that is neither.
 */
export function hikeDayToday(
  trips: readonly Trip[],
  tripIds: readonly string[],
  today: string,
): HikeDayAt | null {
  for (const id of tripIds) {
    const trip = trips.find((candidate) => candidate.id === id)
    if (trip === undefined) continue
    const index = dayOn(trip.plan, today)
    if (index !== null) return { trip, index }
  }
  return null
}

/**
 * Which day of the whole hike today is, counting from its first dated day.
 *
 * One-based, because a hiker says "day one" about the day they started
 * rather than "day zero". Null when nothing in the hike is dated, or when
 * today is before it began - a negative day number would be arithmetic
 * printed as a fact.
 */
export function dayNumber(
  trips: readonly Trip[],
  tripIds: readonly string[],
  today: string,
): number | null {
  let first: string | null = null
  for (const id of tripIds) {
    const trip = trips.find((candidate) => candidate.id === id)
    if (trip === undefined) continue
    for (const day of trip.plan.days) {
      if (day.date === undefined) continue
      if (first === null || day.date < first) first = day.date
    }
  }
  if (first === null) return null
  const days = daysBetween(first, today)
  return days === null || days < 0 ? null : days + 1
}

/**
 * Whether this day ends at the hike's own last point - "the last of it".
 *
 * Compared against the hike's outermost miles rather than the final point in
 * the list, because a hike that turns around finishes in the middle of its
 * own extent and its last point is not its furthest one. Within a tenth of a
 * mile, which is the precision the miles are published and printed at:
 * requiring exactness would mean this never fired.
 */
export function endsTheHike(
  plan: HikePlan,
  dayIndex: number,
  lastPointMile: number,
): boolean {
  const end = plan.stops[dayIndex + 1]
  return end !== undefined && Math.abs(end.mile - lastPointMile) < 0.1
}
