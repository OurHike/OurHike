// Following a retired POI id to the place that stands for it today (#831).
//
// features/POI_IDENTITY.md §4 asks for "a resolver, in one place, used by the
// backend's serialisers and the client rather than implemented twice". This is
// the client's one place. `pipeline/lib/poi_identity.resolve` is the other, and
// they are held to each other by `poiIdentity.contract.test.ts` against shared
// fixtures rather than by anybody remembering.
//
// WHY "ONE RESOLVER" CANNOT MEAN ONE IMPLEMENTATION, DECIDED RATHER THAN INHERITED
//
// #831 asks for this to be settled explicitly. The repository already states
// the constraint in its own words - `backend/tests/test_conditions_publisher_
// contract.py`: "the pipeline is not importable from here (different package,
// its own dependencies)" - and the client is a third runtime again. Across
// Python and TypeScript with no shared package the achievable version is **one
// implementation per runtime, each in exactly one file, held together by a
// contract test over shared fixtures**. That is the pattern three tests in
// `backend/tests/` already use, so this inherits a practice rather than
// inventing one. §4's sentence is amended to say so.
//
// THE TWO RESOLVERS SEE DIFFERENT THINGS, WHICH IS THE PART WORTH READING
//
// The pipeline resolves against the whole ledger - 4,251 rows, live and
// retired. A phone never gets that file: it gets `retired_poi.geojson`, the 93
// retired rows, because the live half is already on the phone as
// `poi_*.geojson` and shipping both would be shipping the same 4,158 places
// twice.
//
// So the tombstones alone cannot tell "live" from "an id this project has never
// heard of", and those are different answers - the pipeline returns the id for
// the first and null for the second, and inventing a target for an id we cannot
// vouch for "would be worse than saying so". `resolvePoiId` therefore takes an
// `isLive` predicate: the caller holds the live set, and passing it in is what
// makes this function answer exactly what the Python one answers. The contract
// test is over that equivalence and not over a looser one.

import type { PoiType } from './config'

/** One published tombstone. Mirrors `lib/poi_identity.TOMBSTONE_PROPERTIES`.
 *
 *  `name` and `supersededBy` are optional because the artifact omits them
 *  rather than nulling them, and absent is a real state in both cases:
 *  nobody named the place, and nothing took its place. `source` is not
 *  optional - the card's sentence is built from it. */
export interface Tombstone {
  id: string
  poiType: string
  source: string
  /** The release that retired it, `YYYY-MM-DD`. */
  retired: string
  /** Where the place WAS. Rides in the artifact's geometry rather than its
   *  properties, which is what makes the file a FeatureCollection a map can
   *  draw. The design lists it among a tombstone's fields for the card's
   *  sake — "a hiker's photos of a decommissioned shelter keep a card to
   *  live on" is a card that can say where. */
  lon: number
  lat: number
  name?: string
  supersededBy?: string
}

/** Tombstones by id — what a lookup needs, and what IndexedDB stores. */
export type Tombstones = Record<string, Tombstone>

export const NO_TOMBSTONES: Tombstones = {}

/**
 * Read `retired_poi.geojson` into a lookup, skipping anything malformed.
 *
 * Lenient on purpose, and in one direction only: a feature missing `id`,
 * `source`, `poi_type` or `retired` is dropped rather than throwing, because
 * this artifact is a courtesy on top of a working map. A phone that fails to
 * parse it should lose the tombstone cards, not the download — everything
 * else in that transaction is the trail and its waypoints.
 *
 * It never invents. A dropped feature is one id that renders nothing, which
 * is exactly what happens today for every retired id, so the failure mode of
 * being strict here is strictly worse than the failure mode of being lenient.
 */
export function parseTombstones(parsed: unknown): Tombstones {
  if (!parsed || typeof parsed !== 'object') return NO_TOMBSTONES
  const features = (parsed as { features?: unknown }).features
  if (!Array.isArray(features)) return NO_TOMBSTONES

  const out: Tombstones = {}
  for (const feature of features) {
    const properties = (feature as { properties?: unknown })?.properties
    if (!properties || typeof properties !== 'object') continue
    const row = properties as Record<string, unknown>
    const {
      id,
      poi_type: poiType,
      source,
      retired,
      name,
      superseded_by: supersededBy,
    } = row
    if (typeof id !== 'string' || id === '') continue
    if (
      typeof poiType !== 'string' ||
      typeof source !== 'string' ||
      typeof retired !== 'string'
    ) {
      continue
    }
    const coordinates = (feature as { geometry?: { coordinates?: unknown } })?.geometry
      ?.coordinates
    if (!Array.isArray(coordinates)) continue
    const [lon, lat] = coordinates as unknown[]
    if (typeof lon !== 'number' || typeof lat !== 'number') continue
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue
    out[id] = {
      id,
      poiType,
      source,
      retired,
      lon,
      lat,
      ...(typeof name === 'string' && name !== '' ? { name } : {}),
      ...(typeof supersededBy === 'string' && supersededBy !== ''
        ? { supersededBy }
        : {}),
    }
  }
  return out
}

