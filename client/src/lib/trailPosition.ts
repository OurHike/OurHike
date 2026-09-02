// Where a GPS fix sits along the trail, in miles from the southern terminus.
//
// TWO WAYS TO GET A MILE ONTO A VERTEX, and which one an index is built from
// is a fact it carries (`onPipelineAxis`) rather than a thing to guess at.
//
// The pipeline's (#1192, pipeline/export_trails.py's write_trail_miles): every
// centerline vertex of trails.geojson projected onto the same calibrated axis
// that `export_poi.attach_miles` projects a shelter onto and that
// elevation_profile.json's distance_mi is sampled along. Read here, those
// numbers make the index speak the axis every published mile is already on -
// a StoredPoi's `mile` IS its position on this index, with no search and no
// second scale to reconcile. This is HIKE_PLANNING.md Finding 1's
// recommendation ("one scale, and it is the pipeline's"), a year late.
//
// The phone's own, for a release that publishes no miles: each centerline
// piece is flipped if its own coordinates run north-to-south, all pieces are
// sorted along a straight Springer->Katahdin axis, and a haversine is summed
// per vertex - the same shape as export_elevation.py's ordered_oriented_parts()
// and with the same limitation, that a stretch running against the overall
// SW-to-NE axis can land slightly out of true hiking order. A mile measured
// this way is close to a pipeline mile and not identical, which is what
// lib/route.ts's anchors exist to carry across. They are kept for exactly
// this case and are identity on the other.
//
// LOOKUPS ARE BUCKETED IN TWO DIMENSIONS. They used to be bucketed by
// latitude alone, which was written for one GPS fix every few seconds and
// then asked to place 16,949 waypoints in one memo: measured 2026-09-02 on the
// live release, 3,154 haversines per waypoint and 53 million per launch,
// 13 s of one long task on a 4x-throttled phone profile. Cells of latitude AND
// longitude cut that to 565 per waypoint with the identical answer for every
// one of them (#1192 has the table). The bulk placement has since moved off
// this thread altogether (lib/trailIndexBuild.ts) and is mostly unnecessary
// on the pipeline's axis; the grid stays because a fix every few seconds for
// three days is still a battery cost worth a fifth of.

import type { FeatureCollection } from 'geojson'

const SPRINGER_LONLAT = [-84.19388, 34.62639] as const
const KATAHDIN_LONLAT = [-68.92139, 45.90444] as const

const EARTH_RADIUS_FT = 20_902_231
const FEET_PER_MILE = 5280

/** Cell height in degrees of latitude - about 3.45 miles, comfortably wider
 *  than any plausible distance between a hiker and the trail. */
const LAT_CELL_DEGREES = 0.05

/**
 * Cell width in degrees of longitude.
 *
 * Derived rather than picked: a degree of longitude is 69.17 x cos(latitude)
 * miles, and the gate below is guaranteed by the +-1 neighbouring cells
 * covering at least MAX_OFF_TRAIL_MILES in every direction. The trail's
 * northern end is Katahdin at 45.9 N, where a degree is 48.1 miles and this
 * width is 3.37 - the narrowest the cells ever get, and still past the gate.
 * At Springer (34.6 N) the same cell is 3.98 miles wide. A width that was
 * exactly three miles somewhere would pass or fail a fix depending on where
 * in its cell it happened to land, which is a worse thing to be than merely
 * conservative - the same argument MAX_OFF_TRAIL_MILES makes for latitude.
 */
const LON_CELL_DEGREES = 0.07

/**
 * Farthest a fix can be from the centerline and still be given a mile.
 *
 * Without this the answer to "where am I on the trail" was "the nearest AT
 * vertex in a nearby cell, however far that is." A phone in Indianapolis,
 * which shares a latitude with the trail in Maryland, was told it was
 * standing on it - and told confidently, with a mile number in the header,
 * because nothing downstream looked at offTrailFeet.
 *
 * Three miles rather than a rounder number because it has to fit inside the
 * cell search: from anywhere inside a cell, the +-1 neighbours cover at least
 * LAT_CELL_DEGREES (about 3.45 miles) north and south and at least 3.37 miles
 * east and west (LON_CELL_DEGREES), so every point within this radius is
 * guaranteed to be a candidate. A wider gate would pass or fail depending on
 * where in its cell the fix happened to land, which is a worse thing to be
 * than merely conservative.
 */
export const MAX_OFF_TRAIL_MILES = 3

