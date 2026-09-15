// Where the shell tells the terrain which DEM cells this phone holds
// (#1475) - and, deliberately, a module that does not import `maplibre-gl`.
//
// WHY THIS IS NOT JUST A FUNCTION IN contours.ts. It was, for about an hour,
// and `scripts/check-build-output.mjs` caught it: contours.ts imports
// `addProtocol` from maplibre-gl as a VALUE, so one static import of it from
// App.tsx put the whole engine in the chunk the document loads before any
// `import()` - 119 KB gzipped of it - and took the eager launch budget from
// under 256,000 bytes to 380,684. That is #1300's rule and
// features/LAUNCH_BUDGET.md §3's number, both broken by an import that looked
// like plumbing.
//
// map/networkTiles.ts keeps the same line by importing `addProtocol` as a
// TYPE only and taking the real one from the engine seam, which is why
// `setNetworkCells` can be called from the shell directly. contours.ts has
// not had that treatment, so the seam moves here instead: this module holds
// the answer, the shell sets it, and contours.ts registers what to do with it
// once it has a DEM source to do it to.
//
// KEPT, NOT JUST FORWARDED, which is the half that would be easy to leave
// out: the cell index is fetched at launch and the map is built later, so the
// shell's first answer routinely arrives before there is anything to deliver
// it to. Remembering it means the terrain starts out knowing what the phone
// holds rather than reading its first tiles as if it held nothing - which on
// a phone with no signal is a blank hillshade until something happens to call
// this again.

import type { CellIndex } from '../lib/coverageCells'

/** What a deliverer does with the shell's answer: post it into the DEM
 *  worker, or set demTiles.ts's module variable where there is no worker.
 *  contours.ts decides which; this module never knows. */
export type DemCellSink = (index: CellIndex | null, held: ReadonlySet<string>) => void

let pending: { index: CellIndex | null; held: ReadonlySet<string> } | null = null
let sink: DemCellSink | null = null

/**
 * Tell the terrain which DEM cells this phone holds.
 *
 * Idempotent and cheap, and meant to be called on every change: a cell
 * finishing its download, a stretch being removed, the index arriving after a
 * launch with no signal. What it is NOT is a repaint - tiles already drawn
 * stay drawn, and the new answer reaches the next tile asked for, exactly as
 * map/networkTiles.ts's `setNetworkCells` does for the lines.
 */
export function setTerrainCells(
  index: CellIndex | null,
  held: ReadonlySet<string>,
): void {
  pending = { index, held }
  sink?.(index, held)
}

/**
 * Register where the answer goes, and deliver whatever the shell has already
 * said. Called by map/contours.ts the moment it has a DEM source.
 *
 * `null` before the shell has said anything, which is not the same claim as
 * "no cells" and must not be delivered as if it were.
 */
export function attachDemCells(deliver: DemCellSink): void {
  sink = deliver
  if (pending !== null) deliver(pending.index, pending.held)
}

/** Test seam only - drops both the sink and the remembered answer so a test
 *  can observe a fresh attach. Production never needs it; a page has one map. */
export function resetDemCellsForTests(): void {
  pending = null
  sink = null
}
