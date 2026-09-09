// The card you leave with someone (#1008, storyboard frame D6) - the text,
// composed here so it is testable and identical wherever it is sent from.
//
// PLAIN TEXT, BECAUSE THE READER DOES NOT HAVE OURHIKE. The whole point of
// leaving word is that somebody who was not on the walk can act on it days
// later, on whatever phone they have. A link would be a dead end offline and
// an app nobody installed; sentences survive a text message, an email, a
// note stuck to a fridge.
//
// THE APP'S LINES AND THE HIKER'S LINES ARE DIFFERENT KINDS OF CLAIM, and
// the composition keeps them apart the way the whole codebase does:
//
// - What the app knows - the route's trails in walk order, the walked-trail
//   miles - comes from ONE source, handed in as `PlanTextFigures`, and
//   carries that source's own hedge. The finished-hike card prefers the live
//   re-derivation and falls back to the stored cache with a sentence saying
//   so; a card that took the cache's number and dropped the sentence would
//   be the display outrunning its source on the one artifact somebody will
//   decide to worry from. So `fromCache` travels with the figures and the
//   text hedges in words.
// - What only the hiker knows - where they are starting from, what the car
//   looks like, and above all "if I'm not back by" - is typed by them and
//   printed verbatim. **The app never computes a return time.** A walking
//   estimate is moving time on a rule of thumb; turning it into "expect me
//   at 4:30" is an arrival clock, which lib/naismith.ts refuses and
//   HIKER_SAFETY.md's posture forbids. The person left holding this card
//   will decide when to worry based on that line, so it has to be a number
//   a human chose, knowing about lunch and the swim and the view.
//
//   THIS SURVIVED THE ELEVATION LANDING, AND ON PURPOSE. #1011 gave the
//   network its per-edge climb, so a walk that could print no ≈time at all
//   when this file was written can print one now - and the builder bar and
//   the finished card both do. This card still does not, and that is the
//   maintainer's decision, asked and answered 2026-08-25: the reach of the
//   estimate was never the reason. A duration on the artifact somebody
//   decides to worry from reads as an arrival promise however it is worded,
//   and better data does not change what the reader does with it. Do not
//   "finish" this by wiring `walkingMinutes` in; the test below pins it.
//
// GROUND WITH NO TRAIL UNDER IT IS NAMED, NEVER BRIDGED BY AN ARROW. A
// deliberate gap (#935) is the part of a day most likely to lose somebody
// and the part a searcher most needs to hear about, so the miles the app
// has evidence for and the miles it does not are two lines rather than one
// total.
//
// The route line keeps the same rule, which is what `PlanTextLegs` exists
// for: AN ARROW ONLY EVER JOINS TWO TRAILS THE APP KNOWS ARE CONTINUOUS.
// The live resolution groups its legs by segment, so the seam is known and
// printed as one; the stored cache flattens them (`DayHikeFigures.legs` has
// no seam in it), so a multi-stretch walk falling back to the cache says the
// names in walk order and says outright that it cannot place the gap among
// them. The earlier version of this file joined the flat list with arrows
// either way, which printed a bushwhack as a junction - and, where the same
// trail lay on both sides of it, collapsed the repeat and erased the gap
// from the line altogether.
//
// A FIELD LEFT EMPTY IS OMITTED, never filled with a placeholder: "Car:
// unknown" on a card handed to a worried friend reads as information and is
// noise. Absent means the hiker didn't say - the same rule the POI exports
// keep.

import type { DayHike } from './dayHikes'
import { localDay } from './passedToday'
import { dayLongDateLabel } from './planDisplay'
import { formatDistance, type UnitSystem } from './units'

/** What only the hiker can say. All optional; empty strings are omitted. */
export interface LeaveWordFields {
  /** Where they are starting from, in their own words - the app has no
   *  trailhead names to offer (#981). */
  startingFrom: string
  /** The car and where it is parked. */
  car: string
  /** The line the whole card exists for. Typed, never computed. */
  notBackBy: string
}

/**
 * The app's half of the card, from ONE source.
 *
 * `miles` and `legs` must come from the same derivation - the live
 * resolution or the stored cache, never one of each. A route line naming
 * the trails a republished graph no longer routes through, beside a mileage
 * from the route that replaced them, is two graphs' answers printed as one
 * walk.
 */
export interface PlanTextFigures {
  /** Walked-trail miles, excluding any gap between segments. */
  miles: number
  /** The trails in walk order, from the same derivation as `miles`, carrying
   *  whether this phone can place the gaps among them. */
  legs: PlanTextLegs
  /** True when both came from the stored cache rather than a live
   *  re-derivation, which the text then says in words. */
  fromCache: boolean
  /** Straight-line miles of deliberate gap between segments (#935), or 0. */
  gapMiles: number
  /** How many stretches the walk is in - 1 unless it has gaps. */
  stretches: number
}

/** The repo's date spelling with the year kept.
 *
 *  `dayLongDateLabel` drops the year, which is right on a screen a hiker is
 *  reading today and wrong on a card that outlives the walk: "sat 12 sep"
 *  from last year is indistinguishable from this year's, on the one artifact
 *  somebody might hand to a searcher. */