export interface LonLat {
  lon: number
  lat: number
}

export interface TrailFix {
  /** Miles from the southern terminus. */
  mile: number
  /**
   * How far the fix is from the A.T. centerline itself.
   *
   * This is the distance the mile is measured from, so it is the one that says
   * how much to trust the mile - not the one that says whether the hiker is on
   * a trail. For that, see {@link offTreadFeet}.
   */
  offTrailFeet: number
  /**
   * How far the fix is from the nearest mapped tread of any kind - the
   * centerline or a blue-blazed side trail.
   *
   * Separate from {@link offTrailFeet} because "which mile am I at" and "am I
   * on a trail" are two different questions that used to share one index, and
   * the answer to the second was wrong nearly every time it mattered. Measured
   * against the live ATC layers (#308): the median shelter on the Appalachian
   * Trail is 197 ft from the Appalachian Trail, and 72% of shelters sit past
   * the 90 ft `OFF_TRAIL_THRESHOLD_FT` - because the shelter is at the end of
   * a side trail, which is what the side trail is for. Counting those side
   * trails takes that 72% to 5%.
   *
   * Always <= `offTrailFeet`, since the centerline is itself mapped tread.
   */
  offTreadFeet: number
}

/**
 * The vertices of some set of lines, cut into cells for nearest-vertex search,
 * with no mile axis on them.
 *
 * {@link TrailIndex} is structurally one of these, which is deliberate: the
 * centerline and the full tread are searched by exactly the same code, and
 * only one of the two carries miles.
 *
 * `cells` maps a cell key ({@link cellKey}) to the indices of the vertices in
 * it - a plain array when built here, a view into one Int32Array when
 * rebuilt from a {@link SerializedVertexIndex}. Both are read by index only.
 */
export interface VertexIndex {
  lons: Float64Array
  lats: Float64Array
  cells: Map<number, ArrayLike<number>>
}

export interface TrailIndex extends VertexIndex {
  miles: Float64Array
  totalMiles: number
  /**
   * Where each centerline piece begins in the flat arrays, ascending.
   *
   * The flat arrays concatenate pieces the source data never joined, so two
   * neighbouring entries can be miles apart on the ground. Anything reading a
   * RUN of coordinates has to break at these indices - see {@link trailSlice},
   * which would otherwise draw a straight line across the gap between two
   * pieces and put a closure band where there is no trail.
   *
   * On the pipeline's axis a piece is also broken wherever its published
   * miles step backwards (46 of 461 chains do, 112 steps in all, the largest
   * 0.27 mi, measured on the 2026-09-02 release): the calibrated axis's
   * nearest piece changed under the chain there, and a run that crossed the
   * step would claim miles it does not have.
   *
   * Nothing else needs them: `locateOnTrail` asks about single vertices, and
   * the mile total already excludes the gaps (see the note in
   * {@link buildTrailIndex}).
   */
  partStarts: readonly number[]
  /**
   * Every mapped trail's vertices - the centerline and the side trails
   * together - for the "am I on a trail" question only.
   *
   * The side trails are in the same published artifact and are excluded from
   * everything above this line on purpose: a mile means distance along the
   * A.T., and a hiker on a spur should read the mile of the junction. That
   * exclusion is right for the mile axis and wrong for the distance, so the
   * distance gets its own set rather than a flag on the shared one.
   */
  tread: VertexIndex
  /**
   * Whether `miles` are the pipeline's own numbers (#1192).
   *
   * True: every StoredPoi's `mile`, every elevation_profile.json sample and
   * every mile this index answers are one measurement, and lib/route.ts's
   * `anchoredMile` is identity. False: the miles were summed here from the
   * geometry, a different measurement of the same line, and the anchors
   * carry numbers between the two. The header of this file says why both
   * exist.
   */
  onPipelineAxis: boolean
}

/**
 * The published per-vertex miles, parsed: feature id -> one mile per vertex,
 * in the feature's own coordinate order. See lib/trailMiles.ts, which is the
 * only thing that builds one.
 */
export type TrailMilesById = ReadonlyMap<string, readonly number[]>

function axisProjection(lon: number, lat: number): number {
  const dx = KATAHDIN_LONLAT[0] - SPRINGER_LONLAT[0]
  const dy = KATAHDIN_LONLAT[1] - SPRINGER_LONLAT[1]
  return (lon - SPRINGER_LONLAT[0]) * dx + (lat - SPRINGER_LONLAT[1]) * dy
}

