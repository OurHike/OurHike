// Display derivations for the plan timeline (#756), kept out of the screen
// component so they can be asserted without a render.

/**
 * A stop's one-line name. A named place is its name; a dropped point is its
 * mile marker - "mi 470.8", the reference every guidebook and shuttle
 * driver shares, which is why a mile MARKER never converts to km however
 * the hiker reads distances (lib/units.ts's own rule, and positionLine.ts's
 * existing rendering of the same idea).
 *
 * Typed on the two fields it reads rather than on PlanStop, because the
 * route builder's draft stops are the same naming problem before a plan
 * exists - one rule, so a stop cannot be called two things on two screens.
 */
export function stopLabel(stop: { mile: number; name?: string }): string {
  if (stop.name !== undefined && stop.name !== '') return stop.name
  return `mi ${mileMarker(stop.mile)}`
}

/**
 * A mile on the A.T.'s own axis, as a MARKER rather than a distance (#986).
 *
 * NEVER CONVERTED, and that is the whole point of it existing. "Mile 470.8"
 * is a name for a place - ATC measures the trail in miles, the shelters are
 * listed by them, and a hiker says "I'm at 470" the way they would say a
 * street number. Running it through `formatDistance` gives a metric hiker
 * "757.7 km", which names nothing: there is no kilometre 757.7 on this trail,
 * and no other surface in the app would agree with it.
 *
 * `formatDistance` is for the other kind of mile - how far it is from here to
 * there - which is a real length and does convert. The two look identical in
 * a number and are not the same quantity; this function exists so a caller
 * has to choose between them on purpose.
 */
export function mileMarker(mile: number): string {
  return mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/** "TUE 12" from an ISO date, in UTC throughout so the label cannot shift a
 *  day as a phone crosses a timezone. */
export function dayDateLabel(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`)
  const weekday = date
    .toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' })
    .toUpperCase()
  return `${weekday} ${date.getUTCDate()}`
}

/**
 * "tue 12 may" from an ISO date - the day summary's own header (#966),
 * lowercase because that card speaks in the hiker's voice rather than the
 * timeline's gutter voice, and carrying the month because a summary can be
 * opened weeks later, when "TUE 12" no longer says which twelfth.
 *
 * UTC throughout, for dayDateLabel's reason: the label must not shift a day
 * as a phone crosses a timezone.
 */
export function dayLongDateLabel(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`)
  const weekday = date.toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' })
  const month = date.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' })
  return `${weekday} ${date.getUTCDate()} ${month}`.toLowerCase()
}

/**
 * ROW HEIGHT = WALKING HOURS - the terrain-row timeline's one physical
 * encoding (wireframe 1b, CHOSEN): a hard day is bigger on the screen, so a
 * section's shape can be felt by scrolling it.
 *
 * The proportionality is the load-bearing part; the two constants are
 * layout, sized to put the wireframe's ≈7-hour day near its drawn height on
 * a phone. The floor is the app's own minimum touch target - every row is
 * tappable, and a half-hour day must not become an untappable sliver.
 */
export const ROW_PX_PER_WALKING_HOUR = 10
export const ROW_CHROME_PX = 24
export const MIN_ROW_PX = 44

export function dayRowHeight(walkingMinutes: number): number {
  return Math.max(
    MIN_ROW_PX,
    Math.round((walkingMinutes / 60) * ROW_PX_PER_WALKING_HOUR) + ROW_CHROME_PX,
  )
}

/**
 * TRIP ROW HEIGHT = DAYS, the same physical encoding one zoom out (#790).
 *
 * A day row is as tall as its walking hours; a trip row is as tall as its
 * days. So a long summer reads long before a single number has been read,
 * and the hike zoom and the day zoom teach the same thing about size rather
 * than two different things.
 *
 * The constants are layout, like the day row's: sized so a fortnight sits
 * near a comfortable card height on a phone. Same touch-target floor, for
 * the same reason - every row is tappable, and a one-day trip must not be
 * an untappable sliver. And a CEILING, which the day row does not need: a
 * recorded stretch can carry a hundred boundaries (#789), and a row taller
 * than the screen is not an encoding, it is a scroll trap.
 */
export const TRIP_PX_PER_DAY = 4
export const TRIP_CHROME_PX = 34
export const MAX_TRIP_ROW_PX = 160

export function tripRowHeight(days: number): number {
  return Math.min(
    MAX_TRIP_ROW_PX,
    Math.max(MIN_ROW_PX, Math.round(days * TRIP_PX_PER_DAY) + TRIP_CHROME_PX),
  )
}

/**
 * A trip's dates as one line - "12–17 May 2026" - or null when it has none
 * (#805).
 *
 * The dates were always there: `buildPlan` writes one onto every day and
 * the timeline prints them in each row's gutter. Nothing that NAMES a trip
 * ever printed them, so a list of seven trips read as seven undated
 * stretches of trail. This is the one function all of those call, so a trip
 * cannot be dated two ways on two screens.
 *
 * UTC throughout, like `dayDateLabel`, so a range cannot shift a day as a
 * phone crosses a timezone.
 */
export function tripDateRange(dates: readonly (string | null)[]): string | null {
  const dated = dates.filter((date): date is string => date !== null).sort()
  if (dated.length === 0) return null

  const first = new Date(`${dated[0]}T00:00:00Z`)
  const last = new Date(`${dated[dated.length - 1]}T00:00:00Z`)
  const month = (date: Date) =>
    date.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' })

  if (first.getTime() === last.getTime()) {
    return `${first.getUTCDate()} ${month(first)} ${first.getUTCFullYear()}`
  }
  // Same month and year: name the month once. Different: name both, because
  // "28–3 Apr" is a date range nobody can read.
  if (
    first.getUTCFullYear() === last.getUTCFullYear() &&
    first.getUTCMonth() === last.getUTCMonth()
  ) {
    return `${first.getUTCDate()}–${last.getUTCDate()} ${month(last)} ${last.getUTCFullYear()}`
  }
  if (first.getUTCFullYear() === last.getUTCFullYear()) {
    return `${first.getUTCDate()} ${month(first)} – ${last.getUTCDate()} ${month(last)} ${last.getUTCFullYear()}`
  }
  return `${first.getUTCDate()} ${month(first)} ${first.getUTCFullYear()} – ${last.getUTCDate()} ${month(last)} ${last.getUTCFullYear()}`
}
