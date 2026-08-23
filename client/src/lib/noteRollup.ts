// What the map shows without reading the feed (features/FIELD_NOTES.md §3).
//
// A feed alone fails the test that matters: eight percent battery, one
// glance, is there water in the next four miles. So three things are
// computed FROM the notes at render time - never stored, the same
// derive-don't-duplicate instinct DATA_NUDGES.md applies to staleness:
//
//   last confirmed   the most recent observation - staleness.ts's input,
//                    which is the producer #256 said did not exist
//   a headline       "Dry — 3 days ago, thru-hiker". One line. No
//                    synthesis, no averaging, no model.
//   contested        recent notes disagree -> show BOTH, labelled. Do not
//                    average, do not pick a winner: a hiker who knows two
//                    people disagree about a spring carries water; a hiker
//                    shown a confident wrong answer does not (value #4).

import type { NoteSummary } from './fieldNotes'
import { observationLabel } from './fieldNotes'

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * How recent two disagreeing observations must both be to count as a live
 * disagreement rather than a change. "Dry in June, flowing in August" is a
 * spring that recovered; "dry Tuesday, flowing Thursday" is two people a
 * hiker should hear both of.
 *
 * @unvalidated - 14 days, borrowed from the FRESH boundary because both are
 * claims about how long an observation keeps describing the ground, and a
 * second unexplained constant would be worse than a borrowed one. The same
 * field-note volume that would settle staleness.ts's thresholds settles
 * this one.
 */
export const CONTESTED_WINDOW_DAYS = 14

export interface NoteHeadline {
  /** "Dry — 3 days ago, thru-hiker" */
  text: string
  observation: string | null
}

export interface NoteRollup {
  /** The most recent `observed_at` among the notes given - visible notes
   *  only, which is the caller's contract; hidden ones never reach a
   *  phone. Null when there are no notes, which staleness.ts reads as its
   *  `never` tier. */
  lastConfirmedAt: Date | null
  headline: NoteHeadline | null
  /** Both sides of a live disagreement, most recent first - or null when
   *  the recent notes agree (or there is at most one). */
  contested: [NoteHeadline, NoteHeadline] | null
}

function age(observedAt: Date, now: Date): string {
  const days = Math.floor((now.getTime() - observedAt.getTime()) / DAY_MS)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  return `${days} days ago`
}

const REPORTER_WORDS: Record<NoteSummary['reporter_type'], string> = {
  thru: 'thru-hiker',
  section: 'section hiker',
  day: 'day hiker',
  maintainer: 'maintainer',
}

/**
 * When one note was made and by whom, for the card's list of them (#941).
 *
 * The same two facts `headlineOf` puts after the em dash, through the same
 * `age` and the same `REPORTER_WORDS` - which is the whole reason it lives
 * here rather than in the component that prints it. A card listing
 * "6 days ago" over a roll-up saying "5 days ago" about the same note is the
 * quiet contradiction OurHikeValues.md #4 is about, and two copies of this
 * arithmetic is how that happens.
 *
 * A middot rather than the headline's comma: this rides beside a tag rather
 * than after a sentence, and the card sets middots between facts of one kind
 * everywhere else it does this.
 */
export function noteAttribution(note: NoteSummary, now: Date): string {
  return `${age(new Date(note.observed_at), now)} · ${REPORTER_WORDS[note.reporter_type]}`
}

function headlineOf(note: NoteSummary, now: Date): NoteHeadline {
  const observed = new Date(note.observed_at)
  const what = note.observation !== null ? observationLabel(note.observation) : 'Noted'
  return {
    text: `${what} — ${age(observed, now)}, ${REPORTER_WORDS[note.reporter_type]}`,
    observation: note.observation,
  }
}

/**
 * The roll-up over one place's visible notes. Order-insensitive: callers
 * hand over whatever the wire or the bake gave them, and recency is decided
 * here from `observed_at` rather than trusted from array position.
 */
export function rollUpNotes(notes: readonly NoteSummary[], now: Date): NoteRollup {
  if (notes.length === 0)
    return { lastConfirmedAt: null, headline: null, contested: null }

  const byRecency = [...notes].sort(
    (a, b) => new Date(b.observed_at).getTime() - new Date(a.observed_at).getTime(),
  )
  const newest = byRecency[0]
  const lastConfirmedAt = new Date(newest.observed_at)

  // A live disagreement is two TAGGED notes, both inside the window, that
  // say different things. Text-only notes cannot disagree mechanically -
  // nothing here reads prose - so they never mark a place contested.
  const cutoff = now.getTime() - CONTESTED_WINDOW_DAYS * DAY_MS
  const recentTagged = byRecency.filter(
    (note) => note.observation !== null && new Date(note.observed_at).getTime() >= cutoff,
  )
  const disagreeing = recentTagged.find(
    (note) => note.observation !== recentTagged[0]?.observation,
  )

  return {
    lastConfirmedAt,
    headline: headlineOf(newest, now),
    contested:
      disagreeing === undefined
        ? null
        : [headlineOf(recentTagged[0], now), headlineOf(disagreeing, now)],
  }
}

/**
 * Group a mixed fetch by place, for the map's consumers - the pin treatment
 * and the lanes ask "this POI's tier", and answering per call would sort the
 * whole list once per waypoint.
 *
 * Notes with no `poi_id` are dropped here rather than grouped under a
 * sentinel: they anchor to coordinates, not to a pin, and no pin should wear
 * their freshness.
 */
export function rollupByPoi(
  notes: readonly NoteSummary[],
  now: Date,
): Map<string, NoteRollup> {
  const byPoi = new Map<string, NoteSummary[]>()
  for (const note of notes) {
    if (note.poi_id === null) continue
    const existing = byPoi.get(note.poi_id)
    if (existing === undefined) byPoi.set(note.poi_id, [note])
    else existing.push(note)
  }

  const rollups = new Map<string, NoteRollup>()
  for (const [poiId, poiNotes] of byPoi) rollups.set(poiId, rollUpNotes(poiNotes, now))
  return rollups
}
