// More than one plan, kept (#787).
//
// THE BUG THIS CLOSES, in the maintainer's own words: the Plan tab kept
// exactly one plan and the next trip overwrote the last. `savePlan()` wrote
// straight over `ourhike:plan`, which is right for a hiker with one trip
// ahead of them and wrong for the hiker this whole group exists for - a
// section hiker whose spring trip destroyed their autumn one, with nothing
// anywhere recording that the two were pieces of one long walk.
//
// THE SHAPE. A TRIP is a saved plan with an identity: SEGMENTS.md's Segment,
// holding the day-Segments the timeline already draws. `HikePlan` is nested
// rather than spread, so the plan model, its validator and every edit in
// plan.ts are untouched by this file - a trip is a plan with a name on it,
// and nothing about the arithmetic changes because it acquired one.
//
// ONE DOCUMENT, ONE KEY. The whole store - every trip and which one is open
// - lives under a single key, the way lib/outbox.ts holds its whole queue
// under `ourhike:outbox`. The alternative (a key per trip, plus a key for
// the pointer) buys nothing here and costs a consistency problem: two writes
// that can half-land, and a pointer that can outlive the trip it names. A
// full thru-hike plan is ~24 KB (HIKE_PLANNING.md Q6) and a hiker has a
// handful of trips, so the whole document is small enough to write at once.
//
// THE PLAN ALREADY ON THE PHONE. `ourhike:plan` is read once, migrated, and
// then never read again - see `loadTrips` below. The legacy key is
// deliberately NOT deleted: the migration writes the new document first, so
// nothing re-reads the old one afterwards, and leaving ~24 KB in place costs
// nothing against irreversibly destroying the only copy of somebody's plan
// if this code is wrong.

import { del, get, set } from 'idb-keyval'
import { stopLabel } from './planDisplay'
import { loadPlan, validatePlan, type HikePlan } from './plan'

export const TRIPS_KEY = 'ourhike:trips'

/** A saved plan with an identity. */
export interface Trip {
  id: string
  /**
   * What the hiker calls it. Written for them from the route's own ends when
   * the trip is saved (`tripName`), and editable - nobody should have to
   * name a thing before they are allowed to keep it.
   */
  name: string
  plan: HikePlan
}

export interface TripStore {
  trips: Trip[]
  /** The trip the Plan tab is showing, or null when none is open. Held here
   *  rather than in its own key so it cannot outlive the trip it names. */
  openId: string | null
}

export const EMPTY_STORE: TripStore = { trips: [], openId: null }

/**
 * A trip's default name, from the route's own ends - "Damascus → Old Orchard
 * Shelter". Uses the timeline's own `stopLabel`, so a trip and the rows
 * inside it cannot call the same place two different things, and an unnamed
 * end reads as its mile marker rather than as a blank.
 */
export function tripName(plan: HikePlan): string {
  if (plan.stops.length < 2) return 'Untitled trip'
  return `${stopLabel(plan.stops[0])} → ${stopLabel(plan.stops[plan.stops.length - 1])}`
}

/**
 * A store, or null if this value cannot describe one. Refused rather than
 * corrected, exactly like `validatePlan()` and `plannedHike()`: this
 * validates values an earlier build may have written, and a shape that
 * cannot carry the invariants must not reach the code that assumes them.
 *
 * A trip whose PLAN does not validate is dropped rather than taking the
 * whole store down with it. That asymmetry is deliberate: one unreadable
 * trip is a lost trip, while refusing the document loses every trip the
 * hiker has - and this store is the thing standing between a section hiker
 * and years of their own record.
 */
