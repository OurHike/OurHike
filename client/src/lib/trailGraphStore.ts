// Keeping the junction graph on the phone (#1050).
//
// THE GAP THIS CLOSES, IN ONE SENTENCE: a hiker who downloaded the corridor at
// home, drove to Harriman and opened the app at the trailhead with no signal
// got a day-hike builder that refused every tap - because `lib/useTrailData.ts`
// fetched the graph over the network on every launch and nothing wrote it
// anywhere.
//
// The service worker could not help: it precaches the bundle, the glyphs and
// the UI fonts, and these are runtime JSON fetches from a different origin.
//
// ALL THREE ARTIFACTS, WHICH IS THE MAINTAINER'S DECISION OF 2026-08-27 AND
// NOT THE OBVIOUS ONE.
//
// The issue proposed storing `trail_graph.json` alone as the cheap option -
// "the first is the minimum, the third is nearly free, the second is the real
// weight". That was true when it was written and stopped being true the same
// week. #1093 removed the chord fallback from snapping, so `nearestPointOnGraph`
// now skips every edge with no vertices and `canSnapToGraph` is false for the
// routing half alone. A phone holding graph-without-geometry therefore opens a
// builder that refuses EVERY tap with "OurHike hasn't got this area's trail
// lines yet" - a sentence lib/dayHikeDraft.ts already documents as false when
// the geometry is never coming. The minimum set that works offline is graph
// plus geometry.
//
// And the sizes in the issue are decoded rather than wire. Measured against
// data.ourhike.org on 2026-08-27 with `Accept-Encoding: gzip`:
//
//   trail_graph.json            1,204,136 B wire   7,475,349 B decoded
//   trail_graph_geometry.json   4,695,479 B wire  17,285,133 B decoded
//   trail_graph_elevation.json     54,902 B wire     277,331 B decoded
//   ------------------------------------------------------------------
//   all three                        5.95 MB           25.04 MB
//
// So the download cost of taking everything is about 2% on top of a corridor
// package that is already ~314 MB of tiles. What 25 MB actually costs is
// IndexedDB, which is a different argument from the one the issue's body makes.
//
// WHAT IS STORED, AND WHY THE HASH TRAVELS WITH THE BYTES
//
// `{bytes, hash, version, fetchedAt}` per artifact, verified on write.
//
// A PHONE OFFLINE CANNOT REACH `latest.json`, so it cannot re-derive what the
// bytes it holds SHOULD hash to. It has to trust a hash recorded at write
// time - which is safe, because nothing is ever written that did not match the
// manifest at the moment it was fetched. This is `lib/nearbyTrailData.ts`'s
// shape, copied deliberately: that module already stores a 7.3 MB artifact
// against its published hash and its read-through is the one this follows.
//
// It is NOT `lib/conditionsCache.ts`'s shape, which #1050's own comment names
// as the template. That module stores `{document, storedAt}` - no bytes, no
// hash, no version - and its `MAX_CACHED_BYTES = 2 * 1024 * 1024` would
// silently delete a 7.5 MB graph on every write.
//
// WHY THE MANIFEST VERSION IS RECORDED
//
// `lib/dayHikes.ts` refuses to persist a `GraphPoint.edgeIndex` because
// `build_trail_graph.py` renumbers edges between publishes. A cached graph
// inherits that hazard one level up: the version is what lets a phone tell
// "the graph I hold" from "the graph my saved hike was priced against", and
// nothing in the resolve path asks that today because until now there has only
// ever been one graph in memory at a time.
//
// Recorded rather than acted on. What it enables - a card that can say its
// cached figures were computed against a different release - is a change to
// what a screen SAYS, which wants its own before-and-after.

import { del, get, set } from 'idb-keyval'

import {
  TRAIL_GRAPH_GEOMETRY_KEY,
  TRAIL_GRAPH_ELEVATION_KEY,
  TRAIL_GRAPH_KEY,
  TRAIL_GRAPH_PROFILE_KEY,
} from './config'

/** One artifact's stored copy. */
export interface StoredGraphArtifact {
  bytes: Blob
  /** The sha256 the manifest named when these bytes were fetched. */
  hash: string
  /** The release version the manifest carried then, or null when it named
   *  none. See the header for what this is for and what it is not. */
  version: string | null
  /** Epoch ms. For a screen that wants to say how old this copy is - nothing
   *  in this module reads it, and nothing decides anything on it. */
  fetchedAt: number
}

/** The store keys, one per published artifact. Spelled out rather than derived
 *  from the published key so that renaming the artifact does not silently
 *  orphan every phone's copy of it. */
