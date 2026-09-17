// Where a report is, and how the phone knows (#1563).
//
// ONE MODULE FOR THREE SURFACES. The report window, the long form and the
// closure form each let a hiker say where a report is, and until this module
// each spelled the answer differently: the window offered the places walked
// past today, the form offered a crosshair, the closure form a typed mile -
// and none of them could name a waypoint the report had not started from.
// This is the vocabulary they share now: what a choice IS, what it is CALLED
// on screen, what it becomes ON THE WIRE, and which named places are worth
// offering. reporting/LocationPicker.tsx draws it; nothing else spells it.
//
// THE FIX IS NEVER FROZEN INTO A CHOICE. `{ kind: 'fix' }` carries no
// coordinates: it means "wherever the phone is when this files", and the
// caller resolves it against the live watch at that moment. Copying the fix
// into the choice when the window opened would file a report at where the
// hiker WAS when they reached for the phone - the stale-fix failure the two
// provenance fields below exist to make visible, built into the data model.
//
// THE PROVENANCE IS THE POINT, not decoration on the coordinates. A blowdown
// at 35.6123, -83.4987 can be a waypoint's surveyed position, a fix under
// canopy with an 800 m radius, or a thumb on a map at a planning zoom, and a
// moderator deciding whether to send a crew is owed the difference. So the
// wire carries which (`location_source`) and, for a fix, the two numbers that
// bound it: the radius the platform stated, and how old the fix was when the
// report took it. lib/useGeolocation.ts keeps the last fix through a pocketed
// pause (#313), which is right for the mile readout and is exactly why the
// age matters here - a radius of 5 m on a fix from forty minutes ago is not
// 5 m of anything.
//
// NOTHING HERE GUESSES. A choice with no fix and no place resolves to no
// coordinates, never to 0,0 (the Atlantic off West Africa) and never to the
// hiker's words turned into a pin: `place_words` travels as prose, exactly as
// screens/ReportForm.tsx has sent it since #1439, and a moderator places it.

import { straightLineMetres } from './dayHikeShelf'
import type { ReportDraft } from './outbox'
import { placeWords } from './placement'
import { searchPois, type SearchablePoi } from './searchPoi'
import { metresToMiles } from './trailGraph'
import type { LonLat } from './trailPosition'
import {
  feetFromMetres,
  formatDistance,
  formatShortDistance,
  type UnitSystem,
} from './units'

/**
 * The phone's own position, distilled for the report path from
 * lib/useGeolocation.ts's `located` state and the shell's snap of it.
 *
 * `accuracyM` is the platform's own figure, unconverted - a 95% radius under
 * the W3C Geolocation definition, from the web watch only. lib/gpsTrace.ts
 * keeps the native plugin's 68% radius apart from this for a reason, and the
 * report path never reads that plugin, so one number is honest here.
 */
export interface FixSnapshot {
  lat: number
  lon: number
  /** The centerline mile the shell snapped the fix to, or absent - off the
   *  corridor, or no trail index on the phone yet. */
  mile?: number
  /** Metres, 95% confidence, as `position.coords.accuracy` gave it. */
  accuracyM: number
  /** When the platform produced the fix - `position.timestamp`. */
  fixedAt: Date
}

/**
 * Where a report is, as the hiker chose it.
 *
 * `poi` is the preferred answer and the only one that names a place: the
 * report is ABOUT that waypoint, its coordinates are the waypoint's, and the
 * moderation queue reads it by id. `point` is a spot marked by hand - the
 * map's long press, or the crosshair. `fix` is the phone, resolved at filing
 * (see the header) - and the only kind that can resolve to nothing.
 */
export type LocationChoice =
  | { kind: 'poi'; poiId: string; name: string; lat: number; lon: number; mile?: number }
  | { kind: 'fix' }
  | { kind: 'point'; lat: number; lon: number; mile?: number }

/** The default every door that supplies no place opens on. One shared object
 *  rather than a fresh literal per door, so state keyed on it keeps identity. */
export const AT_THE_FIX: LocationChoice = { kind: 'fix' }

/** Every field of the wire shape this module decides. */
export type ReportLocationFields = Pick<
  ReportDraft,
  | 'poi_id'
  | 'lat'
  | 'lon'
  | 'mile'
  | 'place_words'
  | 'location_source'
  | 'location_accuracy_m'
  | 'location_fix_age_s'
>

/** Whether this choice, resolved now, would give the report a place at all.
 *  A waypoint and a marked spot always do; the fix only while there is one. */
