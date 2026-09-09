// The Today screen's own lines (#1054): the date eyebrow, the split mile
// readout, and the greeting.
//
// A module rather than inline formatting for positionLine.ts's reason: each
// of these is a decision with cases, and the cases deserve tests that do not
// have to render a screen to run.

/**
 * The eyebrow's two formatters, built once each (#1324).
 *
 * `toLocaleDateString` constructs a fresh `Intl.DateTimeFormat` per call, and
 * this function made two of them on every render of Today - which during a
 * launch is many, none of them about the date. MEASURED 2026-09-09 on a cold
 * first run of client/scripts/measure-first-run.mjs: 100 ms of sampled self
 * time in this module. The same defect #1304 took out of lib/passedToday.ts
 * and #1324 out of chrome/StatusStrip.tsx; this is the third and last of the
 * three the launch profile named.
 *
 * Lazily rather than at module load, for the reason StatusStrip's carries:
 * this module is reachable from the eager closure that
 * scripts/check-build-output.mjs bounds, and an `Intl` built at import time
 * would be work in front of the first paint.
 *
 * `passedToday` went the other way and dropped `Intl` entirely - it composes
 * a storage key, where a hand-rolled answer is exactly as good. These two are
 * a weekday and a month a hiker reads, so they stay with the library that
 * knows how to spell them.
 */
let weekdayFormat: Intl.DateTimeFormat | null = null
let monthFormat: Intl.DateTimeFormat | null = null

/**
 * ...and the answer held for the day, which is worth doing on its own terms.
 *
 * WHAT IS MEASURED, AND WHAT WAS WRONGLY INFERRED FROM IT (#1334). Hoisting
 * the two constructions took the sampled self time from 100 ms to 84 ms and
 * no further (MEASURED 2026-09-09, three cold runs of
 * scripts/measure-first-run.mjs). #1328 read that as "the bill is the format
 * calls, so Today must re-render a great many times" and said so here. Then
 * somebody counted, with a counter on this component's render function,
 * production's public build values, 390x844:
 *
 *   Today, returning launch      14 renders, all inside the first 2 s
 *   Today, first run              0
 *   the shell, returning         14
 *   the shell, first run         11 by 2 s, 12 by 15 s
 *
 * Fourteen renders on a launch where about that many async facts land is
 * unremarkable, and 28 `format` calls cannot be 84 ms. So the inference did
 * not follow and the "separate finding" it handed the next reader was a
 * phantom. @unvalidated: what the residual 84 ms actually is remains unknown.
 * The likeliest explanation is that a SAMPLED profile attributes to the
 * nearest function boundary, so `splitPosition`, `todayGreeting` and
 * `greetingLead` in this same module may be landing on this line - but
 * nobody has checked that either, and it is written here as a hypothesis
 * rather than a cause. What would settle it is an instrumented count of each
 * function rather than a sampler's attribution.
 *
 * The memo stands regardless: computing this once a day instead of once a
 * render is right whatever the profile says, and it costs three getters. Only
 * the story about why was wrong.
 *
 * One entry, because there is only ever one date being asked about. Keyed on
 * the local calendar day rather than on the `Date` instance: lib/useClock.ts
 * hands out a new instance every minute and the eyebrow changes at midnight,
 * so an instance key would miss 1,439 of the 1,440 chances a day to be a hit.
 * Built from the three getters rather than through `Intl` for the reason
 * lib/passedToday.ts's `localDay` gives - a key is not prose, and formatting
 * one here would be paying the cost this exists to avoid.
 */
let eyebrowDay: string | null = null
let eyebrowText = ''

/** "TUE 26 AUG" - weekday, day, month, in the mono eyebrow's own order.
 *  Composed by hand because toLocaleDateString's short form is
 *  "Tue, Aug 26" and no options flag reorders it. */
export function formatTodayEyebrow(now: Date): string {
  const day = `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`
  if (day === eyebrowDay) return eyebrowText

  weekdayFormat ??= new Intl.DateTimeFormat('en-US', { weekday: 'short' })
  monthFormat ??= new Intl.DateTimeFormat('en-US', { month: 'short' })
  eyebrowText =
    `${weekdayFormat.format(now)} ${now.getDate()} ${monthFormat.format(now)}`.toUpperCase()
  eyebrowDay = day
  return eyebrowText
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