export const GRAPH_STORE_KEYS: Record<string, string> = {
  [TRAIL_GRAPH_KEY]: 'ourhike:trail-graph',
  [TRAIL_GRAPH_GEOMETRY_KEY]: 'ourhike:trail-graph-geometry',
  [TRAIL_GRAPH_ELEVATION_KEY]: 'ourhike:trail-graph-elevation',
  [TRAIL_GRAPH_PROFILE_KEY]: 'ourhike:trail-graph-profile',
}

/**
 * How much room to leave free after writing.
 *
 * NOTHING IN THIS CODEBASE CHECKED ROOM BEFORE STORING A VECTOR ARTIFACT, and
 * the graph would have been the largest one yet. `archiveDownload.ts` refuses a
 * download that would not fit; `nearbyTrailData.ts` writes 7.3 MB behind a bare
 * try/catch and lets the browser decide. A quota error is caught either way -
 * the session keeps working on the bytes in hand - so this is not about
 * correctness. It is about not evicting a hiker's downloaded MAP to make room
 * for a routing graph, which a browser under pressure will do without asking.
 *
 * @unvalidated - 50 MB is roughly twice what all four artifacts decode to, so
 * a phone that cannot spare it is a phone with nothing to spare. Nobody has
 * measured what a real phone's headroom looks like after a 314 MB archive,
 * which is what would settle it.
 */
export const GRAPH_STORE_HEADROOM_BYTES = 50 * 1024 * 1024

/** A stored copy, or null when there is none this module trusts. */
export async function readStoredGraph(
  publishedKey: string,
): Promise<StoredGraphArtifact | null> {
  const storeKey = GRAPH_STORE_KEYS[publishedKey]
  if (storeKey === undefined) return null
  try {
    const record = (await get(storeKey)) as StoredGraphArtifact | undefined
    // Shape-checked because this store is written by every past version of
    // this module there will ever be. A record that is not a blob and a hash
    // is treated as absent, and the next verified fetch rewrites it.
    if (record?.bytes instanceof Blob && typeof record.hash === 'string') {
      return {
        bytes: record.bytes,
        hash: record.hash,
        version: typeof record.version === 'string' ? record.version : null,
        fetchedAt: typeof record.fetchedAt === 'number' ? record.fetchedAt : 0,
      }
    }
  } catch {
    // An unreadable store is the no-store case. The fetch path still answers.
  }
  return null
}

/**
 * Keep a verified copy, or decline quietly.
 *
 * NEVER THROWS, and never costs the session the bytes in hand: a full store,
 * a refusing one, or one with no room to spare all end with the caller holding
 * exactly what it fetched. Storing is an improvement on the next launch, not a
 * condition of this one.
 */
export async function writeStoredGraph(
  publishedKey: string,
  record: Omit<StoredGraphArtifact, 'fetchedAt'> & { fetchedAt?: number },
): Promise<boolean> {
  const storeKey = GRAPH_STORE_KEYS[publishedKey]
  if (storeKey === undefined) return false
  try {
    if (!(await hasRoomFor(record.bytes.size))) return false
    await set(storeKey, {
      bytes: record.bytes,
      hash: record.hash,
      version: record.version,
      fetchedAt: record.fetchedAt ?? Date.now(),
    } satisfies StoredGraphArtifact)
    return true
  } catch {
    return false
  }
}

/**
 * Whether the phone can spare the bytes plus the headroom above.
 *
 * True when the browser will not say, which is the right way for this to fail:
 * `navigator.storage.estimate` is absent on some engines and inaccurate on
 * others, and refusing to store on a phone that never answers would make the
 * offline builder a feature only some browsers get. The write itself is still
 * guarded - a quota error is caught above.
 */
async function hasRoomFor(bytes: number): Promise<boolean> {
  try {
    const estimate = await navigator.storage?.estimate?.()
    if (estimate === undefined) return true
    const { quota, usage } = estimate
    if (typeof quota !== 'number' || typeof usage !== 'number') return true
    return quota - usage >= bytes + GRAPH_STORE_HEADROOM_BYTES
  } catch {
    return true
  }
}

/** Forget every stored artifact - what "remove the trail data" has to reach. */
export async function clearStoredGraph(): Promise<void> {
  for (const storeKey of Object.values(GRAPH_STORE_KEYS)) {
    try {
      await del(storeKey)
    } catch {
      // One key that will not delete must not stop the others.
    }
  }
}

/** The bytes each stored artifact holds, for the Downloads window's row.
 *  Absent artifacts are absent from the result rather than zero: nothing
 *  stored is not the same claim as an empty file. */
export async function storedGraphBytes(): Promise<Record<string, number>> {
  const sizes: Record<string, number> = {}
  for (const publishedKey of Object.keys(GRAPH_STORE_KEYS)) {
    const stored = await readStoredGraph(publishedKey)
    if (stored !== null) sizes[publishedKey] = stored.bytes.size
  }
  return sizes
}
