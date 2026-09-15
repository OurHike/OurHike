// The elevation model's tile reads: the downloaded DEM package first, AWS
// Terrain Tiles where the package does not answer (#187).
//
// This is basemap.ts's local-first shape applied to the DEM, at a different
// seam. The vector sheet's resolution lives in a MapLibre protocol; the
// DEM's cannot, because maplibre-contour fetches elevation tiles itself -
// its default getTile is a plain fetch(url), outside MapLibre's
// protocol-aware pipeline entirely. What it does expose is that exact
// function as a constructor parameter (`GetTileFunction`, a public,
// typed init option of its exported LocalDemManager), so this module is
// the app's implementation of it: same URL in, different bytes out.
//
// It runs in whichever thread the contour machinery runs in - the app's own
// DEM worker (demWorker.ts) when Workers exist, the main thread otherwise -
// which is why it lives alone in a module with no DOM dependencies:
// IndexedDB, pmtiles and fetch are all worker-safe, and nothing else is
// imported.
//
// The `url` argument is the AWS template already substituted (terrain.ts's
// DEM_TILE_URL is still the demUrlPattern), and stays the cache key one
// layer up whichever origin answers - one decoded tile per coordinate,
// never two. The z/x/y are parsed back out of it rather than passed
// alongside because GetTileFunction's shape is (url, abort) and matching
// the seam beats widening it.

import { PMTiles } from 'pmtiles'
import {
  cellPackageKey,
  cellsForTile,
  DEM_CELLS,
  type CellIndex,
} from '../lib/coverageCells'
import { DEM_PACKAGE } from '../lib/packages'
import { IndexedDbArchiveSource } from './pmtilesSource'
import { DEM_TILE_URL } from './terrain'

/**
 * maplibre-contour's FetchResponse, spelled structurally: the package's
 * entry point exports no named types (and its deep paths are fenced off by
 * both its exports map and vite.config.ts's alias), so the contract is
 * matched by shape. The assignment sites - LocalDemManager's `getTile`
 * field and init option - are typed upstream, and tsc checks this shape
 * against them there.
 */
export interface DemFetchResponse {
  data: Blob
  expires?: string
  cacheControl?: string
}

/** DEM_TILE_URL with its tokens turned into capture groups, so the z/x/y a
 *  request is for can be read back off the URL the seam hands over. */
const TILE_URL = new RegExp(
  `^${DEM_TILE_URL.replace(/[.]/g, '\\.')
    .replace('{z}', '(\\d+)')
    .replace('{x}', '(\\d+)')
    .replace('{y}', '(\\d+)')}$`,
)

/**
 * One reader per downloaded archive, by package key - the whole DEM package,
 * and since #1475 each held DEM cell and the shared context beside it.
 *
 * Dropped on any failure, for the reason basemap.ts documents: pmtiles'
 * SharedPromiseCache never evicts a rejected header promise, so keeping the
 * instance would keep answering from a stale error after a mid-session
 * download completes.
 */
const readers = new Map<string, PMTiles>()

function reader(packageKey: string): PMTiles {
  let existing = readers.get(packageKey)
  if (existing === undefined) {
    existing = new PMTiles(new IndexedDbArchiveSource(packageKey))
    readers.set(packageKey, existing)
  }
  return existing
}

/** The shell's last word on the DEM's cells, or null until it has one -
 *  which reads as "no cells", the state every phone was in before #1475. */
let cells: { index: CellIndex; held: ReadonlySet<string> } | null = null

/**
 * What the shell knows about the DEM's cells - map/networkTiles.ts's
 * `setNetworkCells`, for this family and across a worker boundary.
 *
 * THE BOUNDARY IS WHY THIS IS A SETTER AND NOT A READ. Everything else in
 * this module runs wherever the contour machinery runs, which is the app's
 * own DEM worker whenever Workers exist (map/demWorker.ts). A worker cannot
 * see the shell's hooks, so the held set arrives as a message
 * (map/demRpc.ts's `setCells`) and lands here; map/contours.ts forwards it,
 * and calls this directly on the no-Worker path.
 *
 * `held` is package keys (lib/coverageCells.ts's `cellPackageKey` under
 * DEM_CELLS, plus its context key), read on every tile rather than copied
 * anywhere: a cell that finishes downloading mid-session answers the next
 * tile the map asks for. A reader for a key no longer held is dropped - it
 * would answer from bytes the hiker has removed, or from a directory cached
 * before a re-download replaced them.
 */
