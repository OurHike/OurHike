// Building the trail index and placing the waypoints on it, off the thread a
// hiker is tapping (#1192).
//
// WHAT THIS COSTS, AND WHERE IT WAS BEING PAID
//
// A returning hiker's launch used to read the release out of IndexedDB and,
// in one render, JSON.parse 11.5 MB of trails.geojson, index 216,759 vertices
// and run `mileOnTrail` over every stored waypoint - 16,949 of them since
// #1095 shipped the other organizations' waypoints into the same list. On a
// 4x-throttled phone profile, measured 2026-09-02 against the live release:
// 783 ms for the parse and the index, then ONE task of 13,078 ms for the
// placement, during which a tap on the Today tab waited 14,557 ms to be
// accepted. That is the "unresponsive for about ten seconds" the bug report
// describes, and none of it reached a pixel while it ran.
//
// SO IT MOVES OFF THE UI THREAD, THE WAY THE PINS AND THE HASHING DID
//
// The same shape of work map/poiIconImages.ts and lib/sha256Rpc.ts already
// hand to a worker: no DOM, no map, arithmetic over bytes already on the
// phone. The worker parses both files, builds the index, places whatever
// waypoints still need placing, and hands the result back as typed arrays by
// transfer (lib/trailPosition.ts's serialized form) - so the main thread
// receives 250,000 vertices for the cost of rebuilding a cell map from three
// arrays, a few milliseconds, and never parses the lines at all.
//
// THREE THINGS MAKE THE WORK SMALLER BEFORE IT IS MOVED, and each is measured
// in #1192: the index buckets in two dimensions (six times fewer haversines
// per waypoint); on the pipeline's axis (trail_miles.json) a waypoint's
// published mile IS its place on the index, so nothing is placed by search at
// all; and the built index is cached in IndexedDB per release, so the parse is
// paid once per download rather than once per launch.
//
// WHERE THERE IS NO WORKER, the same build runs here in slices, yielding to
// the event loop between them (lib/yieldToMain.ts). That path is for jsdom,
// where the suite runs, and for a WebView old enough to have no Worker - which
// is not a WebView this app can draw a map for (map/mapWorker.ts), so it is
// a fallback in the honest sense: reachable, tested, and not where any phone
// this app is for should ever be.
//
// The order of what the main thread learns is the honest-unknown posture: the
// screen renders with every mile unknown and fills in when the worker
// answers, rather than holding the screen until it can claim to know.

import { get, set } from 'idb-keyval'
import type { FeatureCollection } from 'geojson'
import {
  cellKey,
  collectTrailParts,
  deserializeTrailIndex,
  fillPart,
  indexTrailParts,
  isSerializedTrailIndex,
  mileOnTrail,
  serializeTrailIndex,
  trailIndexBuffers,
  type SerializedTrailIndex,
  type TrailIndex,
  type TrailParts,
} from './trailPosition'
import { parseTrailMiles } from './trailMiles'
import { yieldToMain } from './yieldToMain'

/**
 * What a build needs, and nothing a worker cannot be handed: two Blob handles
 * (structured-cloneable, and read where the parse happens) and the waypoints
 * packed as triples of lon, lat and published mile (NaN where a waypoint has
 * none), which is one transferable array rather than 16,949 objects.
 */
export interface TrailIndexRequest {
  trails: Blob
  trailMiles: Blob | null
  /** `[lon, lat, mile | NaN]` per waypoint, in the order the caller keeps them. */
  pois: Float64Array
  /**
   * What identifies the release these bytes belong to, for the cache - the
   * published hash of trails.geojson from the phone's own release record, or
   * null for a store written before that record existed (#919), which is
   * simply "no cache" rather than a stale one.
   */
  trailsHash: string | null
}