function haversineFeet(a: LonLat, b: LonLat): number {
  const toRad = Math.PI / 180
  const dLat = (b.lat - a.lat) * toRad
  const dLon = (b.lon - a.lon) * toRad
  const lat1 = a.lat * toRad
  const lat2 = b.lat * toRad

  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2

  return 2 * EARTH_RADIUS_FT * Math.asin(Math.min(1, Math.sqrt(h)))
}

// One integer per cell, so the cell map is keyed by a number rather than a
// string built per lookup. Latitude rows are shifted to be non-negative and
// spaced wider than the longitude columns can ever need: 360 / 0.07 is 5,143
// columns, and 8,192 leaves room for a column index to run a little past
// either meridian without colliding with the next row.
const LON_COLUMNS = 8192
const LON_COLUMN_SHIFT = LON_COLUMNS / 2
const LAT_ROW_SHIFT = 2000

function latRow(lat: number): number {
  return Math.floor(lat / LAT_CELL_DEGREES)
}

function lonColumn(lon: number): number {
  return Math.floor(lon / LON_CELL_DEGREES)
}

function keyOf(row: number, column: number): number {
  return (row + LAT_ROW_SHIFT) * LON_COLUMNS + (column + LON_COLUMN_SHIFT)
}

/** The cell a coordinate falls in. Exported for the tests that prove the
 *  search reaches across a cell boundary in both directions. */
export function cellKey(lat: number, lon: number): number {
  return keyOf(latRow(lat), lonColumn(lon))
}

/**
 * Every cell of an index that a bounding box could reach, for a caller that
 * walks a viewport's worth of vertices rather than searching for one
 * (lib/viewportMiles.ts). The cells are a superset of the box - each is up to
 * four miles across - so the caller still tests each vertex against the box's
 * own edges. Kept here so the grid's shape stays this module's business.
 */
export function* cellsInBox(
  index: VertexIndex,
  south: number,
  north: number,
  west: number,
  east: number,
): Generator<ArrayLike<number>> {
  const firstRow = latRow(Math.min(south, north))
  const lastRow = latRow(Math.max(south, north))
  const firstColumn = lonColumn(Math.min(west, east))
  const lastColumn = lonColumn(Math.max(west, east))
  for (let row = firstRow; row <= lastRow; row += 1) {
    for (let column = firstColumn; column <= lastColumn; column += 1) {
      const cell = index.cells.get(keyOf(row, column))
      if (cell !== undefined) yield cell
    }
  }
}

type Coordinates = Array<[number, number]>

/** Cuts a set of vertices, already flat, into cells. */
function cellsOf(lons: Float64Array, lats: Float64Array): Map<number, ArrayLike<number>> {
  const cells = new Map<number, number[]>()
  for (let i = 0; i < lons.length; i += 1) {
    const key = cellKey(lats[i], lons[i])
    const cell = cells.get(key)
    if (cell === undefined) cells.set(key, [i])
    else cell.push(i)
  }
  return cells
}

/** Flattens coordinate runs into typed arrays and cells them. */
function buildVertexIndex(runs: Coordinates[]): VertexIndex {
  const flat: Coordinates = runs.flat()
  const count = flat.length

  const lons = new Float64Array(count)
  const lats = new Float64Array(count)
  for (let i = 0; i < count; i += 1) {
    const [lon, lat] = flat[i]
    lons[i] = lon
    lats[i] = lat
  }

  return { lons, lats, cells: cellsOf(lons, lats) }
}

/**
 * One centerline piece, oriented so its miles rise, with its miles beside it
 * where the pipeline published them.
 */
export interface TrailPart {
  coords: Coordinates
  /** The pipeline's mile per vertex, or null to be measured here. */
  miles: readonly number[] | null
}

/**
 * What an index is built from, once the collection has been read.
 *
 * Split out from {@link buildTrailIndex} so lib/trailIndexBuild.ts can do the
 * same reading and then index in slices on a thread it must not hold; the
 * one-call form below is the same two steps back to back.
 */
export interface TrailParts {
  /** Centerline pieces, sorted south to north and each oriented to rise. */
  parts: TrailPart[]
  /** Every mapped line as published - the centerline pieces whole, before
   *  any orienting or splitting, and then the side trails - for the tread. */
  tread: Coordinates[]
  /** True when every part carries the pipeline's miles - see the rule in
   *  {@link collectTrailParts}. */
  onPipelineAxis: boolean
}