export function setDemCells(index: CellIndex | null, held: ReadonlySet<string>): void {
  cells = index === null ? null : { index, held }
  for (const key of [...readers.keys()]) {
    if (key !== DEM_PACKAGE.idbKey && !held.has(key)) readers.delete(key)
  }
}

/**
 * Which downloaded archives may hold this tile, in the order they are asked.
 *
 * THE STRETCH FIRST, then the whole package, and the order is a cost rather
 * than a correctness choice: the cells are cut FROM `dem.pmtiles`, so on the
 * corridor both hold the same bytes. A phone that took a stretch holds no
 * whole package, and a phone that took the whole sheet holds no cells and
 * gets an empty list here for one in-memory lookup - so asking the specific
 * thing first is cheaper in both of the cases that actually occur, and
 * matches the local-first order map/basemap.ts and map/networkTiles.ts walk.
 *
 * The shared context comes last and only at or under its own zoom: it is the
 * z0-9 pyramid published once per sheet (features/OFFLINE_COVERAGE.md §6), so
 * it is what answers when a hiker pans out past the piece they hold.
 */
function localCandidates(z: number, x: number, y: number): string[] {
  const keys: string[] = []
  if (cells !== null) {
    for (const cell of cellsForTile(
      cells.index.cells,
      z,
      x,
      y,
      cells.index.seamMarginKm,
    )) {
      const key = cellPackageKey(cell.name, DEM_CELLS)
      if (cells.held.has(key)) keys.push(key)
    }
  }
  keys.push(DEM_PACKAGE.idbKey)
  if (
    cells !== null &&
    cells.index.context !== null &&
    z <= cells.index.contextZoom &&
    cells.held.has(DEM_CELLS.contextPackageKey)
  ) {
    keys.push(DEM_CELLS.contextPackageKey)
  }
  return keys
}

/**
 * One tile out of one downloaded archive, or undefined for a miss.
 *
 * An unreadable archive is a miss too, and its reader is dropped so the next
 * tile asks afresh - the SharedPromiseCache rule above. An abort is the
 * caller cancelling and propagates as itself.
 */
async function readLocal(
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

/** Abort must propagate as itself, never be misread as an archive miss -
 *  same matching (and reason for it) as basemap.ts. */
function isAbort(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as { name?: unknown }).name === 'AbortError'
  )
}

/**
 * maplibre-contour's GetTileFunction, local-first.
 *
 * The archive's tiles are quantized terrarium WebP (pipeline/export_dem.py)
 * where AWS serves terrarium PNG - both decode through the same
 * createImageBitmap path upstream of the elevation math, so which one
 * answered is invisible past this function, exactly as it should be:
 * quantization changed the precision (1 m), never the encoding contract.
 */
export async function demGetTile(
  url: string,
  abortController: AbortController,
): Promise<DemFetchResponse> {
  const match = url.match(TILE_URL)
  if (match === null) throw new Error(`Not a DEM tile URL: ${url}`)
  const [z, x, y] = [Number(match[1]), Number(match[2]), Number(match[3])]

  // Every archive this phone holds that could carry the tile, in
  // localCandidates' order. undefined is a tile none of them ever held -
  // beyond the ground downloaded, or above z13. A normal miss; only a held
  // tile short-circuits.
  for (const key of localCandidates(z, x, y)) {
    const local = await readLocal(key, z, x, y, abortController.signal)
    if (local !== undefined) return { data: new Blob([local]) }
  }

  // The network stays the SECOND resort, ahead of the local ancestor below,
  // and the order is the decision: a hiker with signal should get the sharp
  // tile AWS has, not a blurry one cropped out of their download. What changed
  // with the taper (#1088) is only what happens when this fails.
  try {
    const response = await fetch(url, { signal: abortController.signal })
    if (!response.ok) {
      // AWS Terrain Tiles is globally complete, so unlike the sparse vector
      // fallthrough there is no "absent is empty" case to translate: a bad
      // status is a failed tile, and failing it is what keeps the hillshade
      // honest - terrain.ts's contract is a missing layer, never a wrong one.
      throw new Error(`DEM tile ${z}/${x}/${y}: HTTP ${response.status}`)
    }
    return {
      data: await response.blob(),
      cacheControl: response.headers.get('cache-control') ?? undefined,
      expires: response.headers.get('expires') ?? undefined,
    }
  } catch (error) {
    if (isAbort(error)) throw error

    // LAST resort, and strictly additive: this replaces a throw, never a
    // working path. Offline past the deep-zoom band the taper keeps, the
    // choice is a coarser tile the hiker already downloaded or a blank square
    // - and a blank square on a phone with no signal is what export_dem.py's
    // publish gate calls "found at the worst possible moment".
    const coarse = await ancestorTile(z, x, y, abortController.signal).catch(() => null)
    if (coarse !== null) return { data: coarse }
    throw error
  }
}