export function hasPlace(choice: LocationChoice, fix: FixSnapshot | null): boolean {
  return choice.kind !== 'fix' || fix !== null
}

/** Seconds between the fix's own timestamp and `now`, floored at zero - a
 *  fix from the future is a clock problem, not a fact about the fix. */
export function fixAgeSeconds(fixedAt: Date, now: Date): number {
  return Math.max(0, Math.round((now.getTime() - fixedAt.getTime()) / 1000))
}

/**
 * How long a fix may sit before the picker says the hiker may have moved.
 *
 * @unvalidated - five minutes is picked, not measured. What bounds the cost
 * of it being wrong is that the number never changes what is RECORDED: the
 * age travels in seconds whatever this says, and the threshold only decides
 * whether the picker adds a sentence. What would settle it is the fix-age
 * distribution on real reports once `location_fix_age_s` has been collected
 * for a season - if most reports file within a minute of a fix, the warning
 * can sit lower; if pocketed phones routinely carry ten-minute fixes onto the
 * trail, it should.
 */
export const STALE_FIX_SECONDS = 5 * 60

export function fixIsStale(fixedAt: Date, now: Date): boolean {
  return fixAgeSeconds(fixedAt, now) >= STALE_FIX_SECONDS
}

/**
 * The radius past which a fix is worth a word before anybody files under it.
 *
 * @unvalidated - a hundred metres is picked, not measured. The reasoning it
 * rests on: a GNSS fix under open sky states a radius of a few metres and
 * under canopy a few tens, while a fix from wifi or a cell tower states
 * tens to thousands - so a hundred is about where the platform has stopped
 * seeing satellites, which is the case a hiker standing at a blowdown should
 * be told about. What would settle it is the radius distribution on real
 * `gps` reports, which the column now collects. Like STALE_FIX_SECONDS it
 * changes only whether a line is drawn, never what is recorded.
 */
export const COARSE_FIX_METRES = 100

/**
 * Whether the report window prints the fix's provenance UNDER its place line
 * rather than only inside the picker (#1563).
 *
 * The line costs height on the smallest phone: with it always drawn, the
 * tile frame that #1480 made fit at 375x667 scrolled again on WebKit by 7 px
 * (measured in CI on 949555d). So it is spent only when it carries a
 * warning - a fix that is stale, or coarser than {@link COARSE_FIX_METRES} -
 * and the ordinary fresh, tight fix reads as its mile alone, with the radius
 * and age one tap away in the picker's own row.
 */
export function fixNeedsAWord(fix: FixSnapshot, now: Date): boolean {
  return fixIsStale(fix.fixedAt, now) || fix.accuracyM >= COARSE_FIX_METRES
}

/** "just now", "12 min ago", "3 hr ago" - coarse on purpose, for a line read
 *  at arm's length. The exact seconds are what the wire carries. */
export function fixAgeWords(fixedAt: Date, now: Date): string {
  const seconds = fixAgeSeconds(fixedAt, now)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  return `${Math.floor(minutes / 60)} hr ago`
}

/**
 * The fix as a hiker reads it: "±16 ft · just now", or, past
 * {@link STALE_FIX_SECONDS}, "±16 ft · 12 min ago — you may have moved since".
 *
 * The radius goes through lib/units.ts like every other length this app
 * prints, and it is a LENGTH rather than a distance along anything, which is
 * why it takes `formatShortDistance` and not `formatDistance`.
 */
export function fixWords(fix: FixSnapshot, units: UnitSystem, now: Date): string {
  const radius = `±${formatShortDistance(feetFromMetres(fix.accuracyM), units)}`
  const age = fixAgeWords(fix.fixedAt, now)
  return fixIsStale(fix.fixedAt, now)
    ? `${radius} · ${age} — you may have moved since`
    : `${radius} · ${age}`
}

/**
 * What a report's place becomes on the wire.
 *
 * ONE FUNCTION FOR EVERY SURFACE THAT FILES, so the window and the long form
 * cannot come to disagree about what a `gps` report carries. The rules:
 *
 *  - a waypoint sends its id AND its coordinates, so a phone whose data
 *    release has dropped the waypoint still has somewhere to draw the pin;
 *  - a marked spot sends coordinates and says they were marked;
 *  - the fix sends coordinates, the radius, and the age as of `now` - the
 *    moment the report is filed, which is the moment the coordinates are
 *    committed to it;
 *  - the fix with NO fix sends the hiker's words, when they gave any, and
 *    otherwise nothing at all. Absent, never zero, never a pin made of prose.
 *
 * The mile is omitted rather than zeroed wherever it is unknown: mi 0.0 is
 * Springer Mountain, and the serious-warnings banner filters on this number.
 */
