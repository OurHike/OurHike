// Which coverage cells this phone holds, as the shell tells the tile handlers
// that cannot ask (#1591, #1257 stage 2).
//
// A LEAF, ON PURPOSE. map/basemap.ts and map/networkTiles.ts answer the
// `basemap://` and `network://` tile requests out of the held cells before
// they spend a byte of a data plan, and the shell tells them which cells are
// held through a setter. Those two setters used to live in the handler
// modules themselves, so the shell's one import of each - `setBasemapCells`,
// `setNetworkCells`, called from App.tsx as the completion markers are read
// - put both handlers, the pmtiles library they read archives with, and
// fflate under it into the bundle a launch parses before its first frame:
// 14,295 + 4,508 raw bytes on a Today screen that mounts no map, measured
// 2026-09-30 by attributing the built chunks to their sources. The record
// lives here now, importing only a type; the handlers read it on every tile
// and subscribe to prune a reader for a cell no longer held. The handlers
// still re-export their setter, so a test or a reader that imported it from
// them still finds it.
//
// `held` is package keys (lib/coverageCells.ts's `cellPackageKey` under the
// family, plus its context key), read on every tile rather than copied into
// anything: a cell that finishes downloading mid-session is answered from on
// the next tile the map asks for. Null until the shell has an index to hand
// over, which reads as "no cells" - the bucket is then the whole answer,
// exactly as before cells existed.

import type { CellIndex } from '../lib/coverageCells'

export interface HeldCells {
  index: CellIndex
  held: ReadonlySet<string>
}

type Family = 'basemap' | 'network'

/** What the shell last said, per family. */
const held: Record<Family, HeldCells | null> = { basemap: null, network: null }

/** Who wants to hear the set change - the handler's reader pruning. */
const listeners: Record<Family, Set<(held: ReadonlySet<string>) => void>> = {
  basemap: new Set(),
  network: new Set(),
}

function setCells(
  family: Family,
  index: CellIndex | null,
  keys: ReadonlySet<string>,
): void {
  held[family] = index === null ? null : { index, held: keys }
  for (const listener of listeners[family]) listener(keys)
}

function onCellsSet(
  family: Family,
  listener: (held: ReadonlySet<string>) => void,
): () => void {
  listeners[family].add(listener)
  return () => {
    listeners[family].delete(listener)
  }
}

/**
 * The hiking sheet's cells (map/basemap.ts). Idempotent and cheap, meant to
 * be called on every change: a cell finishing its download, a stretch being
 * removed, the index arriving after a launch with no signal.
 */
export function setBasemapCells(
  index: CellIndex | null,
  keys: ReadonlySet<string>,
): void {
  setCells('basemap', index, keys)
}

/** The other organizations' network cells (map/networkTiles.ts), on the
 *  same terms. */
export function setNetworkCells(
  index: CellIndex | null,
  keys: ReadonlySet<string>,
): void {
  setCells('network', index, keys)
}

export function heldBasemapCells(): HeldCells | null {
  return held.basemap
}

export function heldNetworkCells(): HeldCells | null {
  return held.network
}

/** Called with the held set on every `setBasemapCells`, so a handler can
 *  drop a reader for a cell that is gone. Returns the unsubscribe. */
export function onBasemapCellsSet(
  listener: (held: ReadonlySet<string>) => void,
): () => void {
  return onCellsSet('basemap', listener)
}

export function onNetworkCellsSet(
  listener: (held: ReadonlySet<string>) => void,
): () => void {
  return onCellsSet('network', listener)
}

/** Test seam only - forgets both families, so a test observes a shell that
 *  has said nothing yet. The handlers' own `reset*ForTests` call it. */
export function resetHeldCellsForTests(): void {
  held.basemap = null
  held.network = null
}
