// The day hikes a hiker keeps (#976) - lib/trips.ts's design, one surface over.
//
// A finished draft (lib/dayHikeDraft.ts) becomes a DayHike here: a thing with
// an identity that survives the session, follows the account from day one
// (the maintainer's decision, 2026-08-25 - lib/dayHikesSync.ts), and comes
// back on the next phone.
//
// ONE DOCUMENT, ONE KEY, for the reasons trips.ts already argues: every saved
// day hike and which one is open live under a single key, so there is no
// pointer that can outlive the hike it names and no pair of writes that can
// half-land. There is no migration here - no earlier key ever held day hikes.
//
// WHAT IS PERSISTED IS THE ENDS, NEVER THE ROUTE.
//
// **CRITICAL: never persist a GraphPoint.edgeIndex - not in this store, not in
// any shape derived from it.** An edgeIndex is a positional index into the
// graph artifact's `edges` array, and build_trail_graph.py's `build_graph`
// fills that array in input-piece order and then compacts it (dropping
// float-noise loops, renumbering nodes) - so a republished graph silently
// shifts a stored index onto a DIFFERENT trail, with nothing anywhere to
// notice. A coordinate has no such dependence: it re-resolves against
// whatever graph the phone holds, through the same `nearestPointOnGraph`
// projection a fresh tap uses, and a coordinate the new graph cannot claim is
// REFUSED rather than silently reassigned. So a segment is the ordered
// coordinates the hiker tapped, and the route between them is recomputed, not
// stored.
//
// JUNK COSTS THE FIELD, NEVER THE STORE.
//
// Validation here SANITISES rather than refusing, which is lib/plan.ts's
// `validateRhythm` trade applied across a whole record: a field that carries
// no invariant the arithmetic assumes (a name, a date, a poiId, a flag) is
// repaired to its honest empty value when it is junk, and only the parts that
// ARE the hike - its identity and its tapped ends - can cost the hike itself.
// One unreadable hike is dropped rather than taking the store down with it,
// the same asymmetry validateTripStore states: losing one record is
// survivable, losing every record is not.

import { del, get, set } from 'idb-keyval'
import { recordDayHikeEdits } from './dayHikeSyncState'
import type { RouteClimb } from './trailGraph'

export const DAY_HIKES_KEY = 'ourhike:day-hikes'

/**
 * One end the hiker tapped: a coordinate, and later the POI it was near.
 *
 * `coord` is `[lon, lat]` on WGS84 - the order the graph artifact's own nodes
 * and geometry use, and GeoJSON's. It is the point AFTER being pulled onto
 * the line (`GraphPoint.at`), not the raw tap, so re-resolving it lands on
 * the trail rather than up to 150 ft off it.
 *
 * `poiId` is null tonight: the join to a shelter or viewpoint lands with the
 * finished-hike card (#980). The field exists now so that arrival is new data
 * in an existing slot rather than a migration.
 */
export interface DayHikeEnd {
  coord: [number, number]
  poiId: string | null
}

/**
 * An ordered run of ends the network connects.
 *
 * A day hike holds a LIST of these because #935's answer allows deliberate
 * gaps - a bushwhack between two stretches of maintained trail is between
 * segments, which keeps it distinguishable from a route that merely failed
 * to connect.
 */
export type DayHikeSegment = DayHikeEnd[]

/** One leg of the cached figures - lib/trailGraph.ts's RouteLeg, minus the
 *  trail_id the display never prints. */
export interface DayHikeLeg {
  name: string | null
  source: string | null
  blaze_color: string | null
  miles: number
}

/**
 * Cached display numbers, so a list can print "3.4 mi · A.T." without
 * loading the graph.
 *
 * A cache, and provenance says so: these were computed from the graph the
 * phone held when the hike was saved. A republished graph can route the same
 * ends differently, so anything re-resolving the segments should re-derive
 * these rather than trusting them past that point.
 */