export function reportLocationFields(
  choice: LocationChoice,
  fix: FixSnapshot | null,
  now: Date,
  words = '',
): ReportLocationFields {
  switch (choice.kind) {
    case 'poi':
      return {
        poi_id: choice.poiId,
        lat: choice.lat,
        lon: choice.lon,
        ...(choice.mile !== undefined ? { mile: choice.mile } : {}),
        location_source: 'poi',
      }
    case 'point':
      return {
        lat: choice.lat,
        lon: choice.lon,
        ...(choice.mile !== undefined ? { mile: choice.mile } : {}),
        location_source: 'map',
      }
    case 'fix': {
      if (fix === null) {
        const trimmed = words.trim()
        return trimmed === '' ? {} : { place_words: trimmed }
      }
      return {
        lat: fix.lat,
        lon: fix.lon,
        ...(fix.mile !== undefined ? { mile: fix.mile } : {}),
        location_source: 'gps',
        // A tenth of a metre is below anything a radius claims, and it stops
        // a platform float like 4.999999 travelling as fourteen digits of
        // precision nobody stated.
        location_accuracy_m: Math.round(fix.accuracyM * 10) / 10,
        location_fix_age_s: fixAgeSeconds(fix.fixedAt, now),
      }
    }
  }
}

/** The words for one place, in the three forms the surfaces print. */
export interface LocationWords {
  /** What a header or a line states - "Bailey Gap Shelter", "mi 628.4",
   *  "Where you are", "No location yet". */
  label: string
  /**
   * The same place as a phrase the receipt can end a sentence with - "at
   * Bailey Gap Shelter", "here", "at the spot you marked". A second field
   * rather than `at ${label}` because "here" is an adverb and the others are
   * nouns: composing the preposition produced "Filed — blow down at here" the
   * first time this screen was photographed with no fix (#1133).
   */
  phrase: string
  /** One line under the label saying HOW the place is known - the provenance
   *  the wire carries, in words. Null where there is nothing to say. */
  detail: string | null
}

/**
 * How a choice reads, resolved against the fix as it is right now.
 *
 * The mile marker is written through lib/placement.ts's `placeWords` so the
 * window, the form, the press plate and the crosshair bar cannot come to
 * describe one point differently; a marker is never a distance and never
 * goes through `formatDistance` (#986).
 */
export function locationWords(
  choice: LocationChoice,
  fix: FixSnapshot | null,
  units: UnitSystem,
  knowsTrail: boolean,
  now: Date,
  words = '',
): LocationWords {
  switch (choice.kind) {
    case 'poi': {
      const marker =
        choice.mile === undefined ? null : placeWords(choice.mile, true, units)
      return {
        label: choice.name,
        phrase: `at ${choice.name}`,
        detail: marker === null ? 'A named place' : `A named place · ${marker}`,
      }
    }
    case 'point': {
      // The three answers placement.ts gives - a mile, "This spot", or more
      // than 3 mi off the trail - and never a mile borrowed from the hiker.
      const label = placeWords(choice.mile ?? null, knowsTrail, units)
      return {
        label,
        phrase: choice.mile === undefined ? 'at the spot you marked' : `at ${label}`,
        detail: 'Marked on the map',
      }
    }
    case 'fix': {
      if (fix === null) {
        return words.trim() === ''
          ? { label: 'No location yet', phrase: 'here', detail: null }
          : { label: 'In your words', phrase: 'where you described', detail: null }
      }
      const label =
        fix.mile === undefined ? 'Where you are' : placeWords(fix.mile, true, units)
      return {
        label,
        phrase: fix.mile === undefined ? 'here' : `at ${label}`,
        detail: `Your position · ${fixWords(fix, units, now)}`,
      }
    }
  }
}

/**
 * The trail mile a choice resolves to, or null - what the closure form fills
 * its "shut from" box with when a hiker picks a place rather than typing one.
 * A named place or a marked spot carries its own mile or none; the fix
 * carries the shell's snap of it. Null is the honest answer for anything
 * off the corridor, and the closure form refuses to guess from it.
 */
export function chosenMile(
  choice: LocationChoice,
  fix: FixSnapshot | null,
): number | null {
  if (choice.kind === 'fix') return fix?.mile ?? null
  return choice.mile ?? null
}

/** A waypoint as the picker can offer it: search's own view of it, with the
 *  coordinates a choice needs. Required rather than looked up at pick time,
 *  for the reason the old passed-places list gave: a lookup at pick time is
 *  an `undefined` in front of somebody at exactly the moment `lat: 0, lon: 0`
 *  looks like a reasonable default. */
