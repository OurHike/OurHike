// The hiking sheet in pieces: the 1°×1° cells pipeline/cut_cells.py cuts, as
// the phone reads them (#557, #558, features/OFFLINE_COVERAGE.md).
//
// Two layers, and this module keeps them apart the way the doc does. The CELL
// is the unit that is built, versioned, downloaded and resumed, and nobody
// sees one. What a hiker takes is a SET of them - today the cells under the
// hike lib/plannedHike.ts already stores, derived from two numbers they have
// already given rather than picked off a list. Named pieces ("Virginia",
// "Harriman") are the doc's open question 2, the maintainer's to answer, and
// nothing here invents a name.
//
// THREE THINGS THIS FILE IS THE ONE HOME FOR
//
//   - what the published index looks like, and what a phone refuses to read
//     off it (`parseCellIndex`). The index is bucket data, so it is checked
//     field by field the way lib/dataManifest.ts checks a manifest, and one
//     bad row refuses the whole list: a partial index would price a stretch
//     against pieces it cannot name;
//   - the geometry - which cells a point, a tile or a walk touches. A cell is
//     an axis-aligned rectangle in lon/lat, so all of it is rectangle tests,
//     none of it needs an archive open, and the tile routing mirrors the
//     cutter's own (`cells_for_tile`) so a tile the pipeline put in a cell is
//     a tile this looks for there;
//   - the store - the last verified copy of the index, kept in IndexedDB so a
//     phone with a stretch on it answers "is here covered" with no signal.
//     lib/nearbyTrailData.ts's whole-artifact-or-nothing cache, for the same
//     reason.
//
// WHICH CELLS THE PHONE HOLDS IS DELIBERATELY NOT RECORDED HERE A SECOND TIME.
// Each cell is an ordinary package to lib/archiveStore.ts - its own key, its
// own completion marker, its own resume, its own published hash - so "held" is
// the marker's answer, read through the same hook every sheet's status comes
// from (lib/useArchiveDownload.ts). A list kept beside the markers would be a
// second source of truth to drift from them, and §10 of the doc gets the
// better resume for free: a publish landing mid-download costs one ~7 MB cell
// rather than the 534 MB sheet.

import { get, set } from 'idb-keyval'
import { useEffect, useState } from 'react'
import {
  BASEMAP_CELLS_KEY,
  DATA_CONFIGURED,
  dataUrl,
  NEARBY_TRAILS_CELLS_KEY,
  TRAIL_GRAPH_CELLS_KEY,
} from './config'
import { publishedHash } from './dataManifest'
import { sha256Of } from './trailData'
import { useOnline } from './useOnline'
import type { PublishedSizes } from './usePublishedSizes'

/** `[west, south, east, north]`, in degrees. */
export type Bounds = readonly [west: number, south: number, east: number, north: number]

export interface CoverageCell {
  /** The south-west corner in the USGS quad convention: `n34w085`. */
  name: string
  /** The flat bucket key of its archive, as `latest.json` names it. */
  key: string
  /**
   * Core bounds. The 3 km seam margin the archive carries past these is
   * generosity in the bytes and never a promise in the metadata
   * (cut_cells.py) - so nothing here treats a margin as coverage.
   */
  bounds: Bounds
}

export interface CellIndex {
  cellDegrees: number
  seamMarginKm: number
  contextZoom: number
  /** The shared context archive's key - everything through `contextZoom`,
   *  published once per sheet - or null where the cut had nothing at or
   *  under that zoom to publish. */
  context: string | null
  cells: readonly CoverageCell[]
}

/**
 * One family of cells: everything about a cut that is a NAME rather than
 * geometry (#1257 stage 2). The geometry below is family-neutral - every
 * family is cut on the same graticule by the same cutter - but each family
 * has its own published index, its own store record for it, and its own
 * IndexedDB keys for the archives, because two families' cells share a cell
 * name (`n41w075` is the same ground whichever sheet holds it) and a single
 * key space would let the basemap's Harriman overwrite the network's.
 */
export interface CellFamily {
  /** The published index's bucket key (lib/config.ts). */
  indexKey: string
  /** Where a cell's archive lives in IndexedDB: `${packagePrefix}${name}`,
   *  under the same suffix scheme every package's download records derive
   *  from. */
  packagePrefix: string
  /** The shared context archive's key. Fetched with the first piece and
   *  never offered as a decision - it is what makes a piece legible when a
   *  hiker zooms out past it (OFFLINE_COVERAGE.md §6). */
  contextPackageKey: string
  /** The last verified copy of the index, whole, so a phone with a stretch
   *  on it can place itself with no signal. */
  indexStoreKey: string
}