/**
 * Reads the centerline and the side trails out of trails.geojson, and decides
 * which axis the index will speak.
 *
 * ALL OR NONE. The pipeline's miles are used only when every centerline
 * LineString has a published list of exactly its own length; otherwise every
 * piece is measured here. An index that spoke the pipeline's axis on some
 * pieces and its own on others would be two scales in one array, with nothing
 * downstream able to tell which vertex was which - the exact confusion
 * `onPipelineAxis` exists to rule out. A mismatch is not expected in practice
 * (the file names the lines it was measured on and the download refuses any
 * other pairing, lib/trailData.ts), so this is a guard against a truncated or
 * hand-edited store rather than a mode.
 *
 * On the pipeline's axis a piece is oriented by its miles - flipped where the
 * published numbers fall along its own coordinate order - and SPLIT wherever
 * they step backwards, so every part the index holds rises monotonically and
 * {@link trailSlice}'s contiguity argument stays true. Parts are then sorted
 * by their first mile. On the phone's own axis the geometry decides both, as
 * it always did.
 */
export function collectTrailParts(
  collection: FeatureCollection,
  publishedMiles: TrailMilesById | null = null,
): TrailParts {
  const pieces: Array<{ coords: Coordinates; id: string | null }> = []
  const tread: Coordinates[] = []

  // Defensive about the shape, not the contents: this arrives over a network
  // from a bucket, and a truncated or unexpected payload should degrade to
  // "we don't know where you are" rather than throw somewhere the caller
  // reports as a failed download.
  for (const feature of collection?.features ?? []) {
    // `geometry` before `geometry.type`: a null geometry is valid GeoJSON, not
    // a malformed payload, so a feature carrying one is a thing this can
    // actually be handed. Guarding only the top-level `features` left that
    // throwing a TypeError - from the same network payload the guard above
    // exists to survive, which made the defence half a defence.
    if (feature.geometry?.type !== 'LineString') continue

    const coords = (feature.geometry.coordinates ?? []) as Coordinates
    if (coords.length < 2) continue

    // Everything that is not the centerline is tread and nothing else: no
    // flipping, no ordering, no miles. A side trail has no place on the
    // Springer->Katahdin axis, and asking it for one is the bug this split
    // exists to avoid.
    if (feature.properties?.source !== 'centerline') {
      tread.push(coords)
      continue
    }

    const id = feature.properties?.id
    pieces.push({ coords, id: typeof id === 'string' ? id : null })
    tread.push(coords)
  }

  const onPipelineAxis =
    publishedMiles !== null &&
    pieces.length > 0 &&
    pieces.every(
      ({ coords, id }) => id !== null && publishedMiles.get(id)?.length === coords.length,
    )

  const parts: TrailPart[] = []
  if (onPipelineAxis) {
    for (const { coords, id } of pieces) {
      const miles = publishedMiles.get(id as string) as readonly number[]
      for (const part of risingParts(coords, miles)) parts.push(part)
    }
    parts.sort(
      (a, b) => (a.miles as readonly number[])[0] - (b.miles as readonly number[])[0],
    )
  } else {
    for (const { coords } of pieces) {
      // Flip a piece whose own coordinates run north-to-south, so every piece
      // agrees on which end is Springer before they are ordered.
      const forwards =
        axisProjection(coords[0][0], coords[0][1]) <=
        axisProjection(coords[coords.length - 1][0], coords[coords.length - 1][1])
      parts.push({ coords: forwards ? coords : [...coords].reverse(), miles: null })
    }
    parts.sort(
      (a, b) =>
        axisProjection(a.coords[0][0], a.coords[0][1]) -
        axisProjection(b.coords[0][0], b.coords[0][1]),
    )
  }

  return { parts, tread, onPipelineAxis }
}

/**
 * A piece with published miles, oriented to rise and cut at every step back.
 *
 * Orientation is the ends' call: a piece whose last mile is below its first
 * runs against the axis and is reversed whole (192 of 461 chains on the
 * 2026-09-02 release). Then any vertex whose mile is below its predecessor's
 * starts a new part - the step itself is not a run of trail between two
 * miles, it is the axis's nearest piece changing underneath the chain.
 */
