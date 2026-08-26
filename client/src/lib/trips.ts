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
import { validateHike, type Hike } from './hikes'
import { validateTripGroup, type TripGroup } from './tripGroups'
import { stopLabel } from './planDisplay'
import { loadPlan, validatePlan, type HikePlan } from './plan'
import { recordTripEdits } from './tripSyncState'

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
  /**
   * This trip was RECORDED from memory rather than planned (#789) - a
   * stretch the hiker walked before they had the app, or without planning
   * it. Every day in it is already walked; there are no days in the sense
   * the timeline means, only the boundaries the hiker could remember.
   *
   * The flag exists because provenance changes what a screen may say. A
   * recorded stretch of 300 miles is not a claim that anybody walked 300
   * miles in a day, and nothing may print it as one - so readers that
   * would show per-day figures show the stretch instead.
   */
  recorded?: boolean
}

export interface TripStore {
  trips: Trip[]
  /** The trip the Plan tab is showing, or null when none is open. Held here
   *  rather than in its own key so it cannot outlive the trip it names. */
  openId: string | null
  /**
   * The hikes those trips are grouped into (#788). In this same document
   * rather than a key of their own, for the reason the document exists: a
   * parent in one key and its children in another is two writes that can
   * half-land, and a `tripIds` list that can outlive the trips it names.
   *
   * Absent on a store written by the #787 build, which reads as no hikes -
   * the trips are all still there, ungrouped, which is exactly true.
   */
  hikes: Hike[]
  /**
   * The hiker's own buckets (#800) - "every Sunday", "with Dad". Same
   * document, same reasoning as `hikes`.
   *
   * A trip can be in ANY NUMBER of these, which is what separates them from
   * hikes: a hike is where a trip sits on the trail and there is one such
   * place, a group is how the hiker thinks about it and there can be
   * several. See lib/tripGroups.ts.
   */
  groups: TripGroup[]
}

export const EMPTY_STORE: TripStore = {
  trips: [],
  openId: null,
  hikes: [],
  groups: [],
}

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
    trips.push({
      id: trip.id,
      name: trip.name,
      plan,
      ...(trip.recorded === true ? { recorded: true as const } : {}),
    })
  }

  // A pointer at a trip that did not survive is not a pointer. Falling back
  // to the first trip rather than to null keeps the Plan tab showing
  // something a hiker recognises instead of an empty state that reads as
  // "your plans are gone".
  const openId =
    store.openId !== null && trips.some((trip) => trip.id === store.openId)
      ? store.openId
      : (trips[0]?.id ?? null)

  // Absent is not invalid: a store written before hikes existed has none,
  // and its trips are unaffected. One unreadable hike is dropped for the
  // same reason one unreadable trip is - losing the grouping is survivable,
  // losing the record is not. A hike's `tripIds` are pruned to trips that
  // actually survived, so no list can name a trip that is gone.
  const live = new Set(trips.map((trip) => trip.id))
  const hikes: Hike[] = []
  if (Array.isArray(store.hikes)) {
    for (const entry of store.hikes) {
      const hike = validateHike(entry)
      if (hike === null) continue
      hikes.push({ ...hike, tripIds: hike.tripIds.filter((id) => live.has(id)) })
    }
  }

  // Groups get the same treatment for the same reasons: absent is not
  // invalid, one unreadable group is dropped rather than the store, and
  // every list is pruned to trips that actually survived.
  const groups: TripGroup[] = []
  if (Array.isArray(store.groups)) {
    for (const entry of store.groups) {
      const group = validateTripGroup(entry)
      if (group === null) continue
      groups.push({ ...group, tripIds: group.tripIds.filter((id) => live.has(id)) })
    }
  }

  return { trips, openId, hikes, groups }
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
  const migrated: TripStore = { trips: [trip], openId: trip.id, hikes: [], groups: [] }
  await saveTrips(migrated)
  return migrated
}

