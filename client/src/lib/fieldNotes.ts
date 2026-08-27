// Field notes: the vocabulary of a dated observation about a place, and the
// wire shapes it travels in (features/FIELD_NOTES.md).
//
// This module owns WHAT a note is; lib/noteRollup.ts owns what the map
// derives from many of them; DATA_NUDGES.md (built as #759's surfaces) owns
// WHEN the app asks for one. A note is what someone saw, where, and when
// they saw it - not a rating, not a thread, and never the input to a score.

// Type-only, so nothing here reaches userPreferences at runtime and the two
// modules cannot form a cycle whatever either grows into.
import type { ReporterType } from './userPreferences'

/**
 * The types a hiker is ever asked about (features/DATA_NUDGES.md): water
 * first, then where they sleep, then where they resupply, then the way off
 * the trail. "Just important things like food and shelter", explicitly not
 * viewpoints, bridges or privies. A viewpoint with no data is not a gap; a
 * spring with no data is a hiker carrying the wrong amount of water.
 *
 * Order is the ask's priority, water first - the maintainer's own ordering,
 * restated as a rule the code applies (#759).
 *
 * PARKING JOINED THIS LIST AT #1122, and it is a reversal of a sentence
 * DATA_NUDGES.md wrote down rather than a gap being filled: that doc scoped
 * the ask to food and shelter "explicitly not viewpoints, parking, bridges,
 * or privies". What changed is not the principle but which side of it
 * parking falls on. map/poiPriority.ts already argues the case, for a
 * different purpose: parking sits above the rest of the tail there "because
 * it is the way off the trail: the pin a hiker looks for when the weather
 * turns or an ankle goes, which is the same argument water and shelter win
 * on." A full lot at a trailhead is a hiker's exit being unavailable, and it
 * is the one place on this map where capacity is a fact somebody standing
 * there can actually see.
 *
 * The list has three readers beyond the card, and adding to it moves all of
 * them: lib/stalenessDisplay.ts (which pins wear a freshness tier),
 * lib/passedToday.ts by way of App.tsx (the Volunteer tab's evening list),
 * and chrome/PoiCard.tsx (whether the expand promises notes).
 */
