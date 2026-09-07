// Answers the map's network:// tile requests: the other organizations' trail
// lines, read out of the published PMTiles archive by byte range (#1257).
//
// WHAT THIS REPLACES, AND WHY
//
// Until #1257 these lines reached the map as one GeoJSON file, fetched whole,
// hashed whole, stored whole and handed to MapLibre whole
// (lib/nearbyTrailData.ts). On 2026-09-07 that file was promoted at
// 228,820,578 bytes - nationwide USFS trails, #1231 - and every phone that
// took it crashed its map, the renderer dying at 1.7 GB (#1254). The budget
// #1254 added stops a phone fetching such a file; it does not draw the trails.
// This does. The same lines, cut into z9-z14 vector tiles by
// export_nearby_trails.py's write_tiles, and read the way the hiking sheet
// has always been read: the archive's header and root directory once, then
// one leaf directory and one tile per request, each a ranged GET the bucket
// answers with the bytes asked for and nothing else. Measured on that day's
// archive: 132,995,363 bytes in the bucket, 388 bytes to open it. The file's
// weight is never the phone's again, however many organizations the export
// grows to hold.
//
// WHY A SCHEME AND NOT A URL
//
// The style could name the archive directly, as a pmtiles:// source through
// map/protocol.ts, and read exactly the same bytes. It does not, for the
// reason basemap.ts gives for the hiking sheet: WHICH archive answers a tile
// is a decision that will grow. Today the bucket is the only answer. #1257's
// second stage cuts these same tiles into downloadable cells beside the
// basemap's (cut_cells.py is written per family for exactly this), and a
// phone holding a cell should answer from it before spending a byte of a data
// plan - the local-first order basemap.ts already walks. With the resolution
// behind a scheme, that lands here and the style never moves: one vector
// source, one template, and this module decides per tile.
//
// THE ORDER OF ANSWERS
//
//   build has no bucket        -> empty tile. Nothing to ask.
//   manifest names no archive  -> empty tile, and the bucket is never asked
//                                 for a byte. A release exported before
//                                 write_tiles existed, or one held back with
//                                 its parent on a steward's reaches_hikers -
//                                 the "absent means none" every optional
//                                 artifact gets, decided the same way, off
//                                 latest.json.
//   archive holds the tile     -> its bytes.
//   archive never held it      -> empty tile. Outside every organization's
//                                 lines, which is most of the country.
//   the read fails             -> the error, rethrown, so MapLibre marks the
//                                 tile errored and asks again on the next
//                                 view change rather than caching a blank -
//                                 and the archive handle is dropped, below.
//
// NEVER MEMOISE A FAILURE, on basemap.ts's rule and for its reason: pmtiles'
// SharedPromiseCache stores the header promise before it settles and never
// evicts a rejection, so a PMTiles that once met a dead radio would answer
// from that rejection for the rest of the session. The handle is dropped on
// any failure and the next tile opens the archive afresh, which is what lets
// a launch that opened in a tunnel draw the network when it comes out. The
// manifest read is memoised on the same terms: only an answer that came from
// a readable manifest is kept.
//
// WHAT HOLDS THESE BYTES, said rather than implied (#197). The file this
// replaces was held to its published sha256; a tile read by range cannot be,
// because there is no whole to hash. What stands behind a tile is TLS to the
// bucket and the archive's ETag, which pmtiles carries across its own reads
// so a republish mid-session is a re-opened archive rather than one archive's
// directory over another's tiles. That is a weaker footing than the hash, and
// it is the footing every basemap tile and every contour on this map has
// always stood on: a hiker reads a nearby trail from a tile on the same terms
// they read the hills under it.
//
// NOTHING IS STORED. A tile lives in the browser's HTTP cache and nowhere
// else, so with no signal the map above the seam draws no nearby trails - the
// state before #1082 cached the whole file, and the state #1254's budget
// already left every phone in from 2026-09-07. lib/nearbyTrailData.ts
// deletes the copy earlier releases stored, and the Downloads window no
// longer lists a row for it, because a row would claim coverage this build
// does not have. The corridor-view sketch below the seam is stored as before.

import { addProtocol } from 'maplibre-gl'
import { PMTiles } from 'pmtiles'
import { DATA_CONFIGURED, dataUrl, NEARBY_TRAILS_TILES_KEY } from '../lib/config'
import { publishedSnapshot } from '../lib/dataManifest'

