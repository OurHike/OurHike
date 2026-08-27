// What vector trail data is actually on this phone, measured off the store
// itself (#1103).
//
// The sheets have a catalog with published byte counts; the trail data has
// nothing of the kind - four artifacts of unannounced size that arrive on
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
import { NEARBY_TRAILS_STORE_KEY } from './nearbyTrailData'

export interface TrailDataAsset {
  id: 'trail-line' | 'waypoints' | 'elevation' | 'nearby-trails'
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
  const [trails, pois, elevation, nearby] = await Promise.all([
    read(TRAILS_BLOB_KEY),
    read(POIS_KEY),
    read(ELEVATION_STORE_KEY),
    read(NEARBY_TRAILS_STORE_KEY),
  ])

  const nearbyBytes =
    nearby !== undefined &&
    nearby !== null &&
    (nearby as { bytes?: unknown }).bytes instanceof Blob
      ? (nearby as { bytes: Blob }).bytes.size
      : null

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
      id: 'nearby-trails',
      bytes: nearbyBytes,
      count: null,
      present: nearbyBytes !== null,
    },
  ]
}
