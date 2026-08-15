// Where a GPS fix sits along the trail, in miles from the southern terminus.
//
// This mirrors pipeline/export_elevation.py's ordered_oriented_parts(): each
// centerline piece is flipped if its own coordinates run north-to-south, then
// all pieces are sorted along a straight Springer->Katahdin axis. It carries
// the same limitation that function documents - centerline.geojson has no
// trail-sequence field, so this is a geographic approximation, and a stretch
// that genuinely runs against the overall SW-to-NE axis (the Smokies, for
// instance) can land slightly out of true hiking order.
//
// One real difference from the pipeline worth knowing: the pipeline merges
// connected pieces with ST_LineMerge first and this does not, so a mile here
// and a distance_mi in elevation_profile.json are close but not identical.
// They should not be compared against each other as though they were the same
// measurement.
//
// Lookups are bucketed by latitude because this runs on every GPS fix for
// days at a time. A linear scan over the corridor's ~500k vertices is a few
// milliseconds of CPU each time, which is nothing once but is a battery cost
// over a three-day hike.

import type { FeatureCollection } from 'geojson'

const SPRINGER_LONLAT = [-84.19388, 34.62639] as const
const KATAHDIN_LONLAT = [-68.92139, 45.90444] as const

const EARTH_RADIUS_FT = 20_902_231
const FEET_PER_MILE = 5280

/** Bucket height in degrees of latitude - about 3.5 miles, comfortably wider
 *  than any plausible distance between a hiker and the trail. */
const BUCKET_DEGREES = 0.05

/**
 * Farthest a fix can be from the centerline and still be given a mile.
 *
 * Buckets are latitude-only, so without this the answer to "where am I on the
 * trail" was "the nearest AT vertex at your latitude, however far east or west
 * that is." A phone in Indianapolis, which shares a latitude with the trail in
 * Maryland, was told it was standing on it - and told confidently, with a mile
 * number in the header, because nothing downstream looked at offTrailFeet.
 *
 * Three miles rather than a rounder number because it has to fit inside the
 * bucket search: from anywhere inside a bucket, the ±1 neighbours cover at
 * least BUCKET_DEGREES (about 3.45 miles) in each direction, so every point
 * within this radius is guaranteed to be a candidate. A wider gate would pass
 * or fail depending on where in its bucket the fix happened to land, which is
 * a worse thing to be than merely conservative.
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

interface Bucket {
  /** Indices into the flat coordinate arrays. */
  indices: number[]
}

/**
 * The bucketed vertices of some set of lines, with no mile axis on them.
 *
 * {@link TrailIndex} is structurally one of these, which is deliberate: the
 * centerline and the full tread are searched by exactly the same code, and
 * only one of the two carries miles.
 */
interface VertexIndex {
  lons: Float64Array
  lats: Float64Array
  buckets: Map<number, Bucket>
}

export interface TrailIndex {
  lons: Float64Array
  lats: Float64Array
  miles: Float64Array
  buckets: Map<number, Bucket>
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
}

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

function bucketFor(lat: number): number {
  return Math.floor(lat / BUCKET_DEGREES)
}

type Coordinates = Array<[number, number]>

/** Buckets a set of coordinate runs by latitude, for nearest-vertex search. */
function buildVertexIndex(runs: Coordinates[]): VertexIndex {
  const flat: Coordinates = runs.flat()
  const count = flat.length

  const lons = new Float64Array(count)
  const lats = new Float64Array(count)
  const buckets = new Map<number, Bucket>()

  for (let i = 0; i < count; i += 1) {
    const [lon, lat] = flat[i]
    lons[i] = lon
    lats[i] = lat

    const key = bucketFor(lat)
    const bucket = buckets.get(key)
    if (bucket === undefined) buckets.set(key, { indices: [i] })
    else bucket.indices.push(i)
  }

  return { lons, lats, buckets }
}

/**
 * Builds the mile index from the centerline features of trails.geojson.
 * Spurs and side trails are excluded from it - a mile marker means distance
 * along the AT itself, so a hiker standing on a blue-blazed spur reads the
 * mile of the junction rather than a number measured down the spur.
 *
 * They are not thrown away, though: they are kept separately as `tread`, which
 * is what answers "is this fix on a trail at all". See {@link TrailFix} for
 * why those two questions cannot share one set of vertices.
 */