export interface TrailIndexBuilt {
  index: SerializedTrailIndex
  /**
   * One mile per waypoint in the request's order, NaN where it has none.
   *
   * On the pipeline's axis this is the published mile handed straight back,
   * because it is already the position on this index. Otherwise it is the
   * nearest-vertex search every waypoint used to be run through on the main
   * thread, run here instead - and the {@link MAX_OFF_TRAIL_MILES} gate holds
   * for it exactly as it does for a GPS fix.
   */
  poiMiles: Float64Array
  /**
   * The anchors' successor as a consistency check (#1192): on the pipeline's
   * axis, how far a sample of waypoints' published miles sit from where the
   * index would have placed them by search. Null off that axis, where the
   * search IS the answer and there is nothing to check it against.
   *
   * The two files were measured on the same calibrated axis, so the honest
   * expectation is a drift of hundredths of a mile - a waypoint a few hundred
   * feet off the centerline projects onto it slightly obliquely. A large
   * drift means the lines and the miles are not the pair they claim to be,
   * which the download refuses by hash and nothing on the phone can otherwise
   * see. lib/useTrailData.ts says so in the console; nothing is hidden or
   * corrected on its strength, because a check that quietly overrode the
   * published number would be a second axis with extra steps.
   */
  axisDrift: AxisDrift | null
}

export interface AxisDrift {
  /** How many waypoints were compared. */
  sampled: number
  /** The largest |published - placed| among them, in miles. */
  maxMiles: number
}

/** How many waypoints with a published mile the drift check compares - spread
 *  evenly across the list, so the sample walks the whole trail rather than
 *  the first shelters north of Springer. Two hundred searches is ~0.1 s of a
 *  worker's time on the 2-D grid (#1192's measurement) and it runs once per
 *  release, not per launch. */
export const AXIS_DRIFT_SAMPLE = 200

/**
 * The largest disagreement between published and placed miles over a sample
 * (see {@link TrailIndexBuilt.axisDrift}). Only meaningful on the pipeline's
 * axis; null otherwise. A waypoint the search cannot place (past the gate) is
 * skipped rather than counted as infinite drift - a lean-to in the
 * Adirondacks with a published mile would be a pipeline bug of its own, and
 * this is not the check for it.
 */
export function axisDrift(index: TrailIndex, pois: Float64Array): AxisDrift | null {
  if (!index.onPipelineAxis) return null
  const count = pois.length / POI_STRIDE
  const step = Math.max(1, Math.floor(count / AXIS_DRIFT_SAMPLE))
  let sampled = 0
  let maxMiles = 0
  for (let i = 0; i < count && sampled < AXIS_DRIFT_SAMPLE; i += step) {
    const published = pois[i * POI_STRIDE + 2]
    if (Number.isNaN(published)) continue
    const placed = mileOnTrail(index, {
      lon: pois[i * POI_STRIDE],
      lat: pois[i * POI_STRIDE + 1],
    })
    if (placed === null) continue
    sampled += 1
    const drift = Math.abs(published - placed)
    if (drift > maxMiles) maxMiles = drift
  }
  return { sampled, maxMiles }
}

/** Three numbers per waypoint - see {@link TrailIndexRequest.pois}. */
export const POI_STRIDE = 3

/** Packs waypoints for the request. `mile` may be absent, which packs as NaN. */
export function packPois(
  pois: ReadonlyArray<{ lon: number; lat: number; mile?: number }>,
): Float64Array {
  const packed = new Float64Array(pois.length * POI_STRIDE)
  for (let i = 0; i < pois.length; i += 1) {
    packed[i * POI_STRIDE] = pois[i].lon
    packed[i * POI_STRIDE + 1] = pois[i].lat
    packed[i * POI_STRIDE + 2] = pois[i].mile ?? NaN
  }
  return packed
}

/**
 * A cheap content fingerprint over the packed waypoints, for the cache below.
 * POIs arrive as eight published files (useTrailData.ts's `readTheRest`),
 * none of which `TrailIndexRequest.trailsHash` covers - so a coordinate or
 * published-mile correction that lands with the trail lines and the waypoint
 * count both unchanged (an ordinary dated fix in this pipeline's history, not
 * a new download) needs its own signal, or the cache serves the pre-fix
 * placement indefinitely.
 *
 * Not a security boundary - a collision costs a stale cache hit, which the
 * cache already treats as safe to have - so a 32-bit FNV-1a over the raw
 * bytes is enough, not sha256Rpc's streaming digest built for gigabyte
 * archives.
 */
export function poiFingerprint(pois: Float64Array): number {
  const bytes = new Uint8Array(pois.buffer, pois.byteOffset, pois.byteLength)
  let hash = 0x811c9dc5
  for (let i = 0; i < bytes.length; i += 1) {
    hash ^= bytes[i]
    hash = Math.imul(hash, 0x01000193)
  }
  return hash >>> 0
}

