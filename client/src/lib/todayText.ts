// The Today screen's date line (#1054).
//
// Its own module rather than an inline format call, because the eyebrow is a
// composed shape ("TUE 26 AUG", later "DAY 41 · TUE 26 AUG" once a hike's
// start date is known) and the composition should be testable without
// rendering the screen.

/** "TUE 26 AUG" - weekday, day, month, in the mono eyebrow's own order.
 *  Composed by hand because toLocaleDateString's short form is
 *  "Tue, Aug 26" and no options flag reorders it. */
export function formatTodayEyebrow(now: Date): string {
  const weekday = now.toLocaleDateString('en-US', { weekday: 'short' })
  const month = now.toLocaleDateString('en-US', { month: 'short' })
  return `${weekday} ${now.getDate()} ${month}`.toUpperCase()
}