/** The hiking sheet's cells - the first family, and the default everywhere a
 *  family is not named, so the code written before there were two reads as
 *  it did. */
export const BASEMAP_CELLS: CellFamily = {
  indexKey: BASEMAP_CELLS_KEY,
  packagePrefix: 'ourhike:basemap-cell:',
  contextPackageKey: 'ourhike:basemap-context',
  indexStoreKey: 'ourhike:basemap-cells-index',
}

/** The other organizations' trail lines as tiles, cut into the same cells
 *  (#1257 stage 2, config.ts's NEARBY_TRAILS_CELLS_KEY) - what
 *  map/networkTiles.ts asks before the bucket. Its index carries no context
 *  today (the cut is made one below the tiles' minimum zoom), and nothing
 *  here assumes that: a context published later is read like the basemap's. */
export const NETWORK_CELLS: CellFamily = {
  indexKey: NEARBY_TRAILS_CELLS_KEY,
  packagePrefix: 'ourhike:network-cell:',
  contextPackageKey: 'ourhike:network-context',
  indexStoreKey: 'ourhike:network-cells-index',
}

/** The junction graph in the same cells (#1257 stage 3, config.ts's
 *  TRAIL_GRAPH_CELLS_KEY) - JSON shards a phone parses rather than archives it
 *  reads by range, so the two package keys here name nothing: a graph cell is
 *  kept by lib/trailGraphStore.ts under its own keys, never by
 *  lib/archiveStore.ts. The index, the geometry and `cellsAlong` are the same
 *  as every other family's, which is the point of it being one. */
export const GRAPH_CELLS: CellFamily = {
  indexKey: TRAIL_GRAPH_CELLS_KEY,
  packagePrefix: 'ourhike:graph-cell:',
  contextPackageKey: 'ourhike:graph-context',
  indexStoreKey: 'ourhike:graph-cells-index',
}

/** The basemap family's prefix, kept under its old name for the callers and
 *  tests written when it was the only one. */
export const CELL_PACKAGE_PREFIX = BASEMAP_CELLS.packagePrefix

export function cellPackageKey(name: string, family: CellFamily = BASEMAP_CELLS): string {
  return `${family.packagePrefix}${name}`
}

/** The basemap family's context key, likewise. */
export const CONTEXT_PACKAGE_KEY = BASEMAP_CELLS.contextPackageKey

/**
 * Every cell and the shared context as download requests
 * (lib/useArchiveDownload.ts's shape), so a shell can register a whole family
 * the moment its index is known and read the markers on mount like every
 * sheet's. Empty for no index, which is every phone on a release without
 * that family's cells. Registering starts nothing.
 */
export function cellDownloadRequests(
  index: CellIndex | null,
  family: CellFamily,
): { packageKey: string; url: string; artifactKey: string }[] {
  if (index === null) return []
  const requests = index.cells.map((cell) => ({
    packageKey: cellPackageKey(cell.name, family),
    url: dataUrl(cell.key),
    artifactKey: cell.key,
  }))
  if (index.context !== null) {
    requests.push({
      packageKey: family.contextPackageKey,
      url: dataUrl(index.context),
      artifactKey: index.context,
    })
  }
  return requests
}

/**
 * How far past the hike's own ground a stretch reaches, in kilometres - the
 * client's share of #552's non-negotiable that a wrong answer must not cost
 * somebody map where they are walking. A cell whose edge lies within this
 * distance of the walk is taken too, so a hiker who walks past their planned
 * end, or takes a blue-blazed bail-out toward a road, is still on a cell they
 * hold.
 *
 * @unvalidated 3 km is picked, not found, and it is the cutter's own
 * SEAM_MARGIN_KM deliberately: the data-side margin and the client-side one
 * then describe the same ground, so the first cell past a seam is on the
 * phone exactly where the held cell's own tiles run out. What would settle it:
 * how far past a planned end hikers actually walk, measured once #558 has
 * shipped and there is behaviour to measure - which is the same measurement
 * cut_cells.py says would settle its number.
 */