/** Every mile a build answered for the waypoints, in their order - NaN read
 *  as "none", which is how the rest of the shell already spells a waypoint
 *  it cannot place. */
export function placedMiles(
  index: TrailIndex,
  pois: Float64Array,
  from = 0,
  to = pois.length / POI_STRIDE,
  into = new Float64Array(pois.length / POI_STRIDE),
): Float64Array {
  for (let i = from; i < to; i += 1) {
    const published = pois[i * POI_STRIDE + 2]
    if (index.onPipelineAxis) {
      into[i] = published
      continue
    }
    const mile = mileOnTrail(index, {
      lon: pois[i * POI_STRIDE],
      lat: pois[i * POI_STRIDE + 1],
    })
    into[i] = mile === null ? NaN : mile
  }
  return into
}

async function readParts(request: TrailIndexRequest): Promise<TrailParts> {
  const [trailsText, milesText] = await Promise.all([
    request.trails.text(),
    request.trailMiles?.text() ?? Promise.resolve(null),
  ])
  // A throw from either parse lands with the caller as "no index", the way a
  // truncated download always has (lib/useTrailData.ts's readTheRest): no
  // index, no miles, and a message rather than an unhandled rejection.
  const collection = JSON.parse(trailsText) as FeatureCollection
  const miles = milesText === null ? null : parseTrailMiles(milesText)
  return collectTrailParts(collection, miles?.byId ?? null)
}

/**
 * The whole build, in one go. What the worker runs.
 */
export async function buildTrailIndexNow(
  request: TrailIndexRequest,
): Promise<TrailIndexBuilt> {
  const index = indexTrailParts(await readParts(request))
  return {
    index: serializeTrailIndex(index),
    poiMiles: placedMiles(index, request.pois),
    axisDrift: axisDrift(index, request.pois),
  }
}

/** How many vertices or waypoints a main-thread slice works through before
 *  yielding. Reasoned, not measured on a phone: a slice of vertices is a few
 *  hundred microseconds of copying and cell arithmetic unthrottled, a slice
 *  of waypoints on the phone's own axis is ~565 haversines each (#1192's
 *  measurement of the 2-D grid), so both stay well under a frame at 4x. */
const VERTEX_SLICE = 20_000
const POI_SLICE = 200

/**
 * The same build, on the calling thread, in slices - the fallback for a
 * browser with no Worker. The parse itself cannot be sliced; everything after
 * it can, and is.
 */
export async function buildTrailIndexInSlices(
  request: TrailIndexRequest,
): Promise<TrailIndexBuilt> {
  const { parts, tread, onPipelineAxis } = await readParts(request)
  await yieldToMain()

  const count = parts.reduce((total, part) => total + part.coords.length, 0)
  const lons = new Float64Array(count)
  const lats = new Float64Array(count)
  const miles = new Float64Array(count)
  const partStarts: number[] = []
  let offset = 0
  let feetBefore = 0
  let sinceYield = 0
  for (const part of parts) {
    partStarts.push(offset)
    fillPart(part, offset, lons, lats, miles, feetBefore)
    offset += part.coords.length
    feetBefore = onPipelineAxis ? 0 : miles[offset - 1] * 5280
    sinceYield += part.coords.length
    if (sinceYield >= VERTEX_SLICE) {
      sinceYield = 0
      await yieldToMain()
    }
  }

  const cells = await cellsInSlices(lons, lats)
  let totalMiles = 0
  for (let i = 0; i < count; i += 1) if (miles[i] > totalMiles) totalMiles = miles[i]

  const treadCount = tread.reduce((total, run) => total + run.length, 0)
  const treadLons = new Float64Array(treadCount)
  const treadLats = new Float64Array(treadCount)
  let at = 0
  for (const run of tread) {
    for (const [lon, lat] of run) {
      treadLons[at] = lon
      treadLats[at] = lat
      at += 1
    }
    sinceYield += run.length
    if (sinceYield >= VERTEX_SLICE) {
      sinceYield = 0
      await yieldToMain()
    }
  }
  const treadCells = await cellsInSlices(treadLons, treadLats)

  const index: TrailIndex = {
    lons,
    lats,
    miles,
    cells,
    totalMiles,
    partStarts,
    tread: { lons: treadLons, lats: treadLats, cells: treadCells },
    onPipelineAxis,
  }

  const poiCount = request.pois.length / POI_STRIDE
  const poiMiles = new Float64Array(poiCount)
  for (let from = 0; from < poiCount; from += POI_SLICE) {
    placedMiles(index, request.pois, from, Math.min(from + POI_SLICE, poiCount), poiMiles)
    await yieldToMain()
  }

  return {
    index: serializeTrailIndex(index),
    poiMiles,
    axisDrift: axisDrift(index, request.pois),
  }
}

