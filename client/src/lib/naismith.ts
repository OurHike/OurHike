// Naismith's Rule time estimate. See WIREFRAMES.md's Load-bearing values:
// 5 km/h base pace + 1 hour per 600m of ascent, rounded to 5-minute steps,
// always prefixed ≈, never shown as an arrival clock, no descent credit (a
// known weakness of the rule - don't silently "improve" it by adding one).
//
// Deliberately no `descentFt` parameter at all - not just "ignored if
// passed" but structurally absent, so a future call site can't accidentally
// wire descent in without touching this function's signature first.

const KM_PER_HOUR = 5
const MILES_TO_KM = 1.609344
const FEET_TO_METERS = 0.3048
const MINUTES_PER_HOUR_OF_ASCENT = 60 // 1h per 600m
const METERS_PER_ASCENT_HOUR = 600
const ROUND_TO_MINUTES = 5

export interface NaismithInput {
  distanceMi: number
  ascentFt: number
}

/**
 * Naismith's moving time in unrounded minutes.
 *
 * The number under `naismithTime`, exported for the places that must add or
 * compare estimates BEFORE display - a route's total across legs, a day
 * planner's cost function, a timeline row's height. Rounding each leg to 5
 * minutes and then summing would let the printed total drift from the printed
 * legs by up to 5 minutes a leg; arithmetic happens here, display rules
 * (the 5-minute step, the ≈) happen once, at the end, in naismithTime.
 *
 * pipeline/spike_day_planner.py carries a copy of this arithmetic for
 * measurement and names this file as the one that is right if they disagree.
 */
export function naismithMinutes({ distanceMi, ascentFt }: NaismithInput): number {
  const distanceKm = distanceMi * MILES_TO_KM
  const ascentM = ascentFt * FEET_TO_METERS

  const distanceMinutes = (distanceKm / KM_PER_HOUR) * 60
  const ascentMinutes = (ascentM / METERS_PER_ASCENT_HOUR) * MINUTES_PER_HOUR_OF_ASCENT

  return distanceMinutes + ascentMinutes
}

export function naismithTime(input: NaismithInput): string {
  return formatNaismithMinutes(naismithMinutes(input))
}

/**
 * The display rule for a moving-time estimate that has already been computed -
 * same 5-minute rounding, same ≈, same everything as naismithTime, for the
 * call sites that summed naismithMinutes across legs first.
 */
export function formatNaismithMinutes(totalMinutes: number): string {
  const rounded = Math.round(totalMinutes / ROUND_TO_MINUTES) * ROUND_TO_MINUTES

  const hours = Math.floor(rounded / 60)
  const minutes = rounded % 60

  if (hours === 0) return `≈${minutes}m`
  if (minutes === 0) return `≈${hours}h`
  return `≈${hours}h ${minutes}m`
}
