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
// weekday of the night where the plan carries a date for that day, and "Two
// nights ago" where it does not - never a date the plan never held.

import type { HikePlan, PlanStop } from './plan'

export interface NightBehind {
  label: string
  poiId: string
  name: string
  mile: number
}

export const NIGHTS_SHOWN = 3

/** "Tue" for an ISO day, on the local calendar lib/passedToday.ts reads. */
function weekdayOf(isoDate: string): string | null {
  const parts = isoDate.split('-').map(Number)
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) return null
  const [year, month, day] = parts
  return new Date(year, month - 1, day).toLocaleDateString('en-US', { weekday: 'short' })
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
  const nights: NightBehind[] = []
  const candidates: Array<{ stop: PlanStop | undefined; label: string }> = [
    { stop: plan.stops[dayIndex + 1], label: 'Tonight' },
    { stop: plan.stops[dayIndex], label: 'Last night' },
  ]
  for (
    let back = 1;
    candidates.length < NIGHTS_SHOWN && dayIndex - back >= 0;
    back += 1
  ) {
    const day = plan.days[dayIndex - back]
    const weekday = day?.date === undefined ? null : weekdayOf(day.date)
    candidates.push({
      stop: plan.stops[dayIndex - back],
      label:
        weekday === null
          ? back === 1
            ? 'Two nights ago'
            : `${back + 1} nights ago`
          : `${weekday} night`,
    })
  }
  for (const { stop, label } of candidates) {
    const night = asNight(stop, label)
    if (night !== null) nights.push(night)
  }
  return nights.slice(0, NIGHTS_SHOWN)
}