/**
 * How far up the pyramid {@link ancestorTile} will look for a tile the archive
 * actually holds.
 *
 * Three levels is an 8x magnification, which is where a 10 m source stops
 * saying anything a hiker can read - past that the hillshade is a smooth blob
 * and pretending otherwise would be the confidently-wrong answer FEATURES.md
 * rules out. Below this ceiling a blurry answer beats a hole; above it, a hole
 * is the honest one.
 */
const MAX_ANCESTOR_STEPS = 3

/**
 * The archive's own tile for this coordinate, upscaled from a shallower zoom
 * it does hold - or null when it holds no usable ancestor.
 *
 * WHY THIS EXISTS. The corridor narrows with depth (#1088,
 * pipeline/export_dem.py's CORRIDOR_TAPER_MILES): the archive carries z13 for
 * 6 miles either side of the trail, z12 for 15, z11 for 30. MapLibre's
 * raster-dem source declares ONE maxzoom, so it cannot be told "z13 here, z12
 * out there" - it asks for z13 everywhere the camera is deep enough, and past
 * the narrow band the archive answers undefined. Without this, that miss goes
 * to the network, which is the one thing an offline map may not quietly do.
 *
 * NEAREST-NEIGHBOUR, DELIBERATELY, AND THIS IS NOT A QUALITY SETTING.
 * Terrarium encodes elevation as (R*256 + G + B/256) - 32768, so the red
 * channel is a 256 m band index. Smoothly interpolating between two pixels
 * either side of a band boundary averages the INDICES and invents an elevation
 * hundreds of metres wrong - the same reason lossy compression of terrarium
 * measured at 2,771 m RMSE (pipeline/LIGHT_DOWNLOAD.md). Replicating whole
 * pixels cannot do that: every output pixel is exactly some real input pixel's
 * triple. MapLibre's own overzoom is safe for the opposite reason - it decodes
 * to elevation first and interpolates there.
 */
async function ancestorTile(
  z: number,
  x: number,
  y: number,
  signal: AbortSignal,
): Promise<Blob | null> {
  if (typeof createImageBitmap !== 'function' || typeof OffscreenCanvas !== 'function')
    return null

  for (let step = 1; step <= MAX_ANCESTOR_STEPS && z - step >= 0; step += 1) {
    const scale = 2 ** step
    const [az, ax, ay] = [z - step, x >> step, y >> step]

    // Every archive again, re-asked at the shallower zoom (#1475). The
    // candidates are recomputed per step rather than reused: a z10 tile
    // covers four times the ground a z11 one does, so it can land in cells
    // the deep tile never touched, and at or under the context zoom the
    // shared archive joins the list. A phone holding a stretch and no whole
    // package has to reach this path to get anything at all past its own
    // deep-zoom band.
    let held: ArrayBuffer | undefined
    for (const key of localCandidates(az, ax, ay)) {
      held = await readLocal(key, az, ax, ay, signal)
      if (held !== undefined) break
    }
    if (held === undefined) continue

    // Which quadrant of the ancestor this coordinate is, in ancestor pixels.
    const source = await createImageBitmap(new Blob([held]))
    const span = source.width / scale
    const bitmap = await createImageBitmap(
      source,
      (x % scale) * span,
      (y % scale) * span,
      span,
      span,
      {
        resizeWidth: source.width,
        resizeHeight: source.height,
        resizeQuality: 'pixelated',
      },
    )
    source.close()

    const canvas = new OffscreenCanvas(bitmap.width, bitmap.height)
    const context = canvas.getContext('2d')
    if (context === null) {
      bitmap.close()
      return null
    }
    context.imageSmoothingEnabled = false
    context.drawImage(bitmap, 0, 0)
    bitmap.close()
    return await canvas.convertToBlob({ type: 'image/webp' })
  }
  return null
}

/** Test seam only - drops the archive memos and the shell's cell state so a
 *  test can observe a fresh read. Production never needs it. */
export function resetDemTilesForTests(): void {
  readers.clear()
  cells = null
}
