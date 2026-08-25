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
// nothing else on the map. That is the state the app has shipped in all
// along, which is what makes it a safe thing to fall back to.
//
// NOT STORED, AND THAT IS A REAL GAP RATHER THAN A DESIGN
//
// This fetches over the network and keeps nothing, so a phone with no signal
// draws no nearby trails. features/NEARBY_TRAILS.md §9 asks for the opposite
// in as many words - "a download named 'Harriman' contains every shipped
// trail and every safety POI inside its boundary" - and that is not what this
// does. It is not built here because what a download CONTAINS is
// **#552 — Decide the unit of offline coverage, and write it down**'s
// decision and **#551 — v2: offline coverage in pieces**'s machinery, and
// guessing at it now would put a second, differently-shaped store beside
// lib/trailData.ts's for the one to have to be unpicked later. Until then the
// honest description is the one at the top of this paragraph.

import { dataUrl, DATA_CONFIGURED, NEARBY_TRAILS_KEY } from './config'
import { publishedHash } from './dataManifest'
import { sha256Of } from './trailData'

/**
 * The nearby-trail network as an object URL, or null when there is not one to
 * draw.
 *
 * An object URL rather than parsed GeoJSON for lib/trailOverview.ts's two
 * reasons, unchanged: it is what MapLibre wants, and the bytes are what was
 * hashed - handing the map a re-serialised copy would draw something nobody
 * checked.
 */
export async function fetchNearbyTrails(signal?: AbortSignal): Promise<string | null> {
  if (!DATA_CONFIGURED) return null

  try {
    const response = await fetch(dataUrl(NEARBY_TRAILS_KEY), { signal })
    // A release exported before this artifact existed, or a bucket a publish
    // has not reached. Not a failure - see the header.
    if (!response.ok) return null

    const bytes = new Uint8Array(await response.arrayBuffer())
    const expected = await publishedHash(NEARBY_TRAILS_KEY, { signal })
    // WHERE THIS DEPARTS FROM lib/trailOverview.ts, deliberately: there, a
    // manifest naming no hash falls back to drawing the sketch, because the
    // only thing riding on it is three seconds of a corridor-view line that
    // is replaced within seconds and is drawn nowhere a hiker reads a
    // position off. These lines are drawn at every zoom, sit under the
    // hiker's dot, and are the map at a junction. Unverifiable bytes do not
    // get drawn as trails.
    if (expected === null) return null
    if ((await sha256Of(bytes)) !== expected) return null

    return URL.createObjectURL(
      new Blob([bytes as unknown as BlobPart], {
        type: response.headers.get('content-type') ?? 'application/geo+json',
      }),
    )
  } catch {
    // Every way a fetch can fail, the abort included. None is worth a word to
    // the hiker - see the header.
    return null
  }
}
