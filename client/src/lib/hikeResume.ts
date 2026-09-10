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
import { shiftDate, walkedDayCount, type HikePlan } from './plan'

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
  plans: readonly { days: readonly { date?: string; walked?: boolean }[] }[],
): { count: number; from: string } | null {
  // Every dated day not yet walked, whatever its date (#1373, frame 6d):
  // the count describes what "Move them to today" moves, and a hiker back
  // after a pause has days dated in the PAST still on the plan - which
  // were the ones this used to leave out, so the card told them there was
  // nothing to move on exactly the morning there was.
  const dates = plans
    .flatMap((plan) =>
      plan.days.filter((day) => day.walked !== true).map((day) => day.date),
    )
    .filter((date): date is string => date !== undefined)
    .sort()
  if (dates.length === 0) return null
  return { count: dates.length, from: dates[0] }
}

/**
 * Move a plan's dated days to start today (#1373, frame 6d; the handler
 * WelcomeBackCard's "Move them to today" promised since #1317 and never had
 * - `resumeHike` set the status and moved no date, the inventory's P30).
 *
 * The first day not yet walked that carries a date is the anchor: every
 * date from it onward slides by the same delta, so the rhythm of the plan
 * - its zeros, its pins' spacing - is kept and only the calendar moves.
 * Walked days are records and keep their dates. A plan with no dated day
 * ahead is returned as it is: there is nothing to move, which the card
 * already says.
 */
export function moveDatedDaysToToday(plan: HikePlan, today: string): HikePlan {
  return moveHikeDatedDaysToToday([plan], today)[0]
}

/**
 * The same move across a hike's trips at once (#1374 review): ONE anchor -
 * the earliest unwalked dated day in any of them - and one delta for every
 * dated unwalked day in every plan, so the spacing BETWEEN the trips is
 * kept along with the spacing inside each. Moved plan by plan, each trip
 * slid to start today on its own, and two sections dated a fortnight apart
 * landed on the same week - the card had counted them as one figure and
 * offered one move. Plans are returned in the order given, unchanged
 * objects where nothing moves.
 */
export function moveHikeDatedDaysToToday(
  plans: readonly HikePlan[],
  today: string,
): HikePlan[] {
  const anchor = plans
    .map((plan) => firstDatedAhead(plan))
    .filter((date): date is string => date !== undefined)
    .sort()[0]
  if (anchor === undefined) return [...plans]
  const delta = daysBetween(anchor, today)
  if (delta === null || delta === 0) return [...plans]
  return plans.map((plan) => {
    // Untouched, as the same object, where nothing ahead is dated.
    if (firstDatedAhead(plan) === undefined) return plan
    const first = walkedDayCount(plan)
    return {
      ...plan,
      days: plan.days.map((day, index) =>
        index < first || day.date === undefined
          ? day
          : { ...day, date: shiftDate(day.date, delta) },
      ),
    }
  })
}

/** The date of the first unwalked day that carries one, or undefined. */
function firstDatedAhead(plan: HikePlan): string | undefined {
  return plan.days.slice(walkedDayCount(plan)).find((day) => day.date !== undefined)?.date
}
