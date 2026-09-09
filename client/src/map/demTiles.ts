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
 * The downloaded DEM package, wrapped for reading - and dropped on any
 * failure, for the reason basemap.ts documents: pmtiles' SharedPromiseCache
 * never evicts a rejected header promise, so keeping the instance would
 * keep answering from a stale error after a mid-session download completes.
 */
let archive: PMTiles | null = null

function packageArchive(): PMTiles {
  archive ??= new PMTiles(new IndexedDbArchiveSource(DEM_PACKAGE.idbKey))
  return archive
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

  try {
    const local = await packageArchive().getZxy(z, x, y, abortController.signal)
    // undefined is a tile the archive never held - beyond the corridor, or
    // above z13. A normal miss; only a held tile short-circuits.
    if (local !== undefined) return { data: new Blob([local.data]) }
  } catch (error) {
    if (isAbort(error)) throw error
    archive = null
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
    const held = await packageArchive().getZxy(z - step, x >> step, y >> step, signal)
    if (held === undefined) continue

    // Which quadrant of the ancestor this coordinate is, in ancestor pixels.
    const source = await createImageBitmap(new Blob([held.data]))
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

/** Test seam only - drops the archive memo so a test can observe a fresh
 *  read. Production never needs it. */
export function resetDemTilesForTests(): void {
  archive = null
}