export const STRETCH_MARGIN_KM = 3

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)

function boundsOf(raw: unknown): Bounds | null {
  if (!Array.isArray(raw) || raw.length !== 4 || !raw.every(isFiniteNumber)) return null
  const [west, south, east, north] = raw as number[]
  if (!(west < east) || !(south < north)) return null
  return [west, south, east, north]
}

/**
 * The published index, or null where these bytes are not one.
 *
 * Whole or nothing, deliberately. A row with no key is a piece that cannot be
 * fetched; a row with no bounds is one that cannot be placed; keeping the rest
 * would offer a stretch missing a cell in its middle and call it complete.
 */
export function parseCellIndex(raw: unknown): CellIndex | null {
  if (typeof raw !== 'object' || raw === null) return null
  const record = raw as Record<string, unknown>
  const cellDegrees = record.cell_degrees
  const seamMarginKm = record.seam_margin_km
  const contextZoom = record.context_zoom
  const context = record.context
  if (!isFiniteNumber(cellDegrees) || cellDegrees <= 0) return null
  if (!isFiniteNumber(seamMarginKm) || seamMarginKm < 0) return null
  if (!isFiniteNumber(contextZoom) || contextZoom < 0) return null
  if (context !== null && typeof context !== 'string') return null
  if (!Array.isArray(record.cells)) return null

  const cells: CoverageCell[] = []
  for (const entry of record.cells) {
    if (typeof entry !== 'object' || entry === null) return null
    const { name, key, bounds } = entry as Record<string, unknown>
    const box = boundsOf(bounds)
    if (typeof name !== 'string' || name === '') return null
    if (typeof key !== 'string' || key === '') return null
    if (box === null) return null
    cells.push({ name, key, bounds: box })
  }

  return {
    cellDegrees,
    seamMarginKm,
    contextZoom,
    context: context === null || context === '' ? null : context,
    cells,
  }
}

/** Half-open on the east and north edges, so a point on a shared boundary
 *  belongs to exactly one cell - the same convention the graticule uses. */
export function boundsContain(bounds: Bounds, lon: number, lat: number): boolean {
  const [west, south, east, north] = bounds
  return lon >= west && lon < east && lat >= south && lat < north
}

export function boundsOverlap(a: Bounds, b: Bounds): boolean {
  return a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1]
}

function tileLatitude(y: number, tiles: number): number {
  const t = Math.PI - (2 * Math.PI * y) / tiles
  return (180 / Math.PI) * Math.atan(Math.sinh(t))
}

/**
 * A slippy tile's bounds as an exact lon/lat rectangle.
 *
 * Exact rather than approximate, for the reason cut_cells.py gives: web
 * mercator is monotonic and axis-aligned in both axes, so the tile's corners
 * map to the rectangle's corners and there is nothing to sample.
 */
export function tileBounds(z: number, x: number, y: number): Bounds {
  const tiles = 2 ** z
  const west = (x / tiles) * 360 - 180
  const east = ((x + 1) / tiles) * 360 - 180
  return [west, tileLatitude(y + 1, tiles), east, tileLatitude(y, tiles)]
}

/** Mean meridional degree, the cutter's own constant - good to a few parts in
 *  a thousand over any latitude these sheets cover, far inside a 3 km margin. */
const KM_PER_DEGREE_LAT = 111

/**
 * A margin in degrees at the latitude it applies, mirroring the cutter's
 * `margin_degrees`: longitude degrees shrink with cos(lat), so the widest of
 * the rectangle's own latitudes is used - erring toward more map, the only
 * direction #552 lets anything err in.
 */
export function marginDegrees(
  south: number,
  north: number,
  marginKm: number,
): { dLon: number; dLat: number } {
  const dLat = marginKm / KM_PER_DEGREE_LAT
  const worst = Math.max(Math.abs(south), Math.abs(north))
  const dLon =
    marginKm / (KM_PER_DEGREE_LAT * Math.max(Math.cos((worst * Math.PI) / 180), 0.01))
  return { dLon, dLat }
}

export function widen(bounds: Bounds, marginKm: number): Bounds {
  const { dLon, dLat } = marginDegrees(bounds[1], bounds[3], marginKm)
  return [bounds[0] - dLon, bounds[1] - dLat, bounds[2] + dLon, bounds[3] + dLat]
}

