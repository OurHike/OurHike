// How big an artifact the phone fetches whole may be (#1254).
//
// WHY THERE IS A NUMBER HERE AT ALL
//
// Six of the artifacts a launch asks for are read into memory entire: the
// other organizations' trail lines and their corridor-view sketch
// (lib/nearbyTrailData.ts, handed to MapLibre as one GeoJSON source), and the
// junction graph with its three index-aligned halves (lib/trailGraphData.ts,
// JSON.parsed on the main thread). Nothing weighed any of them before fetching,
// and on 2026-09-07 a data promotion carrying nationwide USFS layers (#1231)
// made nearby_trails.geojson 228,820,578 bytes decoded and trail_graph.json
// 78,595,556. Measured that day against production in a phone-sized Chromium,
// unthrottled on four cores: the graph's parse held the main thread for
// 9,800 ms and then 7,767 ms, and the lines took the renderer to 1,712 MB and
// crashed it. On a phone that was the report - "hanging on the first page...
// isn't responding to button presses" - and then a dead WebView.
//
// The manifest already says how big every artifact is before a byte moves
// (`size_bytes`, lib/dataManifest.ts's `decodedSizes`), so the app can decline
// what it cannot hold the way it already treats a 404: an ordinary absence,
// with its reason attached. An honest "not on this phone" outranks a map that
// crashes on the way to drawing it.
//
// THE NUMBER
//
// Reasoned from four measurements, none of them on a phone, which is why the
// tag below is what it is:
//
//   23.5 MB   nearby_trails.geojson before the growth, decoded (7.3 MB on the
//             wire, measured 2026-08-25) - shipped for weeks, drawn by MapLibre
//   17.3 MB   trail_graph_geometry.json before the growth (2026-08-27,
//             lib/trailGraphStore.ts's table) - JSON.parsed on the main thread
//             when the builder opens, and nobody reported it
//   78.6 MB   trail_graph.json after it - 1,144 ms of bare JSON.parse in Node
//             on the sandbox, 4-10 s of a dead main thread in the browser
//  228.8 MB   nearby_trails.geojson after it - the renderer dies
//
// 32 MiB sits above everything known to work with a third to spare, and under
// half of the smallest thing known to hurt. At the ~70 MB/s the sandbox parsed
// at, an artifact right at the budget costs the main thread about half a
// second there; the throttled phone profile the app is measured on
// (client/scripts/measure-first-run.mjs, 4x) makes that roughly two seconds -
// a stall a hiker feels, not a freeze, and the price of a budget that does not
// refuse the artifacts hikers had yesterday.
//
// @unvalidated - the two good data points are artifacts that shipped without
// complaint, not a measured ceiling; nobody has run measure-first-run.mjs on a
// phone against artifacts sized at this budget, which is what would settle it,
// in either direction.
//
// ONE NUMBER FOR TWO DIFFERENT COSTS, deliberately. A GeoJSON source is parsed
// in MapLibre's worker and costs the main thread its vertex buffers; the graph
// is parsed on the main thread outright. The tighter of the two is the one the
// budget has to protect, and a second constant would be a second unvalidated
// number for a reader to reconcile. If the graph ever moves off the main
// thread (the shape lib/trailIndexBuild.ts already has), the budget for it can
// loosen then, with a measurement.
//
// pipeline/verify_release.py reads this declaration (check 22) so a release
// carrying a text artifact over it fails the gate instead of reaching a phone -
// the same one-home argument that has the gate reading config.ts's keys. The
// literal below is the contract: keep it a number, not an expression.

/** Decoded bytes - what a fetched artifact occupies once the gzip is off. */
export const LAUNCH_ARTIFACT_BUDGET_BYTES = 33_554_432

/**
 * Whether `bytes` is more than a launch may fetch whole.
 *
 * Null - no published size - is NOT oversized: a manifest that names no
 * `size_bytes` predates the measurement, and refusing every artifact it
 * describes would take the map off a phone over a metadata field. Unknown is
 * not too large. The body is weighed again once it has arrived, which is the
 * backstop for exactly that manifest.
 *
 * A type predicate, so the caller that declines can print the number it
 * declined without a cast.
 */
export function oversized(bytes: number | null): bytes is number {
  return bytes !== null && bytes > LAUNCH_ARTIFACT_BUDGET_BYTES
}

/** The same question the other way round, for a reader asking "does it fit". */
export function withinLaunchBudget(bytes: number | null): boolean {
  return !oversized(bytes)
}

/** Where an artifact was weighed and found too big: the manifest before the
 *  fetch, the response after it, or the phone's own store on a later launch. */
export type WeighedAt = 'manifest' | 'response' | 'store'

/**
 * The console line for an artifact the app declined, printed where the
 * decision is made. A maintainer reading a phone's console is the one audience
 * that can act on it - the pipeline is where the size is decided - and a hiker
 * sees the same ordinary absence a 404 gives.
 */
export function warnOversized(key: string, bytes: number, at: WeighedAt): void {
  console.warn(
    `${key} is ${bytes} bytes decoded, over the ${LAUNCH_ARTIFACT_BUDGET_BYTES}-byte ` +
      `launch budget (lib/artifactBudget.ts, #1254); declined at the ${at} rather ` +
      `than parsed.`,
  )
}
