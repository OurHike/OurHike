// The trail line a first run can have in about a second (#869).
//
// WHAT THIS IS FOR
//
// The entry steps are a card over the live map, and on a phone holding
// nothing there was no map behind them worth the name. #863 got the real
// centerline drawn as soon as it is fetched rather than when the whole
// release commits, which took the first line from ~12 s to ~5 s; the five
// seconds that remain are mostly `trails.geojson` itself - 4,143,296 gzipped
// bytes, ~2.8 s of transfer at 12 Mbps, measured against the live bucket
// 2026-08-20. No client can make those bytes arrive sooner.
//
// So there is a second artifact that is 81x smaller and good enough to answer
// the only question the corridor view asks - where does the trail run
// (lib/config.ts's TRAILS_OVERVIEW_KEY, pipeline/export_trails.py's
// write_overview). This module fetches it, checks it, and hands back a URL
// the map can draw. It is a sketch with a deadline: the real line replaces it
// within seconds, and everything below is written so that nothing outlives
// that moment.
//
// IT IS STILL HELD TO ITS PUBLISHED HASH (#197)
//
// Every artifact this app draws is, and a sketch is not an exemption - a
// corrupted overview is a trail drawn somewhere it does not go, which is the
// one thing this map cannot do even for three seconds. The manifest is
// preloaded alongside it (index.html), so the check costs a cache read rather
// than a round trip.
//
// A FAILURE HERE IS SILENT, AND THAT IS THE DIFFERENCE FROM lib/trailData.ts
//
// There, a failed fetch is reported: the hiker asked for a map and did not
// get one. Nobody asked for this. It is a few seconds of head start, so a
// 404 (a release published before this artifact existed), a hash mismatch, a
// refused origin or no signal at all end the same way - with nothing drawn,
// and the real centerline still coming through the path that does report.

import { dataUrl, DATA_CONFIGURED, TRAILS_OVERVIEW_KEY } from './config'
import { publishedHash } from './dataManifest'
import { sha256Of } from './trailData'

/**
 * The corridor-view centerline as an object URL, or null when there is not
 * one to draw.
 *
 * An object URL rather than the parsed GeoJSON because that is what MapLibre
 * wants and because the bytes are what was hashed: handing the map a
 * re-serialised copy would draw something nobody checked.
 */
export async function fetchTrailOverview(signal?: AbortSignal): Promise<string | null> {
  if (!DATA_CONFIGURED) return null

  try {
    const response = await fetch(dataUrl(TRAILS_OVERVIEW_KEY), { signal })
    // A release exported before this artifact existed. Not a failure - the
    // same reading spurs.json and elevation_profile.json get.
    if (!response.ok) return null

    const bytes = new Uint8Array(await response.arrayBuffer())
    const expected = await publishedHash(TRAILS_OVERVIEW_KEY, { signal })
    // Null where the manifest names no hash for it, which is the same
    // downgrade lib/dataManifest.ts describes: a bucket with no manifest, or
    // one written before this key existed, falls back to the checks that ran
    // before #197 - and for this artifact that is "draw it", because the only
    // thing riding on it is three seconds of sketch.
    if (expected !== null && (await sha256Of(bytes)) !== expected) return null

    return URL.createObjectURL(
      new Blob([bytes as unknown as BlobPart], {
        type: response.headers.get('content-type') ?? 'application/geo+json',
      }),
    )
  } catch {
    // Every way a fetch can fail, including the abort that arrives when the
    // real centerline lands first and the shell stops caring. None of them is
    // worth a word to the hiker.
    return null
  }
}
