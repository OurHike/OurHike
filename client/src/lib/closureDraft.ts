// Reporting a closure (#832): what a hiker files when they walk up to a
// stretch of trail that is shut, and the geometry that gets captured with it.
//
// `POST /closures` has existed since the initial schema and this app had
// never called it - `lib/api.ts` carried fetch, verify and dismiss and no
// create. Two things followed from that, and this module exists because of
// the second:
//
//  1. A hiker who walked up to a washout had no way to tell anybody. A
//     closure reached the map only through a maintainer with database access.
//  2. The four geometry columns #674 added were null on every closure that
//     exists, so `lib/closureProjection.ts` was a no-op on 100% of real rows.
//     The anchor problem was PREPARED for and not solved - solved only for
//     closures authored after a form exists.
//
// WHY THE POINTS ARE COMPUTED HERE AND NOT LATER
//
// A mile is a reading against one particular measurement of the centerline,
// and the ATC re-measures. Converting a mile to a point later would need the
// centerline of the release the closure was authored against, and
// pipeline/DATA_RELEASES.md prunes a release 90 days after it is superseded -
// so the conversion stops being possible long before the closure stops
// mattering. Capture-at-write is the whole design, and this is the write.

import type { ClosureReason } from './closureBanner'
import { trailPointAtMile, type TrailIndex } from './trailPosition'

/**
 * What a phone queues, and the body `POST /closures` accepts.
 *
 * Field names match the wire exactly - `FieldNoteDraft`'s convention - so
 * the outbox sends this object with only `id` and `reported_at` added from
 * the item carrying it.
 *
 * The four coordinates are optional and travel as a set of four or not at
 * all. See `closureGeometry`.
 */
export interface ClosureDraft {
  reason_type: ClosureReason
  note?: string
  start_mile_marker: number
  end_mile_marker: number
  start_lat?: number
  start_lon?: number
  end_lat?: number
  end_lon?: number
}

/** The four coordinates, together or not at all. */
export interface ClosureGeometry {
  start_lat: number
  start_lon: number
  end_lat: number
  end_lon: number
}

/**
 * Why a hiker says the trail is shut, in the words a sign at a trailhead
 * uses.
 *
 * The vocabulary is the backend's `ReasonType` and cannot be widened here -
 * these are the five values the column accepts. What is chosen here is how
 * they READ to somebody standing in front of the thing, which is not how
 * they read on a banner: `closureBanner.ts` renders `other` as "Closed",
 * because a hiker being warned about a stretch learns nothing from the word
 * "other". Somebody filing one is answering a different question, and
 * "Something else" is the honest option to offer them.
 *
 * `maintenance` and `relocation` are kept even though a hiker rarely knows
 * either from looking, because the ordinary way a hiker learns why a trail
 * is shut is by reading the club's own sign, which says so.
 */
export interface ClosureReasonOption {
  id: ClosureReason
  label: string
  hint: string
}

export const CLOSURE_REASONS: ClosureReasonOption[] = [
  {
    id: 'storm_damage',
    label: 'Storm damage',
    hint: 'Blowdowns, a slide, a washed-out bridge',
  },
  {
    id: 'flooding',
    label: 'Flooding',
    hint: 'Water over the trail or a ford nobody should take',
  },
  { id: 'maintenance', label: 'Trail work', hint: 'A crew has it shut while they work' },
  {
    id: 'relocation',
    label: 'Relocation',
    hint: 'The trail has moved and this stretch is retired',
  },
  { id: 'other', label: 'Something else', hint: 'Say what you saw in the note' },
]

/**
 * Where the two ends of a closure physically are, or nothing.
 *
 * **All four or none, which is the load-bearing rule and is not this
 * module's invention.** `projectClosure` refuses to re-read a closure whose
 * ends do not both project, because a stretch measured half against one
 * ruler and half against another has a length that is the difference between
 * two rulers rather than a distance. Sending half a closure's geometry would
 * manufacture exactly that row: it looks anchored, and is not.
 *
 * Null is the ordinary answer rather than a failure, and there are three
 * honest ways to get it - no trail index downloaded yet, a mile that falls in
 * the gap between two centerline pieces (`trailPointAtMile` returns null
 * rather than guessing), or a mile past either end of the published trail.
 * A closure with no geometry is exactly what every closure filed before this
 * form looks like, and the projection treats it the way it always has: show
 * the mile as stored.
 */
export function closureGeometry(
  index: TrailIndex | null,
  startMile: number,
  endMile: number,
): ClosureGeometry | null {
  if (index === null) return null

  const start = trailPointAtMile(index, startMile)
  const end = trailPointAtMile(index, endMile)
  if (start === null || end === null) return null

  // `trailPointAtMile` answers [lon, lat] - GeoJSON's order, which is the
  // reverse of the wire's field order here. Named rather than destructured
  // positionally, because a silent transposition would put every closure in
  // this app somewhere off the coast of Somalia and nothing downstream
  // could tell.
  const [startLon, startLat] = start
  const [endLon, endLat] = end

  return { start_lat: startLat, start_lon: startLon, end_lat: endLat, end_lon: endLon }
}

/**
 * The draft a form's answers make, geometry included where it could be
 * captured.
 *
 * Ordering is left alone deliberately: `ClosureCreate` normalises a reversed
 * pair server-side and swaps the geometry along with it (#257 meeting #674),
 * and doing it in two places is how the two come to disagree. What this must
 * not do is send a pair whose points and miles were ordered by different
 * rules, so it sends both exactly as authored.
 */
export function closureDraft(
  fields: {
    reason: ClosureReason
    startMile: number
    endMile: number
    note?: string
  },
  index: TrailIndex | null,
): ClosureDraft {
  const geometry = closureGeometry(index, fields.startMile, fields.endMile)

  return {
    reason_type: fields.reason,
    start_mile_marker: fields.startMile,
    end_mile_marker: fields.endMile,
    ...(fields.note !== undefined && fields.note.trim() !== ''
      ? { note: fields.note.trim() }
      : {}),
    ...(geometry ?? {}),
  }
}
