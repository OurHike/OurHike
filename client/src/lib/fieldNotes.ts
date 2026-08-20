// Field notes: the vocabulary of a dated observation about a place, and the
// wire shapes it travels in (features/FIELD_NOTES.md).
//
// This module owns WHAT a note is; lib/noteRollup.ts owns what the map
// derives from many of them; DATA_NUDGES.md (built as #759's surfaces) owns
// WHEN the app asks for one. A note is what someone saw, where, and when
// they saw it - not a rating, not a thread, and never the input to a score.

/**
 * The types a hiker is ever asked about (features/DATA_NUDGES.md): water
 * first, then where they sleep, then where they resupply - "just important
 * things like food and shelter", explicitly not viewpoints, parking or
 * privies. A viewpoint with no data is not a gap; a spring with no data is
 * a hiker carrying the wrong amount of water.
 *
 * Order is the ask's priority, water first - the maintainer's own ordering,
 * restated as a rule the code applies (#759).
 */
export const NOTE_SCOPED_TYPES = ['water', 'shelter', 'campsite', 'resupply'] as const

export type NoteScopedType = (typeof NOTE_SCOPED_TYPES)[number]

export function isNoteScopedType(poiType: string): poiType is NoteScopedType {
  return (NOTE_SCOPED_TYPES as readonly string[]).includes(poiType)
}

/**
 * The one-tap answers, by POI type. Mirrors the backend's `Observation`
 * enum (backend/app/models/field_note.py) - which holds every value in one
 * enum because the server cannot police the pairing (it has no POI table);
 * this table is where the pairing actually lives, and the picker only ever
 * offers a type its place can wear.
 *
 * `not_found` - the dispute value - is deliberately NOT offered here yet.
 * FIELD_NOTES.md §4's corroboration, decay and existence-axis rendering are
 * their own build; a button that files disputes before anything renders or
 * decays them would collect claims nobody can see or retract.
 */
export type WaterObservation = 'flowing' | 'trickling' | 'dry'
export type ShelterObservation = 'fine' | 'damaged' | 'full'
export type ResupplyObservation = 'open' | 'limited' | 'closed'
export type NoteObservation = WaterObservation | ShelterObservation | ResupplyObservation

export interface ObservationOption {
  id: NoteObservation
  label: string
}

export const OBSERVATION_OPTIONS: Record<NoteScopedType, ObservationOption[]> = {
  water: [
    { id: 'flowing', label: 'Flowing' },
    { id: 'trickling', label: 'Trickling' },
    { id: 'dry', label: 'Dry' },
  ],
  shelter: [
    { id: 'fine', label: 'Fine' },
    { id: 'damaged', label: 'Damaged' },
    { id: 'full', label: 'Full' },
  ],
  campsite: [
    { id: 'fine', label: 'Fine' },
    { id: 'damaged', label: 'Damaged' },
    { id: 'full', label: 'Full' },
  ],
  resupply: [
    { id: 'open', label: 'Open' },
    { id: 'limited', label: 'Limited stock' },
    { id: 'closed', label: 'Closed' },
  ],
}

/** What the observation words mean on a card or in a lane, for reading
 *  rather than tapping. Includes `not_found` because BAKED notes may carry
 *  it once disputes ship, and a word this build cannot read must render as
 *  itself rather than crash a card. */
export function observationLabel(observation: string): string {
  const labels: Record<string, string> = {
    flowing: 'Flowing',
    trickling: 'Trickling',
    dry: 'Dry',
    fine: 'Fine',
    damaged: 'Damaged',
    full: 'Full',
    open: 'Open',
    limited: 'Limited stock',
    closed: 'Closed',
    not_found: 'Reported missing',
  }
  return labels[observation] ?? observation
}

/**
 * Which taps invite a real Report afterwards, and to which type.
 *
 * DATA_NUDGES.md: "tapping 'dry' or 'full' prompts 'want to report this?'"
 * - the note is already filed either way; the escalation reuses Report a
 * Problem's machinery exactly where it is needed (FIELD_NOTES.md §5's
 * hand-off) rather than duplicating problem handling here.
 *
 * `damaged` goes straight to the one report type that names it. `dry` and
 * `full` open the picker instead of guessing: no report type is "a dry
 * spring", and pre-picking a wrong one would file a flooding report about
 * the absence of water.
 */
export function escalationFor(
  observation: NoteObservation,
): { kind: 'form'; type: 'shelter_repair' } | { kind: 'pick' } | null {
  if (observation === 'damaged') return { kind: 'form', type: 'shelter_repair' }
  if (observation === 'dry' || observation === 'full') return { kind: 'pick' }
  return null
}

/**
 * The note a phone queues - lib/outbox.ts's fourth cargo. Field names match
 * the POST /field-notes wire exactly (backend/app/schemas/field_note.py),
 * because the outbox sends this object as the request body with only
 * `observed_at` and `id` added from the item that carries it.
 *
 * `lat`/`lon` are the POI's own coordinates when the note is written from a
 * card - the fallback anchor FIELD_NOTES.md §7 re-anchors an orphan by - or
 * the GPS fix when there is no card. The card path never waits on GPS: the
 * place's position is already known, and it is the place being described.
 */
export interface FieldNoteDraft {
  poi_id?: string
  lat?: number
  lon?: number
  mile?: number
  observation?: NoteObservation
  note?: string
  reporter_type: 'thru' | 'section' | 'day' | 'maintainer'
}

/**
 * One note as every reader sees it - the anonymous serialisation of
 * GET /field-notes, and (minus nothing) the shape baked into
 * conditions/notes.json. `reporter_id` and `posted_at` are deliberately not
 * here at all rather than optional: the client must not learn to read
 * fields the wire withholds (#252's lesson, applied before the leak).
 */
export interface NoteSummary {
  id: string
  poi_id: string | null
  lat: number | null
  lon: number | null
  mile: number | null
  observation: string | null
  note: string | null
  /** ISO timestamp, `...Z`-stamped by the server and by the bake alike. */
  observed_at: string
  reporter_type: 'thru' | 'section' | 'day' | 'maintainer'
}
