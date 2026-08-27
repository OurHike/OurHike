// The trail lines other organizations maintain (#950,
// features/NEARBY_TRAILS.md, pipeline/export_nearby_trails.py).
//
// WHAT ARRIVES HERE
//
// One GeoJSON artifact of somebody else's trails - NYS OPRHP's, NYNJTC's,
// Mohonk Preserve's and NYS DEC's today, statewide since #1019 rather than
// clipped to a box around New York City - carrying exactly the properties the
// A.T.'s own lines carry
// (`source`, `blaze_color`, `name`, `trail_status`, `id`). That is what lets
// map/style.ts draw them with the same expressions rather than a second
// appearance to keep in step: they take the side-trail width because no
// unrecognised source is a through-route, and they GHOST because
// map/nearbyTrails.ts dims every source outside CHOSEN_SYSTEM_SOURCES.
//
// A SEPARATE ARTIFACT FROM trails.geojson, AND THE REASON IS A LICENCE
//
// Not a size decision, and not tidiness. These lines are SEPARATELY
// LICENSED from the A.T.'s: NYS OPRHP permits reuse with required attribution,
// NYNJTC state no terms and ship on the maintainer's authorisation, and ATC's
// own centerline sits on a third basis again (sources.json). Folding them into
// trails.geojson would have made "publish the A.T." and "publish two other
// organizations' data" one action that no field could separate again - which
// is exactly what `reaches_hikers` exists to keep separable, per steward, per
// source. Two files, and either can be held without touching the other.
//
// A 404 IS STILL AN ORDINARY ANSWER, EVEN NOW THAT IT SHIPS
//
// The licences resolved on 2026-08-24 and the artifact publishes, but a 404
// stays the expected answer in two states that are not failures: a phone whose
// release predates the artifact, and any bucket a publish has not reached yet.
// It also lets a reviewer point the app at a local `serve_processed.py`. All
// three end the same way - no nearby trails, chosen trail unaffected.
//
// IT IS HELD TO ITS PUBLISHED HASH (#197)
//
// Every artifact this app draws is. A corrupted trail line is a trail drawn
// somewhere it does not go, and that is no more acceptable for somebody
// else's trail than for the A.T. - a hiker at a junction cannot tell which
// organization drew the line they are looking at, and should not have to.
//
// A FAILURE HERE IS SILENT, LIKE lib/trailOverview.ts's AND UNLIKE
// lib/trailData.ts's
//
// Nobody asked for these lines. They are context around the trail the hiker
// chose, so a 404, a hash mismatch, a refused origin or no signal at all end
// the same way: with the chosen trail drawn exactly as it is drawn today and
// - where nothing verified is stored either - nothing else on the map. That
// is the state the app has shipped in all along, which is what makes it a
// safe thing to fall back to.
//
// STORED AS A CACHE OF THE LAST VERIFIED FETCH - NOT AS OFFLINE COVERAGE
//
// This module used to fetch over the network and keep nothing, and its own
// header called that "a real gap rather than a design". Half of the gap is
// closed here, and the half that is not is the half that was deliberately
// deferred (#1082 is the closing; the deferral's reasoning is preserved
// below because it still governs the other half):
//
// - What IS built: the last verified copy is kept, whole, in IndexedDB.
//   A launch serves it and asks the manifest whether it is still current -
//   which since #1019 is the difference between a ~KB manifest read and
//   re-fetching a 7.3 MB gzip on every launch (pipeline/README.md's "one
//   number wants watching", measured 2026-08-25), and between an offline
//   launch drawing these lines and drawing none.
//
// - What is deliberately NOT built: any notion of what a named download
//   CONTAINS. features/NEARBY_TRAILS.md §9's "a download named 'Harriman'
//   contains every shipped trail and every safety POI inside its boundary"
//   is **#552 - Decide the unit of offline coverage, and write it down**'s
//   decision and **#551 - v2: offline coverage in pieces**'s machinery, and
//   guessing at it here would put a bounded, differently-shaped store beside
//   this one for those issues to have to unpick later. This cache is
//   whole-artifact or nothing, carries no boundary, and appears in no
//   download UI - it is a performance and continuity measure, not coverage.
//
// STALE IS SERVED, AND SAYS NOTHING - THE SAME TRADE THE FETCH PATH MADE
//
// A stored copy is served when there is no signal, and kept when a refresh
// fails. Both are drawing lines that were verified against the manifest of an
// earlier day, which is exactly what the fetch-only version drew for the whole
// of a session that started before a publish landed. The refresh runs once per
// online launch (and once when signal arrives, for a launch that had none), so
// staleness is bounded by the hiker's own launch cadence - the cadence the
// fetch-only version was already bound to.

import { get, set } from 'idb-keyval'
import { dataUrl, DATA_CONFIGURED, NEARBY_TRAILS_KEY } from './config'
import { publishedHash } from './dataManifest'
import { sha256Of } from './trailData'

