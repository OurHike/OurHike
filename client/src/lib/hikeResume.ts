// Coming back to a long hike (#1317).
//
// TWO TRIGGERS, BOTH REQUIRED, and they answer different questions. The
// EXPLICIT one is a hiker who paused and is resuming: they said they were
// stepping off, so the app can say "welcome back" without guessing. The
// NOTICED one is the hiker who did not say - who simply stopped opening the
// app on the trail for a fortnight, because that is what people do - and it
// is the one that makes the feature worth building.
//
// DOING NOTHING CHANGES NOTHING. That sentence is on the screen and it has to
// be true in code, which is why nothing here mutates: this module answers
// "should the offer be made", and every date the hiker might move is moved by
// a handler they pressed. A resume prompt that quietly rolled a plan forward
// would be the app editing somebody's record because they went quiet.
//
// OFFERED ONCE PER HIKE. The dismissal is per hike rather than global,
// because a hiker with two hikes has two different absences, and a global
// "seen it" would silence the second one for the first one's reason.

import { daysBetween } from './hikeText'
import type { Hike } from './hikes'

/**
 * How many days with no fix on a hike's corridor before the app offers to
 * pick it back up.
 *
 * @unvalidated 11 days is the design prototype's number and nothing has
 * measured it. The tension is real in both directions: too short and a
 * hiker who took a week in town is asked whether they are still walking,
 * which is the app second-guessing them; too long and somebody starting
 * again next April gets no help at all and re-enters their dates by hand.
 *
 * What would settle it: the distribution of gaps between consecutive days
 * with a corridor fix, across real long hikes, once there are any - and it
 * plausibly differs by hike type, since a thru-hiker's fortnight off is
 * unusual where a section hiker's eleven months is the ordinary shape of
 * their year. Until then this errs LONG, because a prompt that arrives too
 * early is a prompt that trains hikers to dismiss it.
 */
export const NOTICED_ABSENCE_DAYS = 11

/** Why the app is offering to pick a hike back up, or null for not offering. */
export type ResumeReason = 'paused' | 'noticed'

/**
 * Whether to offer this hike back, and why.
 *
 * `lastSeen` is the last day this hike's corridor had a fix - null for a
 * hike that has never had one, which is NOT an absence: a hike set up on a
 * laptop in February has no fixes and nobody has gone quiet.
 */
export function resumeOffer(
  hike: Hike,
  lastSeen: string | null,
  today: string,
  dismissed: readonly string[],
): ResumeReason | null {
  if (hike.status === 'finished') return null
  if (dismissed.includes(hike.id)) return null
  if (hike.status === 'paused') return 'paused'
  if (lastSeen === null) return null

  const away = daysBetween(lastSeen, today)
  return away !== null && away >= NOTICED_ABSENCE_DAYS ? 'noticed' : null
}

/** How many days a paused hike has been paused, or null. */
export function pausedDays(hike: Hike, today: string): number | null {
  if (hike.pausedOn === undefined) return null
  const days = daysBetween(hike.pausedOn, today)
  return days === null || days < 0 ? null : days
}

/**
 * The dated days still ahead of a hike's plans, and the date they start
 * from - what "eight days are still dated from 28 August" counts.
 *
 * Counted rather than moved. The offer to move them is a button.
 */
export function datedDaysAhead(
  plans: readonly { days: readonly { date?: string }[] }[],
  today: string,
): { count: number; from: string } | null {
  const dates = plans
    .flatMap((plan) => plan.days.map((day) => day.date))
    .filter((date): date is string => date !== undefined && date >= today)
    .sort()
  if (dates.length === 0) return null
  return { count: dates.length, from: dates[0] }
}