/**
 * Follow `superseded_by` from any id ever published to the id that stands for
 * that place today. Null when nothing does.
 *
 * The same three answers `pipeline/lib/poi_identity.resolve` gives, and the
 * third is the one worth stating:
 *
 *   - a live id resolves to itself;
 *   - a retired id with a successor resolves to whatever that points at,
 *     transitively — a place merged twice over two refreshes still arrives
 *     somewhere;
 *   - a retired id WITHOUT a successor resolves to null, which is the honest
 *     answer and not a failure. It means "this place is gone and nothing took
 *     its place", which is exactly what the tombstone card says. Returning a
 *     nearby id instead would be the confident wrong merge that
 *     features/POI_IDENTITY.md tunes every threshold away from.
 *
 * An id neither live nor retired is also null: a reference from somewhere this
 * project cannot vouch for.
 *
 * The seen-set is not defensive padding. `reconcile_poi_identity.py` cannot
 * write a cycle, but a hand-written `merged_into` override is a file a person
 * edits, and "the app froze on a shelter" is a bad way to learn two rows point
 * at each other.
 */
export function resolvePoiId(
  tombstones: Tombstones,
  poiId: string,
  isLive: (id: string) => boolean,
): string | null {
  const seen = new Set<string>()
  let current = poiId
  for (;;) {
    const stone = tombstones[current]
    if (stone === undefined) return isLive(current) ? current : null
    const successor = stone.supersededBy
    if (successor === undefined || seen.has(successor)) return null
    seen.add(current)
    current = successor
  }
}

/** The tombstone for an id, or undefined when the id was never retired. */
export function tombstoneFor(
  tombstones: Tombstones,
  poiId: string,
): Tombstone | undefined {
  return tombstones[poiId]
}

/** A live POI type this tombstone can be drawn as, or undefined.
 *
 *  The artifact's `poi_type` is the pipeline's vocabulary and the client's
 *  `PoiType` is a subset of it. Narrowed here rather than cast, so a type the
 *  client does not draw comes back undefined and the card falls back to a
 *  neutral treatment instead of a React key that matches no icon. */
export function drawableType(
  tombstone: Tombstone,
  types: readonly string[],
): PoiType | undefined {
  return types.includes(tombstone.poiType) ? (tombstone.poiType as PoiType) : undefined
}

/**
 * What IndexedDB gave back, made usable — or nothing.
 *
 * The same posture `storedClubSections` and `storedHighlights` take, and for
 * the same reason: what is in the store was written by whatever version of
 * this app was installed then, and a shape that has since changed must read
 * as "no tombstones" rather than as a card built from undefined.
 *
 * Deliberately re-validates rather than trusting the write. `parseTombstones`
 * is the gate on the way in; this is the gate on the way out, and they are not
 * redundant across an upgrade — the write happened under the old code.
 */
export function storedTombstones(stored: unknown): Tombstones {
  if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return NO_TOMBSTONES
  const out: Tombstones = {}
  for (const [id, value] of Object.entries(stored as Record<string, unknown>)) {
    if (!value || typeof value !== 'object') continue
    const row = value as Partial<Tombstone>
    if (typeof row.poiType !== 'string') continue
    if (typeof row.source !== 'string' || typeof row.retired !== 'string') continue
    if (typeof row.lon !== 'number' || typeof row.lat !== 'number') continue
    out[id] = {
      id,
      poiType: row.poiType,
      source: row.source,
      retired: row.retired,
      lon: row.lon,
      lat: row.lat,
      ...(typeof row.name === 'string' ? { name: row.name } : {}),
      ...(typeof row.supersededBy === 'string' ? { supersededBy: row.supersededBy } : {}),
    }
  }
  return out
}