/** The cells whose core bounds hold a point - one, or none off the cut. */
export function cellsAt(
  cells: readonly CoverageCell[],
  lon: number,
  lat: number,
): CoverageCell[] {
  return cells.filter((cell) => boundsContain(cell.bounds, lon, lat))
}

/**
 * Every cell whose archive may hold a tile: the cells the tile overlaps once
 * widened by the seam margin - the exact routing `cut_cells.py` performed, so
 * a tile it wrote into a cell is a tile this looks for there. More than one
 * near a seam, by construction; any held one answers.
 */
export function cellsForTile(
  cells: readonly CoverageCell[],
  z: number,
  x: number,
  y: number,
  marginKm: number,
): CoverageCell[] {
  const tile = widen(tileBounds(z, x, y), marginKm)
  return cells.filter((cell) => boundsOverlap(cell.bounds, tile))
}

/**
 * The cells a walk crosses, plus every cell it passes within `marginKm` of -
 * the derived answer to "the stretch I am walking" (#558), in the index's own
 * order.
 *
 * Takes the runs `lib/trailPosition.ts`'s `trailSlice` hands back, so a hike
 * that spans a gap between centerline pieces is measured on the ground that
 * exists rather than on a chord across the gap. The centerline's vertices are
 * tens of metres apart, so a boundary crossed between two of them is caught
 * by the margin, never missed.
 */
export function cellsAlong(
  cells: readonly CoverageCell[],
  runs: ReadonlyArray<ReadonlyArray<readonly [number, number]>>,
  marginKm: number,
): CoverageCell[] {
  return cells.filter((cell) => {
    const reach = widen(cell.bounds, marginKm)
    return runs.some((run) => run.some(([lon, lat]) => boundsContain(reach, lon, lat)))
  })
}

export interface StretchPrice {
  /** How many cells the stretch is. */
  pieces: number
  /** How many of them are not on this phone. */
  missing: number
  /**
   * What the missing cells and the shared context will cost, in bytes on the
   * wire - or null where any one of them is unpriced, on lib/packages.ts's
   * all-or-nothing rule: a total that quietly omitted the piece nobody had
   * measured would understate, which is the direction that strands somebody
   * who freed exactly enough room.
   */
  bytes: number | null
}

/**
 * The price of a stretch is the price of what is MISSING (OFFLINE_COVERAGE.md
 * §9): a cell already held costs nothing again, which is also what makes
 * extending a stretch never re-fetch the ground it shares with the last one.
 * Every figure comes from `latest.json`'s measured `size_bytes`, never a
 * constant - the manifest is the only thing that has weighed a cell.
 */
export function priceStretch(
  cells: readonly CoverageCell[],
  context: string | null,
  held: (packageKey: string) => boolean,
  sizes: PublishedSizes,
  family: CellFamily = BASEMAP_CELLS,
): StretchPrice {
  return priceStretches([{ cells, context, family }], held, sizes)
}

/** One family's share of a stretch: the cells under the hike from ITS index,
 *  and its context, if the cut published one. */
export interface StretchPart {
  cells: readonly CoverageCell[]
  context: string | null
  family: CellFamily
}

/**
 * One price for a stretch that is several families of cells (#1257 stage 2:
 * the basemap's and the network's, taken as one decision).
 *
 * A PIECE IS A SQUARE OF GROUND, not an archive. Two families' cells over the
 * same square are one piece to a hiker - "3 pieces" is three squares of the
 * trail, whatever is published for each - so `pieces` counts distinct cell
 * names across the parts, and a piece is `missing` while ANY family's cell for
 * it is. The bytes are every missing archive across every part, contexts
 * included, on priceStretch's all-or-nothing rule: one unpriced archive
 * anywhere and the total is withheld rather than understated.
 */
export function priceStretches(
  parts: readonly StretchPart[],
  held: (packageKey: string) => boolean,
  sizes: PublishedSizes,
): StretchPrice {
  const pieces = new Set<string>()
  const missing = new Set<string>()
  const artifacts: string[] = []
  for (const { cells, context, family } of parts) {
    for (const cell of cells) {
      pieces.add(cell.name)
      if (!held(cellPackageKey(cell.name, family))) {
        missing.add(cell.name)
        artifacts.push(cell.key)
      }
    }
    if (context !== null && !held(family.contextPackageKey)) artifacts.push(context)
  }

  let bytes: number | null = 0
  for (const artifact of artifacts) {
    const size = sizes[artifact]
    if (size === undefined) {
      bytes = null
      break
    }
    bytes += size
  }

  return { pieces: pieces.size, missing: missing.size, bytes }
}