async function cellsInSlices(
  lons: Float64Array,
  lats: Float64Array,
): Promise<Map<number, ArrayLike<number>>> {
  const cells = new Map<number, number[]>()
  for (let from = 0; from < lons.length; from += VERTEX_SLICE) {
    const to = Math.min(from + VERTEX_SLICE, lons.length)
    for (let i = from; i < to; i += 1) {
      const key = cellKey(lats[i], lons[i])
      const cell = cells.get(key)
      if (cell === undefined) cells.set(key, [i])
      else cell.push(i)
    }
    await yieldToMain()
  }
  return cells
}

// ---------------------------------------------------------------------------
// The cache: one built index per release, in IndexedDB.

/** Where the built index lives. One slot, overwritten: a phone holds one
 *  release at a time, and a cache for a release it no longer has is bytes
 *  nobody will read. */
export const TRAIL_INDEX_CACHE_KEY = 'ourhike:trail-index'

interface CachedTrailIndex {
  /** What the entry was built from. All three have to match for a hit: the
   *  lines by hash, and the waypoints by count and by whether the miles
   *  sidecar was there - a release that gained its sidecar on re-download
   *  builds the same lines onto a different axis. */
  trailsHash: string
  poiCount: number
  /** See {@link poiFingerprint} - catches a same-count content change that
   *  trailsHash alone cannot, because trailsHash never covers the POI files. */
  poiFingerprint: number
  withMiles: boolean
  index: SerializedTrailIndex
  poiMiles: Float64Array
  axisDrift: AxisDrift | null
}

function cachedIndexFor(
  request: TrailIndexRequest,
  stored: unknown,
  fingerprint: number,
): TrailIndexBuilt | null {
  if (request.trailsHash === null) return null
  if (typeof stored !== 'object' || stored === null) return null
  const entry = stored as Partial<CachedTrailIndex>
  if (
    entry.trailsHash !== request.trailsHash ||
    entry.poiCount !== request.pois.length / POI_STRIDE ||
    entry.poiFingerprint !== fingerprint ||
    entry.withMiles !== (request.trailMiles !== null) ||
    !isSerializedTrailIndex(entry.index) ||
    !(entry.poiMiles instanceof Float64Array) ||
    entry.poiMiles.length !== entry.poiCount ||
    entry.axisDrift === undefined
  ) {
    return null
  }
  return { index: entry.index, poiMiles: entry.poiMiles, axisDrift: entry.axisDrift }
}

/**
 * The built index for this release, from the cache where it holds one and
 * built (and cached) otherwise. `build` is which build to run - the whole
 * thing at once on a worker, in slices on a thread that must not be held.
 *
 * A cache that cannot be read or written is no cache: the build still
 * answers, and a phone with a broken store loses the shortcut and nothing
 * else. Never a thrown error over a cache.
 */
export async function loadTrailIndex(
  request: TrailIndexRequest,
  build: (request: TrailIndexRequest) => Promise<TrailIndexBuilt> = buildTrailIndexNow,
): Promise<TrailIndexBuilt> {
  let stored: unknown
  try {
    stored = await get(TRAIL_INDEX_CACHE_KEY)
  } catch {
    stored = undefined
  }
  const fingerprint = poiFingerprint(request.pois)
  const cached = cachedIndexFor(request, stored, fingerprint)
  if (cached !== null) return cached

  const built = await build(request)
  if (request.trailsHash !== null) {
    const entry: CachedTrailIndex = {
      trailsHash: request.trailsHash,
      poiCount: request.pois.length / POI_STRIDE,
      poiFingerprint: fingerprint,
      withMiles: request.trailMiles !== null,
      index: built.index,
      poiMiles: built.poiMiles,
      axisDrift: built.axisDrift,
    }
    try {
      await set(TRAIL_INDEX_CACHE_KEY, entry)
    } catch {
      // Storage full, a private window, a store another tab is upgrading:
      // the index is built and handed back regardless.
    }
  }
  return built
}

