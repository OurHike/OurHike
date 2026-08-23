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
 * `not_found` - the dispute value - is offered on every scoped type as of
 * #876, and the order it arrived in was deliberate: this comment used to say
 * it was withheld until "corroboration, decay and existence-axis rendering"
 * existed, because a button that files disputes before anything renders or
 * decays them collects claims nobody can see or retract. Those exist now
 * (lib/disputes.ts here, core/disputes.py on the server), so the button can.
 *
 * **It is offered on low-confidence POIs too**, which FIELD_NOTES.md §4 left
 * open. A hiker standing where an unverified spring should be cannot tell
 * "upstream never confirmed this" from "it is gone", and asking them to is
 * asking them to know our data's provenance. The place that answer is
 * weighed differently is the card's wording, not the picker.
 */
export type WaterObservation = 'flowing' | 'trickling' | 'dry'
export type ShelterObservation = 'fine' | 'damaged' | 'full'
export type ResupplyObservation = 'open' | 'limited' | 'closed'
/** The one value every type shares: the field contradicting upstream on
 *  upstream's own ground (#876). */
export type DisputeObservation = 'not_found'
export type NoteObservation =
  WaterObservation | ShelterObservation | ResupplyObservation | DisputeObservation

export interface ObservationOption {
  id: NoteObservation
  label: string
}

const NOT_FOUND: ObservationOption = {
  id: 'not_found',
  // "Not here" rather than "missing" or "gone": it is what the hiker can
  // actually see from where they are standing, and it does not ask them to
  // claim it was ever there. Last in every list, because it is the answer to
  // a different question from the three above it - those describe a place,
  // this one says there is no place to describe.
  label: 'Not here',
}

export const OBSERVATION_OPTIONS: Record<NoteScopedType, ObservationOption[]> = {
  water: [
    { id: 'flowing', label: 'Flowing' },
    { id: 'trickling', label: 'Trickling' },
    { id: 'dry', label: 'Dry' },
    NOT_FOUND,
  ],
  shelter: [
    { id: 'fine', label: 'Fine' },
    { id: 'damaged', label: 'Damaged' },
    { id: 'full', label: 'Full' },
    NOT_FOUND,
  ],
  campsite: [
    { id: 'fine', label: 'Fine' },
    { id: 'damaged', label: 'Damaged' },
    { id: 'full', label: 'Full' },
    NOT_FOUND,
  ],
  resupply: [
    { id: 'open', label: 'Open' },
    { id: 'limited', label: 'Limited stock' },
    { id: 'closed', label: 'Closed' },
    NOT_FOUND,
  ],
}

/**
 * The two answers a peeking card carries, for a type the app asks about.
 *
 * The ends of the scale: the first option, and the last one before
 * `not_found`. For water that is Flowing and Dry, which is the pair #941's
 * design pass drew on the peek - this rule is the generalisation of that
 * drawing rather than a second decision, and it hands every other scoped
 * type the same two ends: Fine and Full for a shelter or a campsite, Open
 * and Closed for a resupply.
 *
 * REASONED, and worth saying which parts are not measured. Nobody has
 * watched a hiker choose between these standing at a spring, and the
 * ordering the ends are read off is {@link OBSERVATION_OPTIONS}' own -
 * a maintainer's ordering, not an observed frequency. What keeps the cost
 * of a wrong pair low is that the peek is a shortcut and never a filter:
 * every option, `not_found` included, is one tap away in the opened card,
 * so a hiker at a trickling spring is delayed rather than silenced. If
 * field use (#105, #106) says the middle answer is the common one for some
 * type, this function is the one place to change.
 *
 * `not_found` is never offered here. It answers a different question from
 * the three above it - see NOT_FOUND - and a dispute filed by a mis-hit on
 * a crowded peek is the claim #876 built corroboration to keep out.
 */
export function peekObservations(poiType: NoteScopedType): readonly ObservationOption[] {
  const scale = OBSERVATION_OPTIONS[poiType].filter((option) => option.id !== 'not_found')
  const first = scale[0]
  const last = scale[scale.length - 1]
  // Both guards are for a table this file owns and could shrink: a type
  // whose scale is one option long has one end, not two, and would
  // otherwise render the same button twice.
  if (first === undefined || last === undefined || first === last) return scale
  return [first, last]
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
    not_found: 'Not here',
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
  /**
   * What the phone's own check found before the photo left it (#879, and
   * lib/photoScreen.ts for the check itself), or absent for "nothing found
   * OR could not look" - one value on purpose, because a note whose screen
   * failed must be indistinguishable from one whose screen was clean.
   *
   * Travels on the NOTE rather than with the bytes, because the note is what
   * the outbox flushes first: a verdict arriving after the photo would be a
   * hold applied to something already public.
   */
  photo_flagged?: 'nudity' | 'faces'
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
  /**
   * The note's photo (#879), presigned and short-lived, or null.
   *
   * Null covers four things at once and deliberately does not distinguish
   * them: no photo was attached, the bytes never landed, the photo is held
   * on a nudity flag until a person looks, or the server has no photo
   * storage. None of them is a fact a reader of a card can act on
   * differently, and telling them apart would tell a stranger that a held
   * photo exists.
   *
   * Optional as well as nullable, and the two mean different things - the
   * live read always sends the key, and `conditions/notes.json` baked before
   * this shipped omits it. The baseline omits it deliberately going forward
   * too: a presigned URL in a file that is cached for a day is a link that
   * is dead before most readers get to it (the same asymmetry #436 records
   * for baseline report photos).
   */
  photo_url?: string | null
}