export function buildTrailIndex(collection: FeatureCollection): TrailIndex {
  const parts: Coordinates[] = []
  const spurs: Coordinates[] = []

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
      spurs.push(coords)
      continue
    }

    // Flip a piece whose own coordinates run north-to-south, so every piece
    // agrees on which end is Springer before they are ordered.
    const forwards =
      axisProjection(coords[0][0], coords[0][1]) <=
      axisProjection(coords[coords.length - 1][0], coords[coords.length - 1][1])

    parts.push(forwards ? coords : [...coords].reverse())
  }

  parts.sort(
    (a, b) => axisProjection(a[0][0], a[0][1]) - axisProjection(b[0][0], b[0][1]),
  )

  const flat: Coordinates = parts.flat()
  const count = flat.length

  // Where each piece begins in the flattened array. The straight-line jump
  // from the end of one piece to the start of the next is not trail - it is
  // the gap between two pieces the source data never joined - so it must not
  // be added to the running total. Counting those gaps measured the corridor
  // at 4,055 miles against the AT's real ~2,197.
  const partStarts = new Set<number>()
  let offset = 0
  for (const part of parts) {
    partStarts.add(offset)
    offset += part.length
  }

  const lons = new Float64Array(count)
  const lats = new Float64Array(count)
  const miles = new Float64Array(count)
  const buckets = new Map<number, Bucket>()

  let cumulativeFeet = 0

  for (let i = 0; i < count; i += 1) {
    const [lon, lat] = flat[i]
    if (i > 0 && !partStarts.has(i)) {
      const [prevLon, prevLat] = flat[i - 1]
      cumulativeFeet += haversineFeet({ lon: prevLon, lat: prevLat }, { lon, lat })
    }

    lons[i] = lon
    lats[i] = lat
    miles[i] = cumulativeFeet / FEET_PER_MILE

    const key = bucketFor(lat)
    const bucket = buckets.get(key)
    if (bucket === undefined) buckets.set(key, { indices: [i] })
    else bucket.indices.push(i)
  }

  return {
    lons,
    lats,
    miles,
    buckets,
    totalMiles: count === 0 ? 0 : miles[count - 1],
    partStarts: [...partStarts].sort((a, b) => a - b),
    // Centerline included, not just the spurs: the nearest mapped tread to a
    // hiker walking the AT is the AT, and `offTreadFeet` would otherwise
    // report the distance to the nearest blue blaze from the middle of it.
    tread: buildVertexIndex([flat, ...spurs]),
  }
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
 * The trail point nearest a fix. Null when the index is empty or the fix is
 * nowhere near the corridor - farther than MAX_OFF_TRAIL_MILES from any
 * centerline vertex. "We don't know where you are on the trail" is a real
 * answer, and a better one than a mile number measured to a point three states
 * away.
 */
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
 *  enough in latitude to have been bucketed alongside it. */
function nearestVertex(
  index: VertexIndex,
  at: LonLat,
): { index: number; feet: number } | null {
  if (index.lons.length === 0) return null

  const home = bucketFor(at.lat)
  const candidates: number[] = []
  // Neighbouring buckets too, so a fix just inside a boundary still sees the
  // trail points on the other side of it.
  for (const key of [home - 1, home, home + 1]) {
    const bucket = index.buckets.get(key)
    if (bucket !== undefined) candidates.push(...bucket.indices)
  }
  if (candidates.length === 0) return null

  let bestIndex = -1
  let bestFeet = Infinity

  for (const i of candidates) {
    const feet = haversineFeet(at, { lon: index.lons[i], lat: index.lats[i] })
    if (feet < bestFeet) {
      bestFeet = feet
      bestIndex = i
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
 * centerline's 219,293), and a caller placing a POI on the mile axis has no
 * use for it.
 *
 * Worth its own function rather than a flag because of who calls which. This
 * one is called in bulk - App.tsx's `searchablePois` runs it over every POI on
 * the phone, 2,837 of them, in a memo that blocks the main thread; measured
 * 2026-08-15 on x86, `locateOnTrail` over that set costs 975 ms and roughly
 * half of that is the tread scan whose result was being discarded (#717).
 * {@link locateOnTrail} is called once per GPS fix and feeds the wrong-way
 * alert, which needs `offTreadFeet` and must keep paying for it. Splitting
 * them means the cheap path cannot accidentally become the safety path, or
 * the reverse.
 */
export function mileOnTrail(index: TrailIndex, at: LonLat): number | null {
  const onCenterline = nearestVertex(index, at)
  if (onCenterline === null) return null
  if (onCenterline.feet > MAX_OFF_TRAIL_MILES * FEET_PER_MILE) return null
  return index.miles[onCenterline.index]
}

export function locateOnTrail(index: TrailIndex, at: LonLat): TrailFix | null {
  const onCenterline = nearestVertex(index, at)
  if (onCenterline === null) return null

  // Near in latitude is not near. Longitude is not bucketed at all, so the
  // nearest candidate can be most of a continent away and still have been
  // measured - see MAX_OFF_TRAIL_MILES.
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
