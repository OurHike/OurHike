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
}

/** Test seam only - drops the archive memo so a test can observe a fresh
 *  read. Production never needs it. */
export function resetDemTilesForTests(): void {
  archive = null
}