export interface DayHikeFigures {
  miles: number
  legs: DayHikeLeg[]
  /**
   * The climb, or null when this walk has an edge nobody measured.
   *
   * ADDED 2026-08-27, on the maintainer's decision, and it is a stored-shape
   * change rather than a nicety. features/HIKE_PLANNING.md had it as an open
   * question: #1011 gave the network its climb without giving it to THIS
   * record, so the two surfaces that may only read the cache - the day-hike
   * list and the trailhead door - had miles and no ascent, and could not
   * price a walk at all. The storyboard's "fits my time" sort needs the same
   * field.
   *
   * NULL IS ALL OR NOTHING, exactly as {@link RouteClimb} is on the live
   * resolution: a walk with one unmeasured edge caches no climb, because
   * pricing that edge at zero ascent is a flat-ground claim about real ground
   * and pricing only the measured edges understates by the same amount with a
   * number attached. Both fail SHORT, which is the direction that gets
   * somebody caught by the dark.
   *
   * ABSENT IS NOT NULL, and the difference is why this is optional rather
   * than `RouteClimb | null`. A hike saved before this field existed has
   * `undefined` here - the app never knew - while `null` means the app asked
   * and the graph had no answer. A surface that showed "no climb data" for
   * the first would be reporting a limit of the artifact when the truth is a
   * limit of the record, and a re-resolution against a live graph fixes one
   * and not the other.
   */
  climb?: RouteClimb | null
}

export interface DayHike {
  /** Client-minted uuid (crypto.randomUUID), like a trip's - the id the sync
   *  exchange keys on. */
  id: string
  name: string
  /** YYYY-MM-DD, or null - an undated day hike is a first-class state. */
  date: string | null
  segments: DayHikeSegment[]
  figures: DayHikeFigures
  /** Whether the hiker asked to walk back to the first tap. */
  looped: boolean
  /** Planned ahead, or recorded from a walk - provenance that changes what a
   *  screen may say, exactly as a trip's `recorded` flag does. */
  recorded: 'planned' | 'walked'
}

export interface DayHikeStore {
  hikes: DayHike[]
  /** The day hike open on screen, or null. Held in this document rather than
   *  its own key so it cannot outlive the hike it names. */
  openId: string | null
}

export const EMPTY_DAY_HIKES: DayHikeStore = { hikes: [], openId: null }

/** plan.ts's own date shape - dates are stored the same way everywhere. */
const DATE_SHAPE = /^\d{4}-\d{2}-\d{2}$/

/**
 * An end, or null. Rebuilt field by field rather than passed through, which
 * is what enforces the CRITICAL rule above at the read boundary: an
 * `edgeIndex` (or anything else) smuggled onto a stored end does not survive
 * a load, so no later reader can come to depend on one being there.
 */
function validEnd(candidate: unknown): DayHikeEnd | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const end = candidate as Partial<DayHikeEnd>
  const coord = end.coord
  if (!Array.isArray(coord) || coord.length !== 2) return null
  const [lon, lat] = coord as unknown[]
  if (typeof lon !== 'number' || !Number.isFinite(lon)) return null
  if (typeof lat !== 'number' || !Number.isFinite(lat)) return null
  // No range check beyond finiteness: a coordinate off the planet re-resolves
  // against the graph and is refused there, which is the backstop a stored
  // NaN would sail past every distance comparison to avoid.
  return { coord: [lon, lat], poiId: typeof end.poiId === 'string' ? end.poiId : null }
}

/**
 * The segments, or null when they cannot be trusted.
 *
 * This is the one place junk costs the hike rather than the field, and the
 * reason is what the figures claim: a hike with an end silently dropped is a
 * DIFFERENT walk still wearing the old cached miles - a display outrunning
 * its source. Refusing the hike is honest; quietly rerouting it is not.
 */
function validSegments(candidate: unknown): DayHikeSegment[] | null {
  if (!Array.isArray(candidate) || candidate.length === 0) return null
  const segments: DayHikeSegment[] = []
  for (const entry of candidate) {
    if (!Array.isArray(entry) || entry.length === 0) return null
    const ends: DayHikeEnd[] = []
    for (const rawEnd of entry) {
      const end = validEnd(rawEnd)
      if (end === null) return null
      ends.push(end)
    }
    // A STRETCH OF ONE END IS NOT A STRETCH, and dropping it is the lesser of
    // two bad answers rather than an obvious one. `lib/dayHikeCard.ts` needs
    // two ends to route anything, so keeping a one-end stretch would leave the
    // whole hike permanently unresolvable - it would print its cache for ever
    // and no re-download could fix it, which is a worse outcome for the hiker
    // than losing a stretch that describes a place rather than a walk. The
    // builder cannot produce one (App.tsx filters on save), so this is about a
    // record arriving over sync from some other client.
    if (ends.length < 2) continue
    segments.push(ends)
  }
  if (segments.length === 0) return null
  return segments
}