/** One straight edge of the downloaded area, as the two ends of a line. */
export type SeamEdge = readonly [readonly [number, number], readonly [number, number]]

function corner(west: number, south: number): string {
  return `${west.toFixed(4)}|${south.toFixed(4)}`
}

/**
 * The OUTER boundary of the held cells: every cell edge with no held cell on
 * the other side of it. Two neighbouring held cells share an edge that is not
 * a seam - the map is continuous across it - and drawing it would put a
 * dashed line through the middle of somebody's coverage.
 *
 * 1° cells make every seam a meridian or a parallel, and a hiker crossing one
 * sees a dead-straight edge that reads as a rendering fault unless it is
 * named (OFFLINE_COVERAGE.md §7). map/coverageLayers.ts draws these dashed
 * and labelled for exactly that reason.
 */
export function seamEdges(
  held: readonly CoverageCell[],
  cellDegrees: number,
): SeamEdge[] {
  const corners = new Set(held.map((cell) => corner(cell.bounds[0], cell.bounds[1])))
  const edges: SeamEdge[] = []
  for (const {
    bounds: [west, south, east, north],
  } of held) {
    if (!corners.has(corner(west - cellDegrees, south))) {
      edges.push([
        [west, south],
        [west, north],
      ])
    }
    if (!corners.has(corner(east, south))) {
      edges.push([
        [east, south],
        [east, north],
      ])
    }
    if (!corners.has(corner(west, south - cellDegrees))) {
      edges.push([
        [west, south],
        [east, south],
      ])
    }
    if (!corners.has(corner(west, north))) {
      edges.push([
        [west, north],
        [east, north],
      ])
    }
  }
  return edges
}

/** The basemap family's index record, under its old name. */
export const CELL_INDEX_STORE_KEY = BASEMAP_CELLS.indexStoreKey

interface StoredCellIndex {
  /** The published document as it arrived, re-parsed on every read - a value
   *  an earlier build wrote is re-validated the way lib/plannedHike.ts
   *  re-validates a stored hike. */
  index: unknown
  /** The published hash it matched, or null where the manifest named none. */
  hash: string | null
}

export async function readStoredCellIndex(
  family: CellFamily = BASEMAP_CELLS,
): Promise<CellIndex | null> {
  try {
    const stored = (await get(family.indexStoreKey)) as StoredCellIndex | undefined
    if (stored === undefined || stored === null) return null
    return parseCellIndex(stored.index)
  } catch {
    // IndexedDB unavailable or unreadable. No index is the state a phone
    // starts in, and every reader already handles it.
    return null
  }
}

/**
 * The index as the bucket publishes it now, held to its published hash and
 * stored - or null on every way of not getting one.
 *
 * Never fatal, on lib/dataManifest.ts's terms: a 404 is a release without
 * cells, a hash mismatch is a copy that is not what was published (the stored
 * copy stays, and nothing verified is replaced by something that is not), and
 * no signal is no signal. All three read as "no pieces on offer", which is
 * the state the app shipped in before cells existed.
 */
export async function fetchCellIndex({
  signal,
  family = BASEMAP_CELLS,
}: { signal?: AbortSignal; family?: CellFamily } = {}): Promise<CellIndex | null> {
  return (await fetchCellIndexOutcome({ signal, family })).index
}

/**
 * The same fetch, saying WHY there is no index when there is none: whether
 * the bucket answered (a release without this family's cells, or bytes that
 * are not what was published - settled, nothing on this phone changes it) or
 * the request never completed (no signal, a refused origin - the one absence
 * a connection cures). The junction graph's door needs the difference
 * (lib/useTrailGraph.ts): "needs a connection" over a release that has no
 * cells is #1048's bug one surface over.
 */