function risingParts(coords: Coordinates, miles: readonly number[]): TrailPart[] {
  const rises = miles[miles.length - 1] >= miles[0]
  const orderedCoords = rises ? coords : [...coords].reverse()
  const orderedMiles = rises ? miles : [...miles].reverse()

  const parts: TrailPart[] = []
  let from = 0
  for (let i = 1; i < orderedMiles.length; i += 1) {
    if (orderedMiles[i] < orderedMiles[i - 1]) {
      pushPart(parts, orderedCoords, orderedMiles, from, i)
      from = i
    }
  }
  pushPart(parts, orderedCoords, orderedMiles, from, orderedMiles.length)
  return parts
}

/** A part of at least two vertices; a single vertex left over at a step is
 *  not a run of anything and is dropped from the mile axis (it stays in the
 *  tread, which is built from the whole line). */
function pushPart(
  parts: TrailPart[],
  coords: Coordinates,
  miles: readonly number[],
  from: number,
  to: number,
): void {
  if (to - from < 2) return
  parts.push({ coords: coords.slice(from, to), miles: miles.slice(from, to) })
}

/**
 * The index over already-collected parts.
 *
 * Miles come from the parts where they carry them, and are summed here where
 * they do not. Summing excludes the straight-line jump from the end of one
 * piece to the start of the next - it is not trail, it is the gap between two
 * pieces the source data never joined. Counting those gaps measured the
 * corridor at 4,055 miles against the AT's real ~2,197. The pipeline's own
 * accumulation carries across its gaps as though they touched, so on that
 * axis the gaps are whatever the published numbers say, which is the point of
 * reading them.
 */
export function indexTrailParts({
  parts,
  tread,
  onPipelineAxis,
}: TrailParts): TrailIndex {
  const count = parts.reduce((total, part) => total + part.coords.length, 0)
  const lons = new Float64Array(count)
  const lats = new Float64Array(count)
  const miles = new Float64Array(count)
  const partStarts: number[] = []

  let offset = 0
  let cumulativeFeet = 0
  for (const part of parts) {
    partStarts.push(offset)
    fillPart(part, offset, lons, lats, miles, cumulativeFeet)
    offset += part.coords.length
    cumulativeFeet = onPipelineAxis ? 0 : miles[offset - 1] * FEET_PER_MILE
  }

  let totalMiles = 0
  for (let i = 0; i < count; i += 1) if (miles[i] > totalMiles) totalMiles = miles[i]

  return {
    lons,
    lats,
    miles,
    cells: cellsOf(lons, lats),
    totalMiles,
    partStarts,
    // Centerline included, not just the spurs: the nearest mapped tread to a
    // hiker walking the AT is the AT, and `offTreadFeet` would otherwise
    // report the distance to the nearest blue blaze from the middle of it.
    tread: buildVertexIndex(tread),
    onPipelineAxis,
  }
}

/**
 * Writes one part's vertices into the flat arrays from `offset`, summing
 * miles from `feetBefore` where the part carries none. Exported for
 * lib/trailIndexBuild.ts, which does this a part at a time between yields.
 */
export function fillPart(
  part: TrailPart,
  offset: number,
  lons: Float64Array,
  lats: Float64Array,
  miles: Float64Array,
  feetBefore: number,
): void {
  const { coords } = part
  let cumulativeFeet = feetBefore
  for (let i = 0; i < coords.length; i += 1) {
    const [lon, lat] = coords[i]
    lons[offset + i] = lon
    lats[offset + i] = lat
    if (part.miles !== null) {
      miles[offset + i] = part.miles[i]
    } else {
      if (i > 0) {
        const [prevLon, prevLat] = coords[i - 1]
        cumulativeFeet += haversineFeet({ lon: prevLon, lat: prevLat }, { lon, lat })
      }
      miles[offset + i] = cumulativeFeet / FEET_PER_MILE
    }
  }
}

/**
 * Builds the index from trails.geojson, and from the published per-vertex
 * miles where a release carries them (#1192).
 *
 * Spurs and side trails are excluded from the mile axis - a mile marker means
 * distance along the AT itself, so a hiker standing on a blue-blazed spur
 * reads the mile of the junction rather than a number measured down the spur.
 * They are not thrown away, though: they are kept separately as `tread`,
 * which is what answers "is this fix on a trail at all". See {@link TrailFix}
 * for why those two questions cannot share one set of vertices.
 */
export function buildTrailIndex(
  collection: FeatureCollection,
  publishedMiles: TrailMilesById | null = null,
): TrailIndex {
  return indexTrailParts(collectTrailParts(collection, publishedMiles))
}