/**
 * The figures, or null when no honest value exists to repair them to.
 *
 * `miles` gets no sanitised fallback on purpose: zero is a claim ("this walk
 * covers no ground"), not an absence, and this module cannot recompute the
 * cache without the graph. A hike whose miles are junk is dropped instead -
 * rare, and honest. The legs ARE sanitised: an empty breakdown prints as
 * nothing, which claims nothing.
 */
function validFigures(candidate: unknown): DayHikeFigures | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const figures = candidate as Partial<DayHikeFigures>
  const miles = figures.miles
  if (typeof miles !== 'number' || !Number.isFinite(miles) || miles < 0) return null

  const legs: DayHikeLeg[] = []
  if (Array.isArray(figures.legs)) {
    for (const entry of figures.legs) {
      if (typeof entry !== 'object' || entry === null) continue
      const leg = entry as Partial<DayHikeLeg>
      const legMiles = leg.miles
      if (typeof legMiles !== 'number' || !Number.isFinite(legMiles) || legMiles < 0) {
        continue
      }
      legs.push({
        name: typeof leg.name === 'string' ? leg.name : null,
        source: typeof leg.source === 'string' ? leg.source : null,
        blaze_color: typeof leg.blaze_color === 'string' ? leg.blaze_color : null,
        miles: legMiles,
      })
    }
  }

  const climb = validClimb(figures.climb)
  // The key is omitted rather than set to undefined, so that a record written
  // before the field existed round-trips as the same object it went in as -
  // which is what lets `'climb' in figures` mean "the app has looked".
  return climb === undefined ? { miles, legs } : { miles, legs, climb }
}

/**
 * A cached climb, distinguishing all three states.
 *
 * `undefined` - the field was never written (a hike saved before it existed,
 * or junk, which is treated the same way because the honest reading of junk
 * here is "this record does not tell us").
 * `null` - the app asked the graph and the graph could not price this walk.
 * A pair - the figures, when both halves are finite and non-negative.
 *
 * Sanitising rather than refusing, per this file's own rule: a climb carries
 * no invariant the rest of the record's arithmetic depends on, so a broken
 * one costs the field and never the hike.
 */
function validClimb(candidate: unknown): RouteClimb | null | undefined {
  if (candidate === undefined) return undefined
  if (candidate === null) return null
  if (typeof candidate !== 'object') return undefined
  const climb = candidate as Partial<RouteClimb>
  const { gainFt, lossFt } = climb
  if (typeof gainFt !== 'number' || !Number.isFinite(gainFt) || gainFt < 0)
    return undefined
  if (typeof lossFt !== 'number' || !Number.isFinite(lossFt) || lossFt < 0)
    return undefined
  return { gainFt, lossFt }
}

/**
 * A day hike, or null when what is junk is the hike itself.
 *
 * Only two things can cost the hike: an id that is not a non-empty string
 * (an identity cannot be sanitised - minting a replacement would fork the
 * hike on every load, and once synced, upload it as new for ever) and
 * segments or figures that cannot be trusted (see the helpers above).
 * Everything else is repaired: the weaker true value over the stronger
 * invented one, which is why junk `recorded` reads as 'planned' - the one
 * value that invents no walk nobody took.
 */
function validDayHike(candidate: unknown): DayHike | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const hike = candidate as Partial<DayHike>
  if (typeof hike.id !== 'string' || hike.id.length === 0) return null

  const segments = validSegments(hike.segments)
  if (segments === null) return null
  const figures = validFigures(hike.figures)
  if (figures === null) return null

  return {
    id: hike.id,
    name: typeof hike.name === 'string' ? hike.name : '',
    date: typeof hike.date === 'string' && DATE_SHAPE.test(hike.date) ? hike.date : null,
    segments,
    figures,
    looped: hike.looped === true,
    recorded: hike.recorded === 'walked' ? 'walked' : 'planned',
  }
}

/**
 * A store, or null only when this value cannot describe one at all.
 *
 * Inside a recognisable store, everything is sanitised or dropped per hike -
 * see the header. The openId gets trips.ts's repair with this store's decided
 * fallback: a pointer at a vanished hike becomes NULL rather than the first
 * hike, so nothing opens a walk the hiker did not choose.
 */