export const NOTE_SCOPED_TYPES = [
  'water',
  'shelter',
  'campsite',
  'resupply',
  'parking',
] as const

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
 *
 * WHY A SHELTER IS NO LONGER ASKED WHETHER IT IS FULL (#1122). Capacity is
 * the thing this project has already decided it will not claim: a shelter
 * whose capacity nobody stands behind exports no capacity, because "a hiker
 * deciding whether to push on to the next shelter is better served by no
 * answer than by a made-up one" (CLAUDE.md). A one-tap `full` is that same
 * unbacked number wearing a button - and worse than the export's silence,
 * because it arrives dated and attributed. `damaged` is the answer worth the
 * peek's second slot, and `trash` is the fourth the expand has room for.
 *
 * `full` survives on parking, where it is the whole point, and survives in
 * the backend enum either way: removing an accepted request value is the one
 * enum change that breaks a client already in the field
 * (backend/scripts/check_openapi_compat.py).
 */
export type WaterObservation = 'flowing' | 'trickling' | 'dry'
export type ShelterObservation = 'fine' | 'damaged' | 'trash'
export type ResupplyObservation = 'open' | 'limited' | 'closed'
export type ParkingObservation = 'open' | 'full' | 'trash'
/** The one value every type shares: the field contradicting upstream on
 *  upstream's own ground (#876). */
export type DisputeObservation = 'not_found'
export type NoteObservation =
  | WaterObservation
  | ShelterObservation
  | ResupplyObservation
  | ParkingObservation
  | DisputeObservation

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

/** Litter, at a place somebody sleeps at or parks in (#1122). Shares its
 *  name with the report type it escalates into (screens/ReportTypePicker.tsx)
 *  because they are the same complaint at two weights - one tap that dates
 *  the observation, and a form that puts it in front of a maintainer. */
const TRASH: ObservationOption = { id: 'trash', label: 'Trash' }

export const OBSERVATION_OPTIONS: Record<NoteScopedType, ObservationOption[]> = {
  water: [
    { id: 'flowing', label: 'Flowing' },
    { id: 'trickling', label: 'Trickling' },
    { id: 'dry', label: 'Dry' },
    NOT_FOUND,
  ],
  shelter: [
    { id: 'fine', label: 'Good shape' },
    { id: 'damaged', label: 'Damaged' },
    TRASH,
    NOT_FOUND,
  ],
  campsite: [
    { id: 'fine', label: 'Good shape' },
    { id: 'damaged', label: 'Damaged' },
    TRASH,
    NOT_FOUND,
  ],
  resupply: [
    { id: 'open', label: 'Open' },
    { id: 'limited', label: 'Limited stock' },
    { id: 'closed', label: 'Closed' },
    NOT_FOUND,
  ],
  parking: [
    { id: 'open', label: 'Open' },
    { id: 'full', label: 'Full' },
    TRASH,
    NOT_FOUND,
  ],
}

/**
 * The two answers a peeking card carries: the good end, and the problem this
 * kind of place is most often standing in front of.
 *
 * NAMED PER TYPE RATHER THAN DERIVED, and that is #1122's correction to
 * #941's rule. This used to read the first and last answer off
 * {@link OBSERVATION_OPTIONS} - "the ends of the scale" - which worked while
 * every list happened to be ordered best-to-worst. It stops working the
 * moment a list holds two different problems: with `trash` added, the ends
 * rule puts *Trash* on a shelter's peek and hides *Damaged*, and puts *Trash*
 * on parking's peek instead of *Full*. A derived rule that is wrong for two
 * of five types is a table wearing a function's clothes, so this is the
 * table.
 *
 * The pairing itself is REASONED and it is worth saying which parts are not
 * measured. Nobody has watched a hiker choose between these standing at a
 * spring. What keeps the cost of a wrong pair low is that the peek is a
 * shortcut and never a filter: every option, `not_found` included, is one tap
 * away in the opened card, so a hiker at a trickling spring is delayed rather
 * than silenced. If field use (#105, #106) says the middle answer is the
 * common one for some type, this table is the one place to change.
 *
 * `not_found` is never here. It answers a different question from the answers
 * above it - see NOT_FOUND - and a dispute filed by a mis-hit on a crowded
 * peek is the claim #876 built corroboration to keep out.
 */
export const QUICK_ANSWERS: Record<
  NoteScopedType,
  { good: NoteObservation; problem: NoteObservation }
> = {
  water: { good: 'flowing', problem: 'dry' },
  shelter: { good: 'fine', problem: 'damaged' },
  campsite: { good: 'fine', problem: 'damaged' },
  resupply: { good: 'open', problem: 'closed' },
  parking: { good: 'open', problem: 'full' },
}

export function peekObservations(poiType: NoteScopedType): readonly ObservationOption[] {
  const { good, problem } = QUICK_ANSWERS[poiType]
  const options = OBSERVATION_OPTIONS[poiType]
  // Looked up rather than constructed, so the peek's button and the opened
  // card's button for the same value are the same object - one label, one
  // id, and no way for the two heights to drift apart. The filter is a
  // guard for a table this file owns and could mistype; the test asserts it
  // never fires.
  return [good, problem].flatMap((id) => options.filter((option) => option.id === id))
}

/**
 * Whose vocabulary the good answer is offered in.
 *
 * Three lists rather than four, because `thru` and `section` are the same
 * voice - both are reporting a night they spent somewhere - and the
 * distinction the app draws between them is about standing in a moderation
 * queue, not about words.
 */
type Voice = 'long' | 'day' | 'maintainer'

function voiceFor(reporterType: ReporterType): Voice {
  if (reporterType === 'maintainer') return 'maintainer'
  return reporterType === 'thru' || reporterType === 'section' ? 'long' : 'day'
}

/**
 * THE ONE RULE EVERY WORD BELOW CLEARS (#1122), and it is stricter than the
 * first draft of it: **a rotating word must be a SYNONYM for the value it
 * files, carrying nothing that value does not.**
 *
 * There are two ways to break it and the second is the one that is easy to
 * miss.
 *
 * INTENSITY. "Gushing" claims more flow than `flowing` does. A hiker at a
 * merely adequate spring would decline to tap it, and one who taps it anyway
 * has been nudged into overstating what is in front of them. "Stocked up"
 * fails the same way: a store that is open but picked clean is `limited`.
 *
 * SPECIFICITY, which killed the good words. `fine` means "nothing wrong
 * here". It does not mean dry, or level, or that the roof is sound. So "Dry
 * inside", "Stakes hold", "Roof's on" and "Prime spot" are all out, and they
 * were the whole charm of the draft this replaced. Each fails in BOTH
 * directions at once: a hiker at a sound but damp shelter declines to tap
 * "Dry inside" and the note is lost, while one who taps it anyway believes
 * they said something the record does not hold. That second half is the
 * failure this project names as its worst - a display outrunning its source -
 * pointed inward at the hiker rather than outward at the next reader.
 *
 * AND NO WORD MAY READ AS A SCORE. "Five stars", "10/10", "Best on the
 * trail". A note is a dated observation and never a rating; the moment a
 * button reads like one, the whole surface changes meaning
 * (OurHikeValues.md's anti-gamification rule, which DATA_NUDGES.md states
 * four times).
 *
 * That rule is why water, resupply and parking each get ONE list rather than
 * three. Their values are already specific - `flowing`, `open` - so there is
 * exactly one thing to say and only its wording varies. `fine` is the single
 * generic value on the board, so it is the only place a role's voice has room
 * to differ, and what differs is HOW SOMEBODY KNOWS rather than what they are
 * claiming: a day hiker walked past, a thru-hiker slept there, a maintainer
 * inspected it. "No work due" is the one genuinely role-specific word that
 * survives intact - to somebody carrying a saw, that IS what `fine` means.
 *
 * @unvalidated - nobody has watched a hiker read any of these on a phone in
 * daylight, and the claim that a rotating word gets more taps than a fixed
 * one is untested. What settles it is the same field use (#105, #106) that
 * settles the peek pair above. What is NOT at stake in that test is honesty:
 * every word here files the same value, so a wrong pick costs a tap, never a
 * wrong record.
 */
const WATER_WORDS = ['Flowing', 'Running', 'Water’s on', 'Flowing fine'] as const
const RESUPPLY_WORDS = ['Open', 'Doors open', 'Lights on', 'Open today'] as const
/** `open` on a lot means "there is a space", not "there are plenty" - which
 *  is why "Room to spare" is not here and "Space free" is. */
const PARKING_WORDS = ['Spots open', 'Got a spot', 'Space free', 'Room to park'] as const

const FINE_WORDS: Record<Voice, readonly string[]> = {
  long: ['All good', 'No complaints', 'Good to go', 'All’s well'],
  day: ['All good', 'Looks fine', 'No problems', 'Looks good'],
  maintainer: ['No work due', 'All good', 'Good order', 'Serviceable'],
}

/** One list, dealt to every voice - the shape of "there is only one honest
 *  way to say this, and it does not depend on who is saying it". A shared
 *  reference rather than three copies, so it is a rule that cannot drift. */
function everyVoice(words: readonly string[]): Record<Voice, readonly string[]> {
  return { long: words, day: words, maintainer: words }
}

const GOOD_WORDS: Record<NoteScopedType, Record<Voice, readonly string[]>> = {
  water: everyVoice(WATER_WORDS),
  shelter: FINE_WORDS,
  campsite: FINE_WORDS,
  resupply: everyVoice(RESUPPLY_WORDS),
  parking: everyVoice(PARKING_WORDS),
}

/**
 * Every way this hiker might be offered the good answer for this place.
 *
 * Takes the SIGNED reporter type - what `signReportAs` returns - rather than
 * the stored preference, so somebody who never answered the identity screen
 * is dealt the day hiker's list by the same floor that signs their notes
 * (lib/reporterIdentity.ts). One answer to "who is this", not two.
 */
export function goodWords(
  poiType: NoteScopedType,
  reporterType: ReporterType,
): readonly string[] {
  return GOOD_WORDS[poiType][voiceFor(reporterType)]
}

/**
 * One of them, at random.
 *
 * `random` is injectable for the tests rather than for the app: a rotation
 * whose only assertion is "it eventually says all four" is a flaky test, and
 * a seam here is what lets the suite pin the mapping exactly.
 *
 * THE CALLER MUST HOLD THE RESULT STILL. The peek and the opened card are one
 * component at two heights, and a shelter whose peek says "All good" and
 * whose opened card says "No complaints" reads as two different questions
 * being asked. chrome/FieldNoteSection.tsx picks once per waypoint and keeps
 * it, which is also what stops the word changing under a hiker's thumb on an
 * unrelated re-render.
 */
export function pickGoodWord(
  poiType: NoteScopedType,
  reporterType: ReporterType,
  random: () => number = Math.random,
): string {
  const words = goodWords(poiType, reporterType)
  return words[Math.floor(random() * words.length)] ?? words[0]
}

/**
 * How the card opens its acknowledgement of a tap (#1122).
 *
 * These rotate freely and carry none of the rule above, because they are the
 * app speaking about ITSELF rather than about the place: "Logged." claims
 * nothing about a shelter. That is the whole reason they exist - the buttons
 * had to become plain to stay honest, and this is the line where a bit of
 * warmth costs nothing.
 *
 * What follows them does not rotate. "It sends when there's signal" is the
 * offline outbox explaining itself, and it is the one sentence on this
 * surface a hiker actually needs to read.
 */
export const NOTED_OPENERS = [
  'Logged.',
  'Got it.',
  'Noted, thanks.',
  'On the record.',
  'That’s in.',
] as const

export function pickNotedOpener(random: () => number = Math.random): string {
  return NOTED_OPENERS[Math.floor(random() * NOTED_OPENERS.length)] ?? NOTED_OPENERS[0]
}

/** What the observation words mean on a card or in a lane, for reading
 *  rather than tapping.
 *
 *  THE CANONICAL WORD, and the counterweight to the rotation above: a button
 *  may say "All good" or "No complaints" or "Serviceable", and every surface
 *  that READS the note back - the history list, the roll-up headline, the
 *  card's freshness line - prints what is here. A record that read differently
 *  on two screens would be the same note telling two stories.
 *
 *  Includes `not_found` because BAKED notes may carry it, and `full` because
 *  notes filed on shelters before #1122 still hold it - a word this build
 *  cannot read must render as itself rather than crash a card. */
export function observationLabel(observation: string): string {
  const labels: Record<string, string> = {
    flowing: 'Flowing',
    trickling: 'Trickling',
    dry: 'Dry',
    // "Good shape" rather than "Fine" (#1122). The stored value is unchanged,
    // so every note already filed reads correctly; what changed is that
    // "Fine - 6 days ago, thru-hiker" was the flattest sentence on the card
    // and this one is a sentence.
    fine: 'Good shape',
    damaged: 'Damaged',
    trash: 'Trash',
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
 * `damaged` and `trash` each go straight to the one report type that names
 * them. `dry` opens the picker instead of guessing: no report type is "a dry
 * spring", and pre-picking a wrong one would file a flooding report about the
 * absence of water.
 *
 * `full` NO LONGER ESCALATES (#1122), and that is a change to the sentence
 * DATA_NUDGES.md wrote rather than a drift from it. `full` now exists only on
 * parking, and nothing in the report picker describes a busy lot - so "want
 * to report this?" after it would be a prompt pointing at nowhere, which is a
 * control teaching a hiker not to trust its labels. What a hiker at a full
 * lot with something else to say reaches for instead is the report entry the
 * opened card now keeps visible at all times.
 */
export function escalationFor(
  observation: NoteObservation,
): { kind: 'form'; type: 'shelter_repair' | 'trash' } | { kind: 'pick' } | null {
  if (observation === 'damaged') return { kind: 'form', type: 'shelter_repair' }
  if (observation === 'trash') return { kind: 'form', type: 'trash' }
  if (observation === 'dry') return { kind: 'pick' }
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
