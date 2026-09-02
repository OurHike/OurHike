// Answers the hiking sheet's basemap:// tile requests: the downloaded
// package first, the network where the package does not answer (#189).
//
// WHY THE RESOLUTION LIVES HERE AND NOT IN THE STYLE
//
// features/MAP_OPTIONS.md's stacking principle - "every state is at least as
// good, and none of them needs to be detected" - rules out composing a
// different style per connectivity or per download state. So the style
// always declares one source with one template (liveTopo.ts), and WHICH
// bytes answer is decided here, per tile, at fetch time:
//
//   package holds the tile        -> local bytes. Fast, identical to the
//                                    live sheet (same OpenMapTiles schema,
//                                    pipeline/BASEMAP.md), zero data spent.
//   tile beyond the package       -> the same z/x/y from OpenFreeMap, so a
//                                    hiker with signal can pan past the
//                                    package's footprint and still see map.
//   no package, signal            -> every tile from the network: exactly
//                                    the live sheet as it was before #189.
//   no package, no signal         -> requests fail, layers draw nothing,
//                                    the paper backdrop shows through -
//                                    the same honest blank as before, and
//                                    liveSourceHealth still names it.
//
// No state is detected anywhere: "package absent" is not a flag someone
// checks but an ArchiveNotDownloadedError on a read that then falls
// through, and "beyond the footprint" is pmtiles returning undefined for a
// tile the archive never held. Local-first rather than live-first when both
// could answer, because local is the one that cannot be slow, cannot spend
// a data plan, and cannot disagree with what the same hiker saw yesterday.
//
// One honesty note, recorded where the choice is made: the package is built
// by our Planetiler job on our cadence; OpenFreeMap builds theirs weekly.
// Same schema, both OpenStreetMap - but a label edited upstream can differ
// between a local tile and the live tile one screen over until the next
// package release. That is data freshness, not wrongness, and the Downloads
// screen's release date is the place a hiker reads it.
//
// SINCE #557 THE PACKAGE IS NOT THE ONLY LOCAL ANSWER. The hiking sheet also
// ships in 1° cells plus one shared context archive (lib/coverageCells.ts,
// features/OFFLINE_COVERAGE.md), and a phone may hold any set of them with or
// without the whole package. So "local" is a short list rather than one
// archive, walked in order before the network is touched:
//
//   the whole package          -> if held, it holds everything a cell does
//   the held cells this tile   -> routed by the same rectangle overlap the
//   may sit in                    cutter used, seam margin included, so a tile
//                                 the pipeline put in a cell is looked for
//                                 there - and near a seam more than one may
//                                 hold it, and any held one answers
//   the context archive        -> at and under the context zoom only, which
//                                 is all it holds
//   the network                -> exactly as before
//
// Which cells are held is the shell's knowledge - the completion markers,
// read through lib/useArchiveDownload.ts - handed to this module through
// `setBasemapCells`. A protocol handler is not a React component and cannot
// subscribe to anything, so the shell pokes it the way MapView pokes a live
// map. Still nothing detected: an unheld cell is simply never asked.

import { addProtocol } from 'maplibre-gl'
import { PMTiles } from 'pmtiles'
import { BASEMAP_PACKAGE } from '../lib/packages'
import {
  cellPackageKey,
  cellsForTile,
  CONTEXT_PACKAGE_KEY,
  type CellIndex,
} from '../lib/coverageCells'
import { IndexedDbArchiveSource } from './pmtilesSource'
import { BASEMAP_SCHEME, OPENFREEMAP_TILEJSON } from './liveTopo'

const TILE_URL = new RegExp(`^${BASEMAP_SCHEME}://(\\d+)/(\\d+)/(\\d+)$`)

/**
 * The downloaded package, wrapped for reading - and dropped on any failure.
 *
 * pmtilesSource.ts's "never memoise a failure" rule applies one layer up
 * too, and not by analogy: pmtiles' SharedPromiseCache stores the header
 * promise BEFORE it settles and never evicts a rejection, so a PMTiles that
 * ever tried to read an absent archive would keep answering from that
 * cached rejection after the download completes. Discarding the instance on
 * failure is what lets the first tile after a finished download come from
 * the archive rather than from a stale error.
 */
let archive: PMTiles | null = null

function packageArchive(): PMTiles {
  archive ??= new PMTiles(new IndexedDbArchiveSource(BASEMAP_PACKAGE.idbKey))
  return archive
}

/** The cells the shell says this phone holds, by package key, and the index
 *  they are in. Null until the shell has an index to hand over, which reads
 *  as "no cells" - the package and the network are then the whole answer,
 *  exactly as before cells existed. */
let cells: { index: CellIndex; held: ReadonlySet<string> } | null = null

/** One reader per held cell and one for the context, by package key -
 *  created on first use and dropped on failure, on the package's own rule
 *  above. */
const readers = new Map<string, PMTiles>()

/**
 * What the shell knows about cells, for the handler that cannot ask.
 *
 * `held` is package keys (lib/coverageCells.ts's `cellPackageKey`, plus
 * CONTEXT_PACKAGE_KEY), and it is read on every tile rather than copied into
 * anything: a cell that finishes downloading mid-session is answered from on
 * the next tile the map asks for. A reader for a cell no longer in the set is
 * dropped - it would answer from bytes the hiker has removed, or from a
 * directory cached before a re-download replaced them.
 */
export function setBasemapCells(
  index: CellIndex | null,
  held: ReadonlySet<string>,
): void {
  cells = index === null ? null : { index, held }
  for (const key of [...readers.keys()]) {
    if (!held.has(key)) readers.delete(key)
  }
}

