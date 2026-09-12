// The last few nights of a long hike, for Today's "On-trail conditions ·
// last 3 days" (#1373, frame 2d).
//
// "The stops a hiker said they would make - three nights back on a long
// hike ... never everything they passed." A night is a stop on the plan
// that is a published place (it carries a `poiId`), read off the day the
// hiker is on: tonight is where today's day ends, last night is where it
// began, and the night before that is the previous day's start. Dropped
// points - a stop named only by its mile - are not places anybody can
// answer for, and are skipped rather than listed with nothing to tap.
//
// Labelled the way frame 2d labels them: "Tonight", "Last night", then the
// weekday of the night where the plan dates the day that ended at it, and
// "Two nights ago" where it does not - never a date the plan never held.
//
// Which day a night belongs to is the one thing here that can be off by a
// day, so it is written once: day k walks from `stops[k]` to `stops[k + 1]`
// and the hiker sleeps at `stops[k + 1]` on the night of `days[k].date`. So
// the night at `stops[k]` is the night of `days[k - 1]`, and at `stops[0]`
// it is the eve of `days[0]` - the night before the first day, which the
// plan dates only by implication.

import type { HikePlan, PlanStop } from './plan'

export interface NightBehind {
  label: string
  poiId: string
  name: string
  mile: number
}

export const NIGHTS_SHOWN = 3

/** "Tue" for an ISO day plus `offsetDays`, on the local calendar
 *  lib/passedToday.ts reads. */
function weekdayOf(isoDate: string, offsetDays: number): string | null {
  const parts = isoDate.split('-').map(Number)
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) return null
  const [year, month, day] = parts
  return new Date(year, month - 1, day + offsetDays).toLocaleDateString('en-US', {
    weekday: 'short',
  })
}

/** The weekday of the night spent at `plan.stops[stopIndex]`, per the rule
 *  in the header, or null where the plan does not date that day. */
function nightWeekday(plan: HikePlan, stopIndex: number): string | null {
  const day = stopIndex === 0 ? plan.days[0] : plan.days[stopIndex - 1]
  if (day?.date === undefined) return null
  return weekdayOf(day.date, stopIndex === 0 ? -1 : 0)
}

function asNight(stop: PlanStop | undefined, label: string): NightBehind | null {
  if (stop === undefined || stop.poiId === undefined) return null
  return {
    label,
    poiId: stop.poiId,
    name: stop.name ?? `mi ${stop.mile.toFixed(1)}`,
    mile: stop.mile,
  }
}

/**
 * The nights behind the day at `dayIndex`, tonight first, at most
 * `NIGHTS_SHOWN` and only the ones that are places.
 */
export function nightsBehind(plan: HikePlan, dayIndex: number): NightBehind[] {
  const candidates: Array<{ stop: PlanStop | undefined; label: string }> = [
    { stop: plan.stops[dayIndex + 1], label: 'Tonight' },
    { stop: plan.stops[dayIndex], label: 'Last night' },
  ]
  // NIGHTS_SHOWN is three and two are already named, so the night before
  // last is the only further one - the loop an earlier draft ran here could
  // only ever turn once.
  if (dayIndex >= 1) {
    const weekday = nightWeekday(plan, dayIndex - 1)
    candidates.push({
      stop: plan.stops[dayIndex - 1],
      label: weekday === null ? 'Two nights ago' : `${weekday} night`,
    })
  }
  const nights: NightBehind[] = []
  for (const { stop, label } of candidates) {
    const night = asNight(stop, label)
    if (night !== null) nights.push(night)
  }
  return nights
}