// ---------------------------------------------------------------------------
// Serialisation: the index as typed arrays, so it can cross a worker boundary
// by transfer and sit in IndexedDB as a structured clone (#1192,
// lib/trailIndexBuild.ts). The cell map becomes three arrays in compressed-row
// form - keys, the offset each key's run starts at, and one flat run of vertex
// indices - and comes back as views into that run, which is why VertexIndex
// reads its cells as ArrayLike rather than as arrays.

export interface SerializedVertexIndex {
  lons: Float64Array
  lats: Float64Array
  cellKeys: Int32Array
  cellOffsets: Int32Array
  cellOrder: Int32Array
}

export interface SerializedTrailIndex extends SerializedVertexIndex {
  /** Bumped when the layout changes, so a cache written by an older build is
   *  rebuilt rather than misread. */
  format: 1
  miles: Float64Array
  totalMiles: number
  partStarts: Int32Array
  onPipelineAxis: boolean
  tread: SerializedVertexIndex
}

export const SERIALIZED_TRAIL_INDEX_FORMAT = 1

function serializeVertexIndex(index: VertexIndex): SerializedVertexIndex {
  const cellKeys = new Int32Array(index.cells.size)
  const cellOffsets = new Int32Array(index.cells.size + 1)
  const cellOrder = new Int32Array(index.lons.length)
  let cell = 0
  let written = 0
  for (const [key, indices] of index.cells) {
    cellKeys[cell] = key
    cellOffsets[cell] = written
    for (let i = 0; i < indices.length; i += 1) cellOrder[written + i] = indices[i]
    written += indices.length
    cell += 1
  }
  cellOffsets[cell] = written
  return { lons: index.lons, lats: index.lats, cellKeys, cellOffsets, cellOrder }
}

function deserializeVertexIndex(serialized: SerializedVertexIndex): VertexIndex {
  const cells = new Map<number, ArrayLike<number>>()
  const { cellKeys, cellOffsets, cellOrder } = serialized
  for (let cell = 0; cell < cellKeys.length; cell += 1) {
    cells.set(
      cellKeys[cell],
      cellOrder.subarray(cellOffsets[cell], cellOffsets[cell + 1]),
    )
  }
  return { lons: serialized.lons, lats: serialized.lats, cells }
}

export function serializeTrailIndex(index: TrailIndex): SerializedTrailIndex {
  return {
    format: SERIALIZED_TRAIL_INDEX_FORMAT,
    ...serializeVertexIndex(index),
    miles: index.miles,
    totalMiles: index.totalMiles,
    partStarts: Int32Array.from(index.partStarts),
    onPipelineAxis: index.onPipelineAxis,
    tread: serializeVertexIndex(index.tread),
  }
}

export function deserializeTrailIndex(serialized: SerializedTrailIndex): TrailIndex {
  return {
    ...deserializeVertexIndex(serialized),
    miles: serialized.miles,
    totalMiles: serialized.totalMiles,
    partStarts: Array.from(serialized.partStarts),
    onPipelineAxis: serialized.onPipelineAxis,
    tread: deserializeVertexIndex(serialized.tread),
  }
}

/** Every buffer behind a serialized index, for postMessage's transfer list -
 *  moved rather than copied, which is what makes handing 250,000 vertices
 *  across a worker boundary cost microseconds. */
export function trailIndexBuffers(serialized: SerializedTrailIndex): ArrayBuffer[] {
  const arrays = [
    serialized.lons,
    serialized.lats,
    serialized.miles,
    serialized.cellKeys,
    serialized.cellOffsets,
    serialized.cellOrder,
    serialized.partStarts,
    serialized.tread.lons,
    serialized.tread.lats,
    serialized.tread.cellKeys,
    serialized.tread.cellOffsets,
    serialized.tread.cellOrder,
  ]
  // De-duplicated: a buffer listed twice in a transfer list is an error, and
  // nothing stops two views sharing one.
  return [...new Set(arrays.map((array) => array.buffer as ArrayBuffer))]
}

/**
 * Whether a value read back from storage is a serialized index this build can
 * use. Everything typed-array is checked for being one; a cache written by a
 * build with another layout, or anything else in the slot, is "no cache".
 */