function cardDate(isoDate: string): string {
  return `${dayLongDateLabel(isoDate)} ${isoDate.slice(0, 4)}`
}

/** One trail as the card names it. */
interface PlanTextLeg {
  name: string | null
}

/**
 * The trails in walk order, and whether the app can say where the walk
 * leaves them.
 *
 * `placed` carries one array per stretch, so the seams between stretches are
 * exactly the gaps; `unplaced` is the flat list the stored cache keeps, which
 * has lost them. The distinction is a union rather than a nullable field
 * because the two cannot be told apart by inspection - a flat list of three
 * trails and a single stretch of three trails are the same array - and
 * printing one as the other is the failure this type exists to stop.
 */
export type PlanTextLegs =
  | { readonly kind: 'placed'; readonly byStretch: readonly (readonly PlanTextLeg[])[] }
  | { readonly kind: 'unplaced'; readonly flat: readonly PlanTextLeg[] }

/** A trail walked out and back appears twice in the legs; the reader wants
 *  the shape, not the bookkeeping, so consecutive repeats collapse. Applied
 *  WITHIN a stretch only: the same trail either side of a gap is a hiker
 *  leaving it and rejoining it, which is the one repeat that means
 *  something. */
function collapsed(legs: readonly PlanTextLeg[]): string[] {
  const walked: string[] = []
  for (const leg of legs) {
    const name = leg.name ?? 'an unnamed trail'
    if (walked[walked.length - 1] !== name) walked.push(name)
  }
  return walked
}

/**
 * The route as one line: the trails in walk order, with the loop said in
 * words and any gap named rather than bridged.
 */
export function routeLine(legs: PlanTextLegs, looped: boolean): string | null {
  if (legs.kind === 'unplaced') {
    const walked = collapsed(legs.flat)
    if (walked.length === 0) return null
    // Commas, never arrows: this list reached here from the cache, which
    // dropped the seams, so the app does not know which of these joins is a
    // junction and which is open ground. Reaching this branch at all means
    // the walk has more than one stretch - a single-stretch cache is handed
    // in as `placed`, because there its flat list IS the stretch.
    return `${walked.join(', ')} — in walk order, though this phone can’t place the off-trail stretch among them`
  }
  const stretches = legs.byStretch
    .map((stretch) => collapsed(stretch).join(' → '))
    .filter((stretch) => stretch !== '')
  if (stretches.length === 0) return null
  const line = stretches.join(' — off trail — ')
  return looped ? `${line} → back to the start` : line
}

/**
 * The whole card, ready for a text message.
 *
 * `today` is injectable so the "written" line can be tested against a fixed
 * day; it defaults to the phone's own local calendar date, which is the
 * clock this card is about - somebody's morning, not UTC's.
 */
export function dayHikePlanText(
  hike: DayHike,
  figures: PlanTextFigures,
  units: UnitSystem,
  fields: LeaveWordFields,
  today: string = localDay(new Date()),
): string {
  const lines: string[] = []

  // The header carries the day the walk is FOR and, when that is not the day
  // the card was written, both - so a card written the night before reads
  // honestly, and a stale plan date cannot pass for today's walk. The reader
  // is deciding when to worry; a date they cannot place is worse than none.
  if (hike.date === null) {
    lines.push(`${hike.name} · written ${cardDate(today)}`)
  } else if (hike.date === today) {
    lines.push(`${hike.name} · ${cardDate(hike.date)}`)
  } else {
    lines.push(
      `${hike.name} · planned for ${cardDate(hike.date)}, written ${cardDate(today)}`,
    )
  }

  if (fields.startingFrom.trim() !== '') {
    lines.push(`Starting from: ${fields.startingFrom.trim()}`)
  }

  const route = routeLine(figures.legs, hike.looped)
  if (route !== null) lines.push(`Route: ${route}`)

  // Trail miles only. No walking time: none exists for network trails (the
  // builder bar prints none for the same reason), and a time on this card
  // would be read as an arrival promise by exactly the person it must not
  // mislead.
  const hedge = figures.fromCache
    ? ' (measured when this was planned, not re-checked since)'
    : ''
  lines.push(`How far: ${formatDistance(figures.miles, units)} on marked trails${hedge}`)

  if (figures.gapMiles > 0) {
    // The miles above are the ones with evidence under them; these are the
    // ones without. Said separately because they are a different kind of
    // claim, and because this is the stretch a searcher most needs named.
    lines.push(
      figures.stretches > 2
        ? `Plus ${formatDistance(figures.gapMiles, units)} with no trail under it, between the ${figures.stretches} stretches of this walk — I'll be crossing that on my own.`
        : `Plus ${formatDistance(figures.gapMiles, units)} with no trail under it, between the two stretches of this walk — I'll be crossing that on my own.`,
    )
  }

  if (fields.car.trim() !== '') lines.push(`Car: ${fields.car.trim()}`)

  if (fields.notBackBy.trim() !== '') {
    lines.push(`If I'm not back by ${fields.notBackBy.trim()}, something's wrong.`)
  }

  lines.push('Written before leaving, with OurHike. It does not track me.')

  return lines.join('\n')
}
