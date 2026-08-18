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
  return `mi ${stop.mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`
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
