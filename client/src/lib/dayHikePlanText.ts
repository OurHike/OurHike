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
//   miles - comes from the saved hike's own figures and prints with the
//   same words every other surface uses.
// - What only the hiker knows - where they are starting from, what the car
//   looks like, and above all "if I'm not back by" - is typed by them and
//   printed verbatim. **The app never computes a return time.** A walking
//   estimate is moving time on a rule of thumb; turning it into "expect me
//   at 4:30" is an arrival clock, which lib/naismith.ts refuses and
//   HIKER_SAFETY.md's posture forbids. The person left holding this card
//   will decide when to worry based on that line, so it has to be a number
//   a human chose, knowing about lunch and the swim and the view.
//
// A FIELD LEFT EMPTY IS OMITTED, never filled with a placeholder: "Car:
// unknown" on a card handed to a worried friend reads as information and is
// noise. Absent means the hiker didn't say - the same rule the POI exports
// keep.

import type { DayHike } from './dayHikes'
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
 * The route as one line: the trails in walk order, joined by arrows, with
 * the loop said in words. Legs are the saved figures' own list - the same
 * names the card prints - so the text and the screen cannot disagree.
 */
export function routeLine(hike: DayHike): string | null {
  const names = hike.figures.legs.map((leg) => leg.name ?? 'an unnamed trail')
  if (names.length === 0) return null
  // A trail walked out and back appears twice in the legs; the reader wants
  // the shape, not the bookkeeping, so consecutive repeats collapse.
  const walked: string[] = []
  for (const name of names) {
    if (walked[walked.length - 1] !== name) walked.push(name)
  }
  const line = walked.join(' → ')
  return hike.looped ? `${line} → back to the start` : line
}

/**
 * The whole card, ready for a text message.
 *
 * `miles` is passed in rather than read off the hike so the caller can hand
 * the live resolution when it has one and the stored cache when it does not
 * - the same preference the finished-hike card applies, for the same
 * reason.
 */
export function dayHikePlanText(
  hike: DayHike,
  miles: number,
  units: UnitSystem,
  fields: LeaveWordFields,
): string {
  const lines: string[] = []

  // dayLongDateLabel is the day summary's lowercase spelling - the hiker's
  // own voice, which is the register this whole card is written in.
  lines.push(
    hike.date === null ? hike.name : `${hike.name} · ${dayLongDateLabel(hike.date)}`,
  )

  if (fields.startingFrom.trim() !== '') {
    lines.push(`Starting from: ${fields.startingFrom.trim()}`)
  }

  const route = routeLine(hike)
  if (route !== null) lines.push(`Route: ${route}`)

  // Trail miles only. No walking time: none exists for network trails (the
  // builder bar prints none for the same reason), and a time on this card
  // would be read as an arrival promise by exactly the person it must not
  // mislead.
  lines.push(`How far: ${formatDistance(miles, units)} on marked trails`)

  if (fields.car.trim() !== '') lines.push(`Car: ${fields.car.trim()}`)

  if (fields.notBackBy.trim() !== '') {
    lines.push(`If I'm not back by ${fields.notBackBy.trim()}, something's wrong.`)
  }

  lines.push('Written before leaving, with OurHike. It does not track me.')

  return lines.join('\n')
}
