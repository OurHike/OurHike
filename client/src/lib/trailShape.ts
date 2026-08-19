// Whether the trails.geojson on this phone has the merged-chain shape (#161),
// which is the fact that decides the map's `tolerance` for the trails source.
//
// THE PROBLEM THIS SOLVES. geojson-vt's per-zoom simplification drops whole
// features under a projected-length bar, and the pre-merge export's ~3,000
// short centerline segments sat under it at corridor zooms - the miles-long
// gaps of #160. `tolerance: 0` (map/style.ts) makes the drop structurally
// impossible and is the right setting for every pre-merge copy of the data;
// it also disables per-zoom vertex thinning, which costs ~220 ms of worker
// time and 30-50x the displayable geometry at low zooms. The pipeline now
// merges the centerline into maximal chains (pipeline/export_trails.py,
// #161), far above the drop bar at any zoom - and for THAT shape the default
// tolerance is both safe and better.
//
// WHY THIS IS DECIDED PER PHONE RATHER THAN PER RELEASE. The stored blob is
// the authority on what this phone will draw, and it outlives every release:
// trail data re-downloads only when missing, so a phone that downloaded
// before the merge keeps the segmented shape indefinitely, however new the
// published release is. A build-time flag would flip those phones to the
// default tolerance and reopen #160's gaps for exactly the hikers who have
// been offline longest. So the shape is detected from the artifact itself at
// download time, and the answer rides with the data it describes.
//
// WHY localStorage AND NOT IndexedDB. The tolerance is a GeoJSON source
// option, fixed when the style is built - and the style is built before any
// IndexedDB read resolves (the map must not wait on the store; see
// MapView.tsx). localStorage is synchronous, so the answer recorded at
// download time is readable at style-build time. The two stores can in
// principle diverge, and every divergence degrades safely: a cleared flag
// over merged data costs only the worker time `tolerance: 0` always cost,
// and a surviving flag over an evicted blob applies the default tolerance to
// an empty collection, which has nothing to drop. The dangerous combination
// - default tolerance over SEGMENTED data - cannot be produced, because the
// flag is only ever written from a sniff of the exact bytes being stored.

/** Where the answer is kept. */
export const TRAILS_MERGED_STORAGE_KEY = 'ourhike:trails-merged-chains'

/**
 * What a merged export looks like from the outside: the chain ids
 * pipeline/export_trails.py mints (`centerline:chain:<n>`), as they appear in
 * the serialized GeoJSON. A published contract with that file, not a
 * heuristic - its test pins the spelling on the pipeline side, and
 * trailShape.test.ts pins it here, so the two cannot drift silently.
 */
export const CHAIN_ID_MARKER = '"centerline:chain:'

/** Whether this serialized trails.geojson has the merged-chain shape. */
export function sniffMergedChains(trailsText: string): boolean {
  return trailsText.includes(CHAIN_ID_MARKER)
}

/**
 * Record what shape the trails data being stored has. Called only from the
 * download commit path (lib/trailData.ts), beside the bytes it describes.
 */
export function writeTrailsMerged(merged: boolean): void {
  try {
    localStorage.setItem(TRAILS_MERGED_STORAGE_KEY, merged ? 'true' : 'false')
  } catch {
    // Storage full or unavailable - the read side answers false, which is
    // the conservative tolerance. Never worth failing a download over.
  }
}

/**
 * Whether the stored trails data is known to have the merged-chain shape.
 *
 * False for anything except an explicit recorded "true": no record means the
 * data predates the merge (or predates this flag), and both of those need
 * `tolerance: 0`. The conservative direction is always available and only
 * ever costs performance, never a missing trail.
 */
export function readTrailsMerged(): boolean {
  try {
    return localStorage.getItem(TRAILS_MERGED_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

/** The other half of deleteTrailData: no data, no claim about its shape. */
export function clearTrailsMerged(): void {
  try {
    localStorage.removeItem(TRAILS_MERGED_STORAGE_KEY)
  } catch {
    // Nothing to do - an unremovable stale "true" still degrades safely,
    // per the divergence note in the module header.
  }
}