// ---------------------------------------------------------------------------
// The worker boundary.

export type TrailIndexWorkerRequest = { kind: 'build'; request: TrailIndexRequest }
export type TrailIndexWorkerResponse =
  { kind: 'built'; built: TrailIndexBuilt } | { kind: 'failed'; message: string }

/**
 * What the worker does with a request: the cached-or-built index, posted
 * back with its buffers transferred. Separated from the worker entry so it
 * can be driven through a fake channel in jsdom, where a real worker cannot
 * run - lib/sha256Rpc.ts's own arrangement.
 */
export function createTrailIndexRequestHandler(
  post: (message: TrailIndexWorkerResponse, transfer: ArrayBuffer[]) => void,
): (message: TrailIndexWorkerRequest) => Promise<void> {
  return async (message) => {
    try {
      const built = await loadTrailIndex(message.request)
      post({ kind: 'built', built }, [
        ...trailIndexBuffers(built.index),
        built.poiMiles.buffer as ArrayBuffer,
      ])
    } catch (error) {
      post(
        {
          kind: 'failed',
          message: error instanceof Error ? error.message : String(error),
        },
        [],
      )
    }
  }
}

/** jsdom has no Worker, and neither does a browser old enough that MapLibre
 *  cannot draw for it either. Asked as a capability rather than assumed. */
function workerAvailable(): boolean {
  return typeof Worker !== 'undefined'
}

function buildInWorker(request: TrailIndexRequest): Promise<TrailIndexBuilt> {
  return new Promise((resolve, reject) => {
    let worker: Worker
    try {
      worker = new Worker(new URL('./trailIndexWorker.ts', import.meta.url), {
        type: 'module',
      })
    } catch (error) {
      // A worker that cannot be constructed at all - a Content-Security-Policy
      // that refuses one, an asset that did not ship. The caller falls back to
      // slicing the build on this thread; a launch with no index at all is the
      // one outcome this file must never produce on its own.
      reject(error instanceof Error ? error : new Error(String(error)))
      return
    }

    let settled = false
    worker.onmessage = (event: MessageEvent<TrailIndexWorkerResponse>) => {
      settled = true
      worker.terminate()
      if (event.data.kind === 'built') resolve(event.data.built)
      else reject(new Error(event.data.message))
    }
    // A worker that fails to load or throws on its way through has to end
    // with an index on the phone, not with a map that cannot say where a
    // hiker is. The caller's fallback is the same slice-on-this-thread path.
    worker.onerror = (event) => {
      if (settled) return
      settled = true
      worker.terminate()
      reject(new Error(event.message || 'trail index worker failed'))
    }
    worker.postMessage({ kind: 'build', request } satisfies TrailIndexWorkerRequest)
  })
}

/**
 * The built index and the waypoints' miles, for the shell: on a worker where
 * there is one, in slices on this thread where there is not - and in slices
 * on this thread if the worker fails, because the worker failing must cost a
 * launch its shortcut and not its index.
 *
 * Always resolves to a live {@link TrailIndex}: the serialized form is the
 * wire and the cache, and nothing outside this module and the worker ever
 * sees one.
 */
export async function resolveTrailIndex(
  request: TrailIndexRequest,
): Promise<{ index: TrailIndex; poiMiles: Float64Array; axisDrift: AxisDrift | null }> {
  let built: TrailIndexBuilt
  if (workerAvailable()) {
    try {
      built = await buildInWorker(request)
    } catch {
      built = await loadTrailIndex(request, buildTrailIndexInSlices)
    }
  } else {
    built = await loadTrailIndex(request, buildTrailIndexInSlices)
  }
  return {
    index: deserializeTrailIndex(built.index),
    poiMiles: built.poiMiles,
    axisDrift: built.axisDrift,
  }
}