export async function saveTrips(store: TripStore): Promise<void> {
  // Read before write, so the ledger learns what the hiker just did (#892).
  // One extra IndexedDB read per save, which buys the thing
  // features/ACCOUNT_SYNC.md calls a rule: a delete travels only as the
  // hiker's OWN delete. Recorded here, at the moment they perform it, it
  // never has to be inferred from a store that came back empty - see
  // lib/tripSyncState.ts on why that distinction is the whole design.
  //
  // VALIDATED, NOT RAW (#1040). `loadTrips` drops a trip this build cannot
  // parse, so the store written back never holds it - and diffing that
  // against the raw document made the validator's refusal look like a
  // delete the hiker performed. The tombstone travelled, and a phone on an
  // older build took somebody's plan off the account and every other
  // device. `validateTripStore` is what this build could actually read, and
  // that is the only honest thing to compare against.
  const before = validateTripStore(await get(TRIPS_KEY))
  await set(TRIPS_KEY, store)
  await recordTripEdits(before?.trips ?? [], store.trips)
}

/**
 * Write what the ACCOUNT says, without recording it as a local edit (#892).
 *
 * `saveTrips`' opposite number, and the reason there are two functions
 * rather than a flag. Adopting through `saveTrips` would mark every trip the
 * server just sent as changed on this device, so the next sync would upload
 * them all straight back - for ever, and looking from the outside exactly
 * like a sync that works.
 *
 * lib/preferences.ts' `adoptPreferences` is the same split one grain up.
 */
export async function adoptTrips(store: TripStore): Promise<void> {
  await set(TRIPS_KEY, store)
}

/** Forget every trip. A first-class action like `clearPlan()` was, and for
 *  its reason: abandoning plans must never mean clearing the app's data.
 *
 *  Recorded as the hiker deleting every one of them (#892), because that is
 *  what it is. The alternative - dropping the key and letting the next sync
 *  work it out - is exactly the inference features/ACCOUNT_SYNC.md forbids,
 *  and here it would run the other way: the account would hand every trip
 *  straight back. */
export async function clearTrips(): Promise<void> {
  const before = (await get(TRIPS_KEY)) as TripStore | undefined
  await del(TRIPS_KEY)
  await recordTripEdits(before?.trips ?? [], [])
}

// ---------------------------------------------------------------------------
// Edits. Each returns a new store and leaves the argument alone, matching
// plan.ts's own convention so the two can be composed without anybody having
// to remember which of them mutates.