export async function fetchCellIndexOutcome({
  signal,
  family = BASEMAP_CELLS,
}: { signal?: AbortSignal; family?: CellFamily } = {}): Promise<{
  index: CellIndex | null
  unreachable: boolean
}> {
  if (!DATA_CONFIGURED) return { index: null, unreachable: false }

  try {
    const expected = await publishedHash(family.indexKey, { signal })
    const response = await fetch(dataUrl(family.indexKey), { signal })
    if (!response.ok) return { index: null, unreachable: false }

    const bytes = new Uint8Array(await response.arrayBuffer())
    if (expected !== null && (await sha256Of(bytes)) !== expected) {
      return { index: null, unreachable: false }
    }

    const raw: unknown = JSON.parse(new TextDecoder().decode(bytes))
    const index = parseCellIndex(raw)
    if (index === null) return { index: null, unreachable: false }

    await set(family.indexStoreKey, {
      index: raw,
      hash: expected,
    } satisfies StoredCellIndex)
    return { index, unreachable: false }
  } catch (error) {
    // An abort is the caller unmounting, not a missing index - the same
    // matching, and the same reason for it, as lib/dataManifest.ts.
    if ((error as { name?: string } | null)?.name === 'AbortError') throw error
    return { index: null, unreachable: true }
  }
}

/** What {@link useCellIndexState} knows about one family's index. */
export interface CellIndexState {
  index: CellIndex | null
  /** Whether the store has answered and, with signal, the bucket has too -
   *  before this, a null index is "not asked yet", not "there is none". */
  settled: boolean
  /** Whether the reason there is no index is one a connection would cure:
   *  no signal, or a fetch that never completed. False for a bucket that
   *  answered "no such index". */
  unreachable: boolean
}

/**
 * The cell index this phone can answer from: the stored copy at once, the
 * bucket's copy whenever there is signal to ask.
 *
 * The stored read never overwrites a fetched answer, whichever lands first -
 * a launch with signal that reads the store slowly must not replace today's
 * index with last month's.
 */
export function useCellIndex(
  family: CellFamily = BASEMAP_CELLS,
  ready = true,
): CellIndex | null {
  return useCellIndexState(family, 0, ready).index
}

/**
 * {@link useCellIndex} with its two other answers: whether it has answered at
 * all, and whether a connection would change the answer. `attempt` re-asks
 * the bucket when bumped - a "Try again" control's handle.
 */
/**
 * @param ready Whether the launch is past its first frame (#1302). Both the
 *   store read and the fetch wait for it - a cell list changes nothing on
 *   the first frame, and the fetch is followed by a SHA-256 and a parse on
 *   the thread that frame is drawn on. `settled` stays false until then, so
 *   nothing downstream mistakes "not asked yet" for "no cells".
 */
export function useCellIndexState(
  family: CellFamily = BASEMAP_CELLS,
  attempt = 0,
  ready = true,
): CellIndexState {
  const [index, setIndex] = useState<CellIndex | null>(null)
  const [storeRead, setStoreRead] = useState(false)
  const [fetched, setFetched] = useState<{ done: boolean; unreachable: boolean }>({
    done: false,
    unreachable: false,
  })
  const online = useOnline()

  useEffect(() => {
    if (!ready) return
    let wanted = true
    void readStoredCellIndex(family).then((stored) => {
      if (!wanted) return
      if (stored !== null) setIndex((current) => current ?? stored)
      setStoreRead(true)
    })
    return () => {
      wanted = false
    }
  }, [family, ready])

  useEffect(() => {
    // Never with no signal, and never on a build with no bucket - the same
    // gate lib/usePublishedSizes.ts keeps, for the same reason: a phone
    // offline at a trailhead must reach the network zero times.
    if (!DATA_CONFIGURED || !online || !ready) return

    const controller = new AbortController()
    let wanted = true
    setFetched({ done: false, unreachable: false })
    fetchCellIndexOutcome({ signal: controller.signal, family })
      .then((outcome) => {
        if (!wanted) return
        if (outcome.index !== null) setIndex(outcome.index)
        setFetched({ done: true, unreachable: outcome.unreachable })
      })
      .catch(() => {
        // The abort path; fetchCellIndexOutcome answers everything else.
      })

    return () => {
      wanted = false
      controller.abort()
    }
  }, [online, family, attempt, ready])

  // Offline the store is the whole answer; with signal the bucket's word is
  // waited for, so a phone with an old index stored is not told "no cells"
  // in the seconds before this release's list arrives.
  const settled = storeRead && (!online || !DATA_CONFIGURED || fetched.done)
  const unreachable = index === null && settled && (!online || fetched.unreachable)
  return { index, settled, unreachable }
}
