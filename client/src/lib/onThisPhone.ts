// What vector trail data is actually on this phone, measured off the store
// itself (#1103).
//
// The sheets have a catalog with published byte counts; the trail data has
// nothing of the kind - artifacts of unannounced size that arrive on
// their own with signal, and until now their whole account was the word
// "Getting trail data". This module is the detailed half of the answer: it
// reads what lib/trailData.ts and lib/nearbyTrailData.ts actually stored and
// reports it as it is - a measured byte count where the store holds bytes, a
// count where it holds records, presence alone where it holds neither. No
// figure here is ever an estimate: absent stays "not here yet", never a size
// somebody expects it to be.
//
// Its own module rather than a function on either store, because it reads
// BOTH and the two must not import each other (nearbyTrailData already
// imports trailData's hash; a return import is a cycle).

import { get } from 'idb-keyval'
import { ELEVATION_STORE_KEY, POIS_KEY, TRAILS_BLOB_KEY } from './trailData'
import { NEARBY_TRAILS_STORE_KEY, NETWORK_OVERVIEW_STORE_KEY } from './nearbyTrailData'
import { storedGraphBytes } from './trailGraphStore'

export interface TrailDataAsset {
  id:
    | 'trail-line'
    | 'waypoints'
    | 'elevation'
    | 'nearby-trails'
    | 'network-overview'
    | 'day-hike-routing'
  /** Measured bytes of what is stored, or null where the stored shape has
   *  no byte size to measure (a parsed record is not its wire bytes, and
   *  inventing one would be a figure nobody stands behind). */
  bytes: number | null
  /** Measured record count, or null where counting is not the shape. */
  count: number | null
  present: boolean
}

async function read(key: string): Promise<unknown> {
  try {
    return await get(key)
  } catch {
    // An unreadable store answers like an empty one: the list says "not
    // here yet", which is also what the map can draw from it.
    return undefined
  }
}

/**
 * Every trail-data artifact, present or not - the caller renders the whole
 * list so an absence is a stated fact rather than a missing row. Read fresh
 * each call: this is for the downloads window, which mounts at exactly the
 * moment the answer is worth having.
 */
export async function storedTrailData(): Promise<TrailDataAsset[]> {
  const [trails, pois, elevation, nearby, overview, graph] = await Promise.all([
    read(TRAILS_BLOB_KEY),
    read(POIS_KEY),
    read(ELEVATION_STORE_KEY),
    read(NEARBY_TRAILS_STORE_KEY),
    read(NETWORK_OVERVIEW_STORE_KEY),
    storedGraphBytes(),
  ])

  // The four graph artifacts as ONE row, because they are one capability to a
  // hiker: either day hikes work without a signal or they do not, and a row
  // per file would be four numbers answering a question nobody asked. Summed
  // rather than counted for the same reason - what a hiker wants to know is
  // what it is costing them.
  const graphBytes = Object.values(graph).reduce((sum, bytes) => sum + bytes, 0)

  // Both nearby-network artifacts are kept under one shape by
  // lib/nearbyTrailData.ts (`{ bytes: Blob, hash: string }`), so one reader
  // serves both rather than two that have to be kept agreeing.
  const storedBytes = (record: unknown): number | null =>
    record !== undefined &&
    record !== null &&
    (record as { bytes?: unknown }).bytes instanceof Blob
      ? (record as { bytes: Blob }).bytes.size
      : null

  const nearbyBytes = storedBytes(nearby)
  const overviewBytes = storedBytes(overview)

  const elevationSamples =
    elevation !== undefined &&
    elevation !== null &&
    Array.isArray((elevation as { samples?: unknown }).samples)
      ? ((elevation as { samples: unknown[] }).samples.length as number)
      : null

  return [
    {
      id: 'trail-line',
      bytes: trails instanceof Blob ? trails.size : null,
      count: null,
      present: trails instanceof Blob,
    },
    {
      id: 'waypoints',
      bytes: null,
      count: Array.isArray(pois) ? pois.length : null,
      present: Array.isArray(pois) && pois.length > 0,
    },
    {
      id: 'elevation',
      bytes: null,
      count: elevationSamples,
      present: elevation !== undefined && elevation !== null,
    },
    {
      id: 'day-hike-routing',
      bytes: graphBytes > 0 ? graphBytes : null,
      count: null,
      present: graphBytes > 0,
    },
    {
      id: 'nearby-trails',
      bytes: nearbyBytes,
      count: null,
      present: nearbyBytes !== null,
    },
    // The corridor-view sketch of that same network (#1135). A SEPARATE ROW
    // rather than folded into the one above, which is the opposite call from
    // the four graph files and made on the same test: is this one capability
    // to a hiker, or two? The graph files are one - day hikes work offline or
    // they do not. These two are not. They draw at different zooms, and losing
    // only the sketch means an offline launch opens on an A.T.-only map that
    // the last online launch did not show, with the detailed network arriving
    // as you zoom in. That is a distinguishable thing to be missing, so it
    // gets a line that can say so.
    //
    // It was in no row at all until now, which is the defect: this window
    // claims to be what is on the phone, and an artifact holding bytes while
    // appearing nowhere is the one answer it must not give.
    {
      id: 'network-overview',
      bytes: overviewBytes,
      count: null,
      present: overviewBytes !== null,
    },
  ]
}
