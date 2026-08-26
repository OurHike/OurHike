// The Today screen's own lines (#1054): the date eyebrow, the split mile
// readout, and the greeting.
//
// A module rather than inline formatting for positionLine.ts's reason: each
// of these is a decision with cases, and the cases deserve tests that do not
// have to render a screen to run.

/** "TUE 26 AUG" - weekday, day, month, in the mono eyebrow's own order.
 *  Composed by hand because toLocaleDateString's short form is
 *  "Tue, Aug 26" and no options flag reorders it. */
export function formatTodayEyebrow(now: Date): string {
  const weekday = now.toLocaleDateString('en-US', { weekday: 'short' })
  const month = now.toLocaleDateString('en-US', { month: 'short' })
  return `${weekday} ${now.getDate()} ${month}`.toUpperCase()
}

export type PositionReadout =
  { kind: 'mile'; mile: string; unit: string } | { kind: 'sentence'; sentence: string }

/**
 * The one position line (lib/positionLine.ts), split for the big readout.
 *
 * PARSED FROM THE LINE RATHER THAN RECOMPUTED, deliberately: positionLine
 * holds a precedence with eight outcomes, and a second module taking the same
 * inputs is how the header and the Today readout would come to disagree about
 * where the hiker is. The mile form is pinned by positionLine's own tests
 * ("mi 1,407.2 · NOBO"), so this match is against a tested contract, not a
 * guess - and anything that does not match renders as the sentence it is.
 */
export function splitPosition(position: string): PositionReadout {
  const match = /^mi ([\d,]+\.\d)(?: · (NOBO|SOBO))?$/.exec(position)
  if (match === null) return { kind: 'sentence', sentence: position }
  return {
    kind: 'mile',
    mile: match[1],
    unit: match[2] === undefined ? 'mi' : `mi · ${match[2]}`,
  }
}

/** Warmer register than a bare figure, honest about the clock: morning until
 *  noon, afternoon until five, evening after. */
export function greetingLead(now: Date): string {
  const hour = now.getHours()
  if (hour >= 5 && hour < 12) return 'Good morning.'
  if (hour >= 12 && hour < 17) return 'Good afternoon.'
  return 'Good evening.'
}

export interface GreetingInputs {
  now: Date
  /** The next shelter ahead, when the journal could rank one - with its
   *  distance in miles. */
  destination?: { name: string; distanceMi: number }
  /**
   * The walking-time estimate for that distance ("≈3h 40m"), already
   * ≈-prefixed by lib/naismith.ts or lib/pace.ts - or undefined when the
   * ascent between here and there is not measurable, in which case the
   * greeting says the distance and stops. A DURATION, never an arrival
   * clock: WIREFRAMES.md's Naismith rule ("never shown as an arrival
   * clock") outranks the prototype's "you'll be there around 4:40", because
   * Naismith knows nothing about breaks and gives no descent credit, and an
   * arrival time is a promise the rule cannot keep - recorded as a
   * deliberate deviation on #1054.
   */
  estimate?: string
}

/**
 * One warm sentence, sized to what the data supports:
 * "Good morning. Bailey Gap Shelter is 8.4 miles ahead — ≈3h 40m of walking."
 * down to "Good morning." when nothing ahead is rankable.
 */
export function todayGreeting({ now, destination, estimate }: GreetingInputs): string {
  const lead = greetingLead(now)
  if (destination === undefined) return lead

  const miles = destination.distanceMi.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
  const distance = `${destination.name} is ${miles} ${miles === '1.0' ? 'mile' : 'miles'} ahead`
  return estimate === undefined
    ? `${lead} ${distance}.`
    : `${lead} ${distance} — ${estimate} of walking.`
}