export function isSerializedTrailIndex(value: unknown): value is SerializedTrailIndex {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>
  const vertexIndex = (part: unknown): boolean =>
    typeof part === 'object' &&
    part !== null &&
    (part as Record<string, unknown>).lons instanceof Float64Array &&
    (part as Record<string, unknown>).lats instanceof Float64Array &&
    (part as Record<string, unknown>).cellKeys instanceof Int32Array &&
    (part as Record<string, unknown>).cellOffsets instanceof Int32Array &&
    (part as Record<string, unknown>).cellOrder instanceof Int32Array
  return (
    candidate.format === SERIALIZED_TRAIL_INDEX_FORMAT &&
    vertexIndex(candidate) &&
    candidate.miles instanceof Float64Array &&
    typeof candidate.totalMiles === 'number' &&
    candidate.partStarts instanceof Int32Array &&
    typeof candidate.onPipelineAxis === 'boolean' &&
    vertexIndex(candidate.tread)
  )
}

/**
 * The trail's own coordinates between two mile markers, as one or more runs.
 *
 * Several runs rather than one, because `partStarts` exists: the flat arrays
 * concatenate centerline pieces that the source data never joined, and joining
 * them here would draw a straight line across a gap that is not trail. A
 * caller gets what it can honestly draw - a MultiLineString's worth of pieces
 * - rather than a single line through country nobody surveyed.
 *
 * Direction-agnostic. `fromMile` and `toMile` are normalised, so a SOBO
 * caller reading a closure's `end_mile_marker` first gets the same band.
 */
export function trailSlice(
  index: TrailIndex,
  fromMile: number,
  toMile: number,
): Array<Array<[number, number]>> {
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)
  const count = index.lons.length
  if (count === 0) return []

  const runs: Array<Array<[number, number]>> = []

  for (let p = 0; p < index.partStarts.length; p += 1) {
    const start = index.partStarts[p]
    const end = (index.partStarts[p + 1] ?? count) - 1

    // Miles rise monotonically inside a piece (the gaps between pieces are the
    // only places they do not), so the piece's own span is its two ends and
    // the matching indices below are contiguous.
    if (index.miles[end] < low || index.miles[start] > high) continue

    let first = start
    while (first <= end && index.miles[first] < low) first += 1
    let last = end
    while (last >= start && index.miles[last] > high) last -= 1

    // Fewer than two vertices in range is not "no closure here" - it is a
    // range shorter than the survey's own vertex spacing, or one that happens
    // to fall between two of them. Widening to the neighbours draws a band a
    // few dozen feet longer than the report; dropping it draws nothing at all,
    // which on this map is a closed stretch of trail rendered as open.
    if (last < first) {
      // Nothing in range, so the two searches crossed: `last` is the vertex
      // just before it and `first` the one just after, which is exactly the
      // pair that brackets it.
      ;[first, last] = [last, first]
    } else if (last === first) {
      first = Math.max(start, first - 1)
      last = Math.min(end, last + 1)
    }
    if (last <= first) continue

    const run: Array<[number, number]> = []
    for (let i = first; i <= last; i += 1) run.push([index.lons[i], index.lats[i]])
    runs.push(run)
  }

  return runs
}

/**
 * Where a single mile marker is, as one coordinate - or null if it is not on
 * this build's centerline.
 *
 * The counterpart to {@link trailSlice}, and it exists because a point is not
 * a short band. `trailSlice` widens a zero-length range to the two vertices
 * that bracket it, which is the right answer for a *range* too small to draw
 * and the wrong one for a place: a shelter at mile 1,503.6 became a few dozen
 * feet of line, invisible at any zoom a hiker uses. Most of what the ATC
 * publishes is a single mile (map/atcUpdateLayers.ts).
 *
 * Interpolated between the two bracketing vertices rather than snapped to the
 * nearer one, because the centerline's vertex spacing is coarser than the
 * tenth of a mile ATC quotes, and snapping would move a footbridge to
 * wherever the survey happened to put a point.
 *
 * Pieces are respected the way `trailSlice` respects them: a mile that falls
 * in the gap *between* two centerline pieces belongs to neither, and answering
 * with a coordinate there would place a notice on trail this build does not
 * have.
 */
export function trailPointAtMile(
  index: TrailIndex,
  mile: number,
): [number, number] | null {
  const count = index.lons.length
  if (count === 0) return null

  for (let p = 0; p < index.partStarts.length; p += 1) {
    const start = index.partStarts[p]
    const end = (index.partStarts[p + 1] ?? count) - 1
    if (mile < index.miles[start] || mile > index.miles[end]) continue

    let i = start
    while (i < end && index.miles[i + 1] < mile) i += 1

    const span = index.miles[i + 1] - index.miles[i]
    // Two vertices recorded at the same mile: no gradient to interpolate
    // along, and either endpoint is as good an answer as the other.
    const t = span > 0 ? (mile - index.miles[i]) / span : 0
    return [
      index.lons[i] + (index.lons[i + 1] - index.lons[i]) * t,
      index.lats[i] + (index.lats[i + 1] - index.lats[i]) * t,
    ]
  }

  return null
}