export const NETWORK_SCHEME = 'network'
export const NETWORK_TILES_URL = `${NETWORK_SCHEME}://{z}/{x}/{y}`

/** The one layer inside the archive - export_nearby_trails.py's TILES_LAYER,
 *  which every layer style.ts builds over the source names as its
 *  `source-layer`. A vector layer naming a source-layer the tiles do not carry
 *  draws nothing, silently, so the spelling is held from the pipeline side
 *  too (pipeline/tests/test_export_nearby_trails.py). */
export const NETWORK_TILES_LAYER = 'trails'

const TILE_URL = new RegExp(`^${NETWORK_SCHEME}://(\\d+)/(\\d+)/(\\d+)$`)

/** The published archive, opened for reading - and dropped on any failure,
 *  for the reason the header gives. */
let archive: PMTiles | null = null

function publishedArchive(): PMTiles {
  archive ??= new PMTiles(dataUrl(NEARBY_TRAILS_TILES_KEY))
  return archive
}

/** Whether latest.json names the archive: one read per session, kept only when
 *  the manifest actually answered. Read WITHOUT the asking tile's signal, so a
 *  tile the map cancels does not cancel the answer every other tile is
 *  waiting on. */
let published: Promise<boolean> | null = null

function archivePublished(): Promise<boolean> {
  if (published !== null) return published
  const attempt = publishedSnapshot().then(
    (snapshot) => {
      // A snapshot naming no artifact at all is an unreadable manifest -
      // offline, a 404, a refused origin - not an empty bucket. Answer "not
      // published" this once and ask again on the next tile.
      if (Object.keys(snapshot.hashes).length === 0) published = null
      return snapshot.hashes[NEARBY_TRAILS_TILES_KEY] !== undefined
    },
    (error: unknown) => {
      published = null
      throw error
    },
  )
  published = attempt
  return attempt
}

/** Abort is the map cancelling a tile it no longer wants - a normal event
 *  that must propagate as itself, never be misread as a failed archive.
 *  Matched on the name rather than instanceof: an abort arrives as a
 *  DOMException, whose place in the Error hierarchy varies by runtime. */
function isAbort(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as { name?: unknown }).name === 'AbortError'
  )
}

/** What MapLibre gets where there is nothing to draw: an empty tile, which the
 *  worker parses as a tile with no features. A fresh array each time - the
 *  worker takes ownership of the buffer it is handed. */
function emptyTile(): { data: Uint8Array } {
  return { data: new Uint8Array() }
}

/**
 * One network:// request answered, in the header's order. Exported for its
 * tests; MapLibre reaches it through {@link registerNetworkProtocol}.
 */
export async function loadNetworkTile(
  url: string,
  signal: AbortSignal,
): Promise<{ data: Uint8Array }> {
  const match = url.match(TILE_URL)
  if (match === null) throw new Error(`Not a ${NETWORK_SCHEME}:// tile URL: ${url}`)
  if (!DATA_CONFIGURED) return emptyTile()
  if (!(await archivePublished())) return emptyTile()

  const [z, x, y] = [Number(match[1]), Number(match[2]), Number(match[3])]
  try {
    const tile = await publishedArchive().getZxy(z, x, y, signal)
    // undefined is pmtiles' word for "this archive never held that tile" -
    // ground with no organization's trail on it, or a zoom outside the cut.
    return tile === undefined ? emptyTile() : { data: new Uint8Array(tile.data) }
  } catch (error) {
    if (isAbort(error)) throw error
    archive = null
    throw error
  }
}

let registered = false

/**
 * Registers the network:// handler. Idempotent, and called by MapView before
 * every map build, the same way as registerBasemapProtocol() - a second
 * addProtocol for the same scheme would silently replace the first
 * mid-session, which is exactly the class of surprise that call exists to
 * prevent.
 */
export function registerNetworkProtocol(): void {
  if (registered) return
  addProtocol(NETWORK_SCHEME, (params, abortController) =>
    loadNetworkTile(params.url, abortController.signal),
  )
  registered = true
}

/** Test seam only - drops the registration guard and both memos so a test can
 *  observe a fresh registration and a fresh manifest read. Production never
 *  needs it. */
export function resetNetworkTilesForTests(): void {
  registered = false
  archive = null
  published = null
}