export function validateDayHikeStore(candidate: unknown): DayHikeStore | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const store = candidate as Partial<DayHikeStore>
  if (!Array.isArray(store.hikes)) return null

  const hikes: DayHike[] = []
  for (const entry of store.hikes) {
    const hike = validDayHike(entry)
    if (hike === null) continue
    hikes.push(hike)
  }

  const openId =
    typeof store.openId === 'string' && hikes.some((hike) => hike.id === store.openId)
      ? store.openId
      : null

  return { hikes, openId }
}

/** Re-validated on the way out rather than trusted, like every store here:
 *  this is a value an earlier build may have written. */
export async function loadDayHikes(): Promise<DayHikeStore> {
  const stored = await get(DAY_HIKES_KEY)
  if (stored === undefined || stored === null) return EMPTY_DAY_HIKES
  return validateDayHikeStore(stored) ?? EMPTY_DAY_HIKES
}

/** Every hike the stored document holds, readable or not - guarded so a junk
 *  document costs the record of one save, never the save itself.
 *
 *  Used ONLY where the hiker has asked to delete everything, which is an act
 *  rather than an inference: "forget every day hike" means the ones this
 *  build cannot read too, and leaving those behind would have them sync back
 *  afterwards. Every other caller wants `readableHikes` below - see it for
 *  what went wrong when the two were one function. */
function storedHikes(stored: unknown): DayHike[] {
  const hikes = (stored as Partial<DayHikeStore> | undefined)?.hikes
  return Array.isArray(hikes) ? hikes : []
}

/**
 * What this build could READ before the save, for the ledger's before/after.
 *
 * Validated, not raw, and the difference is a hike (#1040). `loadDayHikes`
 * drops a record this build cannot parse - deliberate, and documented - so
 * the store written back never contains it. Diffing that against the RAW
 * document made the validator's refusal look like the hiker's own delete:
 * the next ordinary save recorded a tombstone for it, and the tombstone
 * travelled, taking a walk off the account and every other device. A phone
 * on an older build destroyed what a newer one had made, everywhere, and
 * nobody performed a delete.
 *
 * `lib/dayHikeSyncState.ts` states the rule this restores: a delete travels
 * only as the hiker's OWN delete, recorded at the moment they perform it,
 * never inferred. "I could not read it" is an inference.
 *
 * What still degrades, said rather than left to be found: the unreadable
 * record is not written back to this device either, so it lives only on the
 * account until a build that understands it comes back. That is the same
 * honest skew `mergeServerDayHikes` already applies to a row from a newer
 * build - dropped rather than rendered - and it is survivable in a way a
 * tombstone is not.
 */
function readableHikes(stored: unknown): DayHike[] {
  return validateDayHikeStore(stored)?.hikes ?? []
}

export async function saveDayHikes(store: DayHikeStore): Promise<void> {
  // Read before write, so the ledger learns what the hiker just did - the
  // same one-extra-read saveTrips pays, buying the same rule: a delete
  // travels only as the hiker's OWN delete, recorded at the moment they
  // perform it, never inferred from a store that came back empty. See
  // lib/dayHikeSyncState.ts.
  const before = await get(DAY_HIKES_KEY)
  await set(DAY_HIKES_KEY, store)
  await recordDayHikeEdits(readableHikes(before), store.hikes)
}

/**
 * Write what the ACCOUNT says, without recording it as a local edit.
 *
 * `saveDayHikes`' opposite number, and the reason there are two functions
 * rather than a flag - `adoptTrips` has the long version: adopting through
 * the marking path would upload back everything the server just sent, for
 * ever, looking from the outside exactly like a sync that works.
 */
export async function adoptDayHikes(store: DayHikeStore): Promise<void> {
  await set(DAY_HIKES_KEY, store)
}

/** Forget every day hike. Recorded as the hiker deleting each of them,
 *  because that is what it is - clearTrips makes the same call, and the
 *  alternative is the inference features/ACCOUNT_SYNC.md forbids. */
export async function clearDayHikes(): Promise<void> {
  const before = await get(DAY_HIKES_KEY)
  await del(DAY_HIKES_KEY)
  await recordDayHikeEdits(storedHikes(before), [])
}