function reader(packageKey: string): PMTiles {
  let existing = readers.get(packageKey)
  if (existing === undefined) {
    existing = new PMTiles(new IndexedDbArchiveSource(packageKey))
    readers.set(packageKey, existing)
  }
  return existing
}

/** Which local archives may hold this tile, in the order they are asked. */
function localCandidates(z: number, x: number, y: number): string[] {
  if (cells === null) return []
  const { index, held } = cells
  const keys: string[] = []
  for (const cell of cellsForTile(index.cells, z, x, y, index.seamMarginKm)) {
    const key = cellPackageKey(cell.name)
    if (held.has(key)) keys.push(key)
  }
  if (index.context !== null && z <= index.contextZoom && held.has(CONTEXT_PACKAGE_KEY)) {
    keys.push(CONTEXT_PACKAGE_KEY)
  }
  return keys
}

/**
 * A tile out of one held archive, or undefined for a miss.
 *
 * An unreadable archive is a miss too, and the reader is dropped so the next
 * tile asks afresh - the same rule as the package's read below, for the same
 * reason: pmtiles never evicts a rejected header promise, so keeping the
 * instance would keep answering from a stale failure after a resume lands.
 */
async function readHeld(
  packageKey: string,
  z: number,
  x: number,
  y: number,
  signal: AbortSignal,
): Promise<ArrayBuffer | undefined> {
  try {
    const tile = await reader(packageKey).getZxy(z, x, y, signal)
    return tile?.data
  } catch (error) {
    if (isAbort(error)) throw error
    readers.delete(packageKey)
    return undefined
  }
}

/**
 * OpenFreeMap's concrete tile template, learned from its TileJSON once per
 * session - their tile URLs are dated deployment paths that must not be
 * hardcoded. Memoised on success only, for the session-length version of
 * the same reason as the archive handle: the usual failure is "offline
 * right now", and the fallthrough has to be able to recover the moment
 * signal returns.
 */
let networkTemplate: Promise<string> | null = null

function networkTileTemplate(): Promise<string> {
  if (networkTemplate !== null) return networkTemplate

  networkTemplate = fetch(OPENFREEMAP_TILEJSON)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Basemap TileJSON: HTTP ${response.status}`)
      }
      return response.json() as Promise<{ tiles?: unknown }>
    })
    .then(({ tiles }) => {
      const template = Array.isArray(tiles) ? tiles[0] : undefined
      if (typeof template !== 'string') {
        throw new Error('Basemap TileJSON carries no tile template')
      }
      return template
    })
    .catch((error: unknown) => {
      networkTemplate = null
      throw error
    })

  return networkTemplate
}

/** Abort is the map cancelling a tile it no longer wants - a normal event
 *  that must propagate as itself, never be misread as an archive miss.
 *  Matched on the name rather than instanceof: an abort arrives as a
 *  DOMException, whose place in the Error hierarchy varies by runtime. */
function isAbort(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as { name?: unknown }).name === 'AbortError'
  )
}

async function loadTile(
  url: string,
  signal: AbortSignal,
): Promise<{ data: Uint8Array; cacheControl?: string; expires?: string }> {
  const match = url.match(TILE_URL)
  if (match === null) throw new Error(`Not a ${BASEMAP_SCHEME}:// tile URL: ${url}`)
  const [z, x, y] = [Number(match[1]), Number(match[2]), Number(match[3])]

  try {
    const local = await packageArchive().getZxy(z, x, y, signal)
    // undefined is pmtiles' word for "this archive never held that tile" -
    // beyond the package's footprint, or above/below its zoom range. A
    // normal miss, so it falls through; only a held tile short-circuits.
    if (local !== undefined) return { data: new Uint8Array(local.data) }
  } catch (error) {
    if (isAbort(error)) throw error
    // ArchiveNotDownloadedError is the expected way here (nothing under the
    // key yet); anything else is unexpected but costs the same: this tile
    // resolves over the network, and the next one retries the archive.
    archive = null
  }

  // The cells, then the context - every held archive that could hold this
  // tile, before a byte of anybody's data plan is spent (#557).
  for (const key of localCandidates(z, x, y)) {
    const held = await readHeld(key, z, x, y, signal)
    if (held !== undefined) return { data: new Uint8Array(held) }
  }

  const template = await networkTileTemplate()
  const response = await fetch(
    template
      .replace('{z}', String(z))
      .replace('{x}', String(x))
      .replace('{y}', String(y)),
    { signal },
  )
  // A sparse tileset answers "no such tile" for open ocean; that is an empty
  // tile, not an error - the same convention pmtiles' own protocol uses for
  // vector archives.
  if (response.status === 404 || response.status === 204) {
    return { data: new Uint8Array() }
  }
  if (!response.ok)
    throw new Error(`Basemap tile ${z}/${x}/${y}: HTTP ${response.status}`)

  return {
    data: new Uint8Array(await response.arrayBuffer()),
    cacheControl: response.headers.get('cache-control') ?? undefined,
    expires: response.headers.get('expires') ?? undefined,
  }
}

let registered = false

/**
 * Registers the basemap:// handler. Idempotent, and called by MapView
 * before every map build, the same way as registerPMTilesProtocol() - a
 * second addProtocol for the same scheme would silently replace the first
 * mid-session, which is exactly the class of surprise that call exists to
 * prevent.
 */
export function registerBasemapProtocol(): void {
  if (registered) return
  addProtocol(BASEMAP_SCHEME, (params, abortController) =>
    loadTile(params.url, abortController.signal),
  )
  registered = true
}

/** Test seam only - drops the registration guard and both memos so a test
 *  can observe a fresh registration. Production never needs it. */
export function resetBasemapForTests(): void {
  registered = false
  archive = null
  networkTemplate = null
  cells = null
  readers.clear()
}