/**
 * The one record this module keeps: the artifact's bytes and the published
 * hash they matched when they were fetched (#197). The hash is stored so a
 * later launch can answer "is this still what is published?" with a string
 * comparison against the manifest - the bytes are NOT re-hashed on read,
 * which is the standard lib/trailData.ts already sets for its own stored
 * blobs: verification happens where bytes cross the network.
 */
export const NEARBY_TRAILS_STORE_KEY = 'ourhike:nearby-trails'

type StoredNearbyTrails = { bytes: Blob; hash: string }

/**
 * The nearby-trail network as an object URL, or null when there is not one to
 * draw, plus whether that answer was checked against the live manifest.
 *
 * An object URL rather than parsed GeoJSON for lib/trailOverview.ts's two
 * reasons, unchanged: it is what MapLibre wants, and the bytes are what was
 * hashed - handing the map a re-serialised copy would draw something nobody
 * checked.
 */
export type NearbyTrailsAnswer = {
  url: string
  /**
   * True when this session compared the answer against the published
   * manifest - whether that kept the stored copy, replaced it, or fell back
   * to it after a failed refresh. False only for a copy served without
   * signal, which is the caller's cue (lib/useTrailData.ts) to ask again
   * when signal arrives.
   */
  revalidated: boolean
}

async function readStored(): Promise<StoredNearbyTrails | null> {
  try {
    const record = (await get(NEARBY_TRAILS_STORE_KEY)) as StoredNearbyTrails | undefined
    // Shape-checked because this store is written by every past version of
    // this module there will ever be: a record that is not exactly a blob and
    // a hash is treated as absent, and the next verified fetch rewrites it.
    if (record?.bytes instanceof Blob && typeof record.hash === 'string') {
      return record
    }
  } catch {
    // An unreadable store is the no-store case, not a failure worth a word -
    // the fetch path below still answers.
  }
  return null
}

function urlFor(stored: StoredNearbyTrails): NearbyTrailsAnswer {
  return { url: URL.createObjectURL(stored.bytes), revalidated: false }
}

/**
 * Loads the nearby-trail network: from the store when there is no signal,
 * and against the published manifest when there is - re-fetching the
 * artifact only when the manifest names a hash the stored copy does not
 * carry. See the module header for what is stored and what stale means.
 */
export async function loadNearbyTrails(
  online: boolean,
  signal?: AbortSignal,
): Promise<NearbyTrailsAnswer | null> {
  if (!DATA_CONFIGURED) return null

  const stored = await readStored()
  if (!online) {
    return stored === null ? null : urlFor(stored)
  }

  try {
    const expected = await publishedHash(NEARBY_TRAILS_KEY, { signal })
    if (expected === null) {
      // No manifest, or a manifest naming no hash. Fresh bytes would be
      // unverifiable and are not drawn (the header's #197 stance) - but the
      // stored copy was verified when it was fetched, so it is served, as it
      // would be offline. `revalidated` is true because the question was
      // ASKED this session; answering false here would re-ask on a loop for
      // as long as the manifest stays unreachable.
      return stored === null ? null : { ...urlFor(stored), revalidated: true }
    }

    if (stored !== null && stored.hash === expected) {
      // The common launch since #1082: the manifest still names the hash the
      // store carries, and the 23.5 MB artifact is not fetched at all.
      return { ...urlFor(stored), revalidated: true }
    }

    const response = await fetch(dataUrl(NEARBY_TRAILS_KEY), { signal })
    // A release exported before this artifact existed, or a bucket a publish
    // has not reached. Not a failure - see the header. The stored copy, where
    // one exists, outlives a bucket that has gone quiet.
    if (!response.ok) {
      return stored === null ? null : { ...urlFor(stored), revalidated: true }
    }

    const bytes = new Uint8Array(await response.arrayBuffer())
    if ((await sha256Of(bytes)) !== expected) {
      // Bytes that are not what was published are not drawn - and not
      // stored. The last verified copy stands.
      return stored === null ? null : { ...urlFor(stored), revalidated: true }
    }

    const fresh: StoredNearbyTrails = {
      bytes: new Blob([bytes as unknown as BlobPart], {
        type: response.headers.get('content-type') ?? 'application/geo+json',
      }),
      hash: expected,
    }
    try {
      await set(NEARBY_TRAILS_STORE_KEY, fresh)
    } catch {
      // A full or refusing store must not cost the session its lines: the
      // verified bytes in hand still draw, and the next launch fetches again
      // exactly as every launch did before this cache existed.
    }
    return { url: URL.createObjectURL(fresh.bytes), revalidated: true }
  } catch (error) {
    // The abort is the caller unmounting - nothing should be handed back,
    // because nothing would revoke it.
    if ((error as { name?: string } | null)?.name === 'AbortError') return null
    // Every other way the refresh can fail - no signal after all, a refused
    // origin - lands where the offline branch already stands: the last
    // verified copy, or nothing. Revalidated, because the attempt was made;
    // the next launch tries again.
    return stored === null ? null : { ...urlFor(stored), revalidated: true }
  }
}