/** The closest vertex in a set to a point, or null if the set has none near
 *  enough to share a cell or a neighbouring one. */
function nearestVertex(
  index: VertexIndex,
  at: LonLat,
): { index: number; feet: number } | null {
  if (index.lons.length === 0) return null

  const row = latRow(at.lat)
  const column = lonColumn(at.lon)

  let bestIndex = -1
  let bestFeet = Infinity

  // The home cell and its eight neighbours, so a fix just inside a boundary
  // still sees the trail points on the other side of it - in either axis.
  for (let dr = -1; dr <= 1; dr += 1) {
    for (let dc = -1; dc <= 1; dc += 1) {
      const cell = index.cells.get(keyOf(row + dr, column + dc))
      if (cell === undefined) continue
      for (let c = 0; c < cell.length; c += 1) {
        const i = cell[c]
        const feet = haversineFeet(at, { lon: index.lons[i], lat: index.lats[i] })
        if (feet < bestFeet) {
          bestFeet = feet
          bestIndex = i
        }
      }
    }
  }

  if (bestIndex === -1) return null
  return { index: bestIndex, feet: bestFeet }
}

/**
 * The mile alone, for a caller that wants nothing else.
 *
 * The same centerline search and the same {@link MAX_OFF_TRAIL_MILES} gate
 * {@link locateOnTrail} applies, and deliberately NOT the second search over
 * `tread`. That second search is what answers "am I on a trail at all", it is
 * the more expensive of the two (251,544 tread vertices against the
 * centerline's 219,293), and a caller placing a point on the mile axis has no
 * use for it.
 *
 * Worth its own function rather than a flag because of who calls which.
 * {@link locateOnTrail} is called once per GPS fix and feeds the wrong-way
 * alert, which needs `offTreadFeet` and must keep paying for it. This one is
 * for a tapped point, a report, a closure end - single places with no
 * precomputed answer. It is NOT for placing every waypoint on the phone: that
 * was 16,949 calls in one memo on the launch thread (#1192), and it now
 * happens either not at all (the pipeline publishes the mile) or off the
 * thread, in lib/trailIndexBuild.ts. Splitting them means the cheap path
 * cannot accidentally become the safety path, or the reverse.
 */
export function mileOnTrail(index: TrailIndex, at: LonLat): number | null {
  const onCenterline = nearestVertex(index, at)
  if (onCenterline === null) return null
  if (onCenterline.feet > MAX_OFF_TRAIL_MILES * FEET_PER_MILE) return null
  return index.miles[onCenterline.index]
}

/**
 * The trail point nearest a fix. Null when the index is empty or the fix is
 * nowhere near the corridor - farther than MAX_OFF_TRAIL_MILES from any
 * centerline vertex. "We don't know where you are on the trail" is a real
 * answer, and a better one than a mile number measured to a point three states
 * away.
 */
export function locateOnTrail(index: TrailIndex, at: LonLat): TrailFix | null {
  const onCenterline = nearestVertex(index, at)
  if (onCenterline === null) return null

  // Near in one cell is not near. A cell is up to four miles across, so the
  // nearest candidate can be well past the gate and still have been measured
  // - see MAX_OFF_TRAIL_MILES.
  if (onCenterline.feet > MAX_OFF_TRAIL_MILES * FEET_PER_MILE) return null

  // Gated on the centerline rather than on the tread, deliberately: this gate
  // is about whether the *mile* means anything, and a mile is only ever
  // measured along the centerline. A hiker three miles up a side trail is off
  // the axis this index describes, however much tread they are standing on.
  const onTread = nearestVertex(index.tread, at)

  return {
    mile: index.miles[onCenterline.index],
    offTrailFeet: onCenterline.feet,
    // The centerline is part of `tread`, so this can only be shorter - and the
    // fallback is unreachable in practice for the same reason. It is here
    // because an index built from a payload with no usable lines at all should
    // report the honest distance it does have rather than a zero.
    offTreadFeet: onTread === null ? onCenterline.feet : onTread.feet,
  }
}