export function validateTripStore(candidate: unknown): TripStore | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const store = candidate as Partial<TripStore>
  if (!Array.isArray(store.trips)) return null
  if (store.openId !== null && typeof store.openId !== 'string') return null

  const trips: Trip[] = []
  for (const entry of store.trips) {
    if (typeof entry !== 'object' || entry === null) continue
    const trip = entry as Partial<Trip>
    if (typeof trip.id !== 'string' || trip.id.length === 0) continue
    if (typeof trip.name !== 'string') continue
    const plan = validatePlan(trip.plan)
    if (plan === null) continue
    trips.push({ id: trip.id, name: trip.name, plan })
  }

  // A pointer at a trip that did not survive is not a pointer. Falling back
  // to the first trip rather than to null keeps the Plan tab showing
  // something a hiker recognises instead of an empty state that reads as
  // "your plans are gone".
  const openId =
    store.openId !== null && trips.some((trip) => trip.id === store.openId)
      ? store.openId
      : (trips[0]?.id ?? null)

  return { trips, openId }
}

/**
 * The store, migrating the single-plan key on first read.
 *
 * The migration is a deliberate, tested step rather than something left to
 * the validator, because `validatePlan()` refuses shapes it does not
 * recognise - a `HikePlan` handed to `validateTripStore()` is not a store
 * and would read as "no trips", silently, on the phone of every hiker who
 * had one.
 */
export async function loadTrips(): Promise<TripStore> {
  const stored = await get(TRIPS_KEY)
  if (stored !== undefined && stored !== null) {
    return validateTripStore(stored) ?? EMPTY_STORE
  }

  const legacy = await loadPlan()
  if (legacy === null) return EMPTY_STORE

  const trip: Trip = { id: crypto.randomUUID(), name: tripName(legacy), plan: legacy }
  const migrated: TripStore = { trips: [trip], openId: trip.id }
  await saveTrips(migrated)
  return migrated
}

export async function saveTrips(store: TripStore): Promise<void> {
  await set(TRIPS_KEY, store)
}

/** Forget every trip. A first-class action like `clearPlan()` was, and for
 *  its reason: abandoning plans must never mean clearing the app's data. */
export async function clearTrips(): Promise<void> {
  await del(TRIPS_KEY)
}

// ---------------------------------------------------------------------------
// Edits. Each returns a new store and leaves the argument alone, matching
// plan.ts's own convention so the two can be composed without anybody having
// to remember which of them mutates.

/** Keep a plan as a new trip, and open it. */
export function addTrip(store: TripStore, plan: HikePlan, name?: string): TripStore {
  const trip: Trip = {
    id: crypto.randomUUID(),
    name: name === undefined || name === '' ? tripName(plan) : name,
    plan,
  }
  return { trips: [...store.trips, trip], openId: trip.id }
}

/** Write a plan back to the trip it came from. Unknown id changes nothing -
 *  an edit to a trip that is no longer there must not resurrect it. */
export function updateTrip(store: TripStore, id: string, plan: HikePlan): TripStore {
  if (!store.trips.some((trip) => trip.id === id)) return store
  return {
    ...store,
    trips: store.trips.map((trip) => (trip.id === id ? { ...trip, plan } : trip)),
  }
}

/**
 * Rename a trip. An empty name is not stored as an empty name: it falls back
 * to the route's own ends, so a trip cleared to blank comes back as
 * "Damascus → Old Orchard Shelter" rather than as an unidentifiable row.
 */
export function renameTrip(store: TripStore, id: string, name: string): TripStore {
  return {
    ...store,
    trips: store.trips.map((trip) =>
      trip.id === id
        ? { ...trip, name: name.trim() === '' ? tripName(trip.plan) : name.trim() }
        : trip,
    ),
  }
}

/** Forget one trip. Removing the open one opens whatever is left, so the
 *  Plan tab never lands on a pointer to nothing. */
export function removeTrip(store: TripStore, id: string): TripStore {
  const trips = store.trips.filter((trip) => trip.id !== id)
  if (trips.length === store.trips.length) return store
  return {
    trips,
    openId: store.openId === id ? (trips[0]?.id ?? null) : store.openId,
  }
}

/** Show this trip on the Plan tab. Unknown id changes nothing. */
export function openTrip(store: TripStore, id: string): TripStore {
  if (!store.trips.some((trip) => trip.id === id)) return store
  return { ...store, openId: id }
}

/** The trip the Plan tab is showing, or null. */
export function openTripOf(store: TripStore): Trip | null {
  if (store.openId === null) return null
  return store.trips.find((trip) => trip.id === store.openId) ?? null
}