/** Keep a plan as a new trip, and open it. */
export function addTrip(
  store: TripStore,
  plan: HikePlan,
  name?: string,
  recorded = false,
): TripStore {
  const trip: Trip = {
    id: crypto.randomUUID(),
    name: name === undefined || name === '' ? tripName(plan) : name,
    plan,
    ...(recorded ? { recorded: true as const } : {}),
  }
  return { ...store, trips: [...store.trips, trip], openId: trip.id }
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
    ...store,
    trips,
    openId: store.openId === id ? (trips[0]?.id ?? null) : store.openId,
    // A hike that still named the deleted trip would count miles from a
    // plan nobody can open. Groups, the same (#800).
    hikes: store.hikes.map((hike) =>
      hike.tripIds.includes(id)
        ? { ...hike, tripIds: hike.tripIds.filter((tripId) => tripId !== id) }
        : hike,
    ),
    groups: store.groups.map((group) =>
      group.tripIds.includes(id)
        ? { ...group, tripIds: group.tripIds.filter((tripId) => tripId !== id) }
        : group,
    ),
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

// ---------------------------------------------------------------------------
// Hikes over those trips (#788). Same convention: a new store out, the
// argument untouched.

/** Keep a hike. Trips it names stay where they are - a trip belongs to at
 *  most one hike, so any it claims are released from whichever hike had
 *  them, rather than being counted twice in two roll-ups. */
export function addHike(store: TripStore, hike: Hike): TripStore {
  const claimed = new Set(hike.tripIds)
  return {
    ...store,
    hikes: [
      ...store.hikes.map((existing) => ({
        ...existing,
        tripIds: existing.tripIds.filter((id) => !claimed.has(id)),
      })),
      hike,
    ],
  }
}

/** Put a trip in a hike, taking it out of any other. */
export function assignTrip(store: TripStore, hikeId: string, tripId: string): TripStore {
  if (!store.hikes.some((hike) => hike.id === hikeId)) return store
  if (!store.trips.some((trip) => trip.id === tripId)) return store
  return {
    ...store,
    hikes: store.hikes.map((hike) => {
      const without = hike.tripIds.filter((id) => id !== tripId)
      return hike.id === hikeId
        ? { ...hike, tripIds: [...without, tripId] }
        : { ...hike, tripIds: without }
    }),
  }
}

/** Take a trip out of whatever hike holds it. The trip itself is untouched:
 *  ungrouping is not deleting, and a hiker who dissolves a hike still has
 *  every trip they walked. */
export function unassignTrip(store: TripStore, tripId: string): TripStore {
  return {
    ...store,
    hikes: store.hikes.map((hike) => ({
      ...hike,
      tripIds: hike.tripIds.filter((id) => id !== tripId),
    })),
  }
}

/** Forget a hike, keeping its trips. Same reason as above. */
export function removeHike(store: TripStore, hikeId: string): TripStore {
  return { ...store, hikes: store.hikes.filter((hike) => hike.id !== hikeId) }
}

/**
 * A new, empty group (#800).
 *
 * Empty rather than "every trip you have": a bucket the hiker names is a
 * bucket the hiker fills, and pre-filling one would make "every Sunday"
 * mean "everything" until they emptied it again.
 */
export function addGroup(store: TripStore, name: string): TripStore {
  return {
    ...store,
    groups: [...store.groups, { id: crypto.randomUUID(), name, tripIds: [] }],
  }
}

/**
 * Put a trip in a group, leaving every other group it is in alone.
 *
 * The one line that separates this from `assignTrip`, which moves a trip
 * BETWEEN hikes because a trip has one place on the trail. A trip has as
 * many ways of being thought about as the hiker has - "the entire AT" and
 * "my section this year" are both true of the same walk.
 */
export function addToGroup(store: TripStore, groupId: string, tripId: string): TripStore {
  if (!store.trips.some((trip) => trip.id === tripId)) return store
  return {
    ...store,
    groups: store.groups.map((group) =>
      group.id === groupId && !group.tripIds.includes(tripId)
        ? { ...group, tripIds: [...group.tripIds, tripId] }
        : group,
    ),
  }
}

export function removeFromGroup(
  store: TripStore,
  groupId: string,
  tripId: string,
): TripStore {
  return {
    ...store,
    groups: store.groups.map((group) =>
      group.id === groupId
        ? { ...group, tripIds: group.tripIds.filter((id) => id !== tripId) }
        : group,
    ),
  }
}

/** Forget a group, keeping every trip in it - the same rule `removeHike`
 *  follows, because a bucket is a way of looking at trips and throwing away
 *  the bucket must never throw away the walking. */
export function removeGroup(store: TripStore, groupId: string): TripStore {
  return { ...store, groups: store.groups.filter((group) => group.id !== groupId) }
}

/** Rename a group; an empty name is refused rather than stored - a group
 *  has no route to fall back on for a name the way a trip does. */
export function renameGroup(store: TripStore, groupId: string, name: string): TripStore {
  if (name.trim() === '') return store
  return {
    ...store,
    groups: store.groups.map((group) =>
      group.id === groupId ? { ...group, name: name.trim() } : group,
    ),
  }
}

/** Rename a hike; an empty name is refused rather than stored, since a hike
 *  has no ends-derived fallback the way a trip does. */
export function renameHike(store: TripStore, hikeId: string, name: string): TripStore {
  if (name.trim() === '') return store
  return {
    ...store,
    hikes: store.hikes.map((hike) =>
      hike.id === hikeId ? { ...hike, name: name.trim() } : hike,
    ),
  }
}