export interface PlaceCandidate extends SearchablePoi {
  lat: number
  lon: number
}

export interface NearbyPlace extends PlaceCandidate {
  /** Straight-line miles from the reference point, or null with none. A
   *  DISTANCE, so it converts; the mile marker beside it does not. */
  awayMiles: number | null
}

/**
 * How far a named place may be from the reference point and still be
 * offered unasked.
 *
 * @unvalidated - two miles is picked. It is wide enough to reach the shelter
 * behind a hiker who noticed a blowdown and walked on, and narrow enough that
 * the list is places they could plausibly be reporting about rather than a
 * gazetteer; the filter box reaches everything else by name. What would
 * settle it is how far the waypoint actually chosen sits from the fix on real
 * reports, which `location_source: 'poi'` rows now make measurable.
 */
export const NEARBY_WITHIN_MILES = 2

/**
 * How many nearby rows the sheet draws unasked; the filter reaches the rest.
 *
 * @unvalidated - eight is a guess at what a hand scans without scrolling on
 * a phone, not a measurement. What would settle it is how often the place a
 * hiker actually chooses sits past the cut, which `location_source: 'poi'`
 * rows make countable against the nearest-first order once they exist.
 */
export const NEARBY_LIMIT = 8

/** What a by-name search may be asked to leave out. */
export interface SearchPlacesOptions {
  /** Only places that carry a mile - the closure form's ask, applied before
   *  the cap rather than after it. */
  withMile?: boolean
}

export function awayMiles(place: LonLat, reference: LonLat | null): number | null {
  return reference === null ? null : metresToMiles(straightLineMetres(reference, place))
}

function nearestFirst(a: NearbyPlace, b: NearbyPlace): number {
  return (
    (a.awayMiles ?? Number.POSITIVE_INFINITY) -
      (b.awayMiles ?? Number.POSITIVE_INFINITY) || a.name.localeCompare(b.name)
  )
}

/**
 * The named places worth offering for this report, nearest first.
 *
 * Within {@link NEARBY_WITHIN_MILES} of the reference point - the report's
 * current place, or the fix - plus every place the hiker walked past today
 * (lib/passedToday.ts) at any distance, because "that spring a mile back" is
 * the re-anchor the old list existed for and a SOBO's day runs the other
 * way. With no reference at all only the passed places remain, in name order.
 *
 * NO COUNT, ANYWHERE, and the caller must keep it so: a number here is a
 * scoreboard of places walked past without reporting, the guilt mechanic
 * DATA_NUDGES.md rules out four times.
 */
export function nearbyPlaces(
  candidates: readonly PlaceCandidate[],
  reference: LonLat | null,
  passedIds: ReadonlySet<string> = new Set(),
  { limit = NEARBY_LIMIT, withinMiles = NEARBY_WITHIN_MILES } = {},
): NearbyPlace[] {
  const rows: NearbyPlace[] = []
  for (const candidate of candidates) {
    const away = awayMiles(candidate, reference)
    if (!passedIds.has(candidate.id) && (away === null || away > withinMiles)) continue
    rows.push({ ...candidate, awayMiles: away })
  }
  return rows.sort(nearestFirst).slice(0, limit)
}

/**
 * Places found by name, for the filter box - the same match search uses
 * (lib/searchPoi.ts), so a name findable on the map is findable here. With a
 * reference point the matches come nearest first, which is what turns "Spring"
 * from two hundred rows into the three that could be meant.
 */
export function placesByName(
  query: string,
  candidates: readonly PlaceCandidate[],
  reference: LonLat | null,
  limit = NEARBY_LIMIT,
): NearbyPlace[] {
  // Every match, not the search box's own first 25: that cap is applied
  // after a sort by where the word sits in the name, so with it in place
  // the nearest shelter to a hiker who typed "shelter" was usually not in
  // the result at all, and a row hundreds of miles off read as nearest
  // (review of #1571). The cap belongs after the distance sort, below.
  const found = searchPois(query, candidates, { limit: Number.POSITIVE_INFINITY }).map(
    (place) => ({
      ...place,
      awayMiles: awayMiles(place, reference),
    }),
  )
  return (reference === null ? found : found.sort(nearestFirst)).slice(0, limit)
}

/** "0.3 mi away" - a distance, through lib/units.ts, never a marker. */
export function awayWords(awayMiles: number, units: UnitSystem): string {
  return `${formatDistance(awayMiles, units)} away`
}
