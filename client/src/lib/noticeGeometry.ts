// Whether a line a hiker will walk meets a place a notice names (#1805,
// decision 66 and 67).
//
// Two questions in this app turn on it, and both are asked of geometry the
// phone already holds rather than of anything a server answers:
//
//  - lib/plannedNotices.ts: does a notice touch a hike the hiker has planned
//    to start in the next 7 days?
//  - lib/hazardAreas.ts: does a trail this phone has downloaded cross a
//    hunting area, a shooting site or a burned area?
//
// Both are "does this polyline meet that shape", so the arithmetic has one
// home. Nothing here knows what a notice is.
//
// THE MEASURE IS A LOCAL FLAT ONE, on purpose. Every comparison is between a
// shape and a line a few miles long at most, so an equirectangular projection
// about the shape's own latitude is off by well under 1% of the distance it
// measures (Reasoned: the cosine of latitude changes by less than 0.2% across
// the 0.1 degree a notice spans, at 45 N). lib/trailGraph.ts's `localMetres`
// makes the same call for the same reason.

/** `[lon, lat]`, GeoJSON's order and the graph artifact's. */
export type Position = readonly [number, number]

/** A GeoJSON geometry as conditions/notices.json carries one. Typed loosely
 *  on purpose: it is published bytes, read defensively below, and a shape
 *  this module does not recognise meets nothing rather than throwing. */
export interface NoticeGeometryValue {
  type: string
  coordinates?: unknown
  geometries?: unknown
}

export interface Bounds {
  minLon: number
  minLat: number
  maxLon: number
  maxLat: number
}

const FEET_PER_METRE = 3.28084
const METRES_PER_DEGREE_LAT = 110_540
const METRES_PER_DEGREE_LON_AT_EQUATOR = 111_320

/** The parts of a geometry, flattened: its lone points, its lines and its
 *  polygons (each a list of rings, the first the shell). */
export interface GeometryParts {
  points: Position[]
  lines: Position[][]
  polygons: Position[][][]
}

function isPosition(value: unknown): value is Position {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    typeof value[0] === 'number' &&
    typeof value[1] === 'number' &&
    Number.isFinite(value[0]) &&
    Number.isFinite(value[1])
  )
}

function positions(value: unknown): Position[] {
  return Array.isArray(value) ? value.filter(isPosition).map((p) => [p[0], p[1]]) : []
}

function rings(value: unknown): Position[][] {
  return Array.isArray(value)
    ? value.map(positions).filter((ring) => ring.length >= 3)
    : []
}

/**
 * How many GeometryCollections deep a geometry may nest before the whole of it
 * reads as having no parts.
 *
 * RFC 7946 §3.1.8 asks producers not to nest collections at all, and DuckDB's
 * `ST_AsGeoJSON`, which writes conditions/notices.json, does not nest them
 * (Reasoned, not measured). The bound is for a corrupted or hostile file: in
 * the review of #1805 — dlt → dbt re-platform as one go/no-go change, a row
 * nested 20,000 deep overflowed the stack in vitest on 2026-10-05, which on
 * a phone is inside a hook `App` renders, so the whole app goes down, and
 * the copy the phone kept repeats it offline.
 *
 * @unvalidated 8 is picked: deeper than anything a producer here writes, and
 * nine frames of recursion at most. What would settle it: a real source that
 * nests deeper, which none is known to.
 */
export const MAX_COLLECTION_DEPTH = 8

/** A geometry's parts, or empty parts for one this module cannot read - or
 *  one nested past {@link MAX_COLLECTION_DEPTH}, of which none is kept. */
export function geometryParts(
  geometry: NoticeGeometryValue | null | undefined,
): GeometryParts {
  const parts: GeometryParts = { points: [], lines: [], polygons: [] }
  return addParts(parts, geometry, 0) ? parts : { points: [], lines: [], polygons: [] }
}

/** Adds one geometry's parts to `parts`; false once it nests too deep. */
function addParts(
  parts: GeometryParts,
  geometry: NoticeGeometryValue | null | undefined,
  depth: number,
): boolean {
  if (geometry === null || geometry === undefined || typeof geometry !== 'object')
    return true
  const { coordinates } = geometry
  switch (geometry.type) {
    case 'Point':
      if (isPosition(coordinates)) parts.points.push([coordinates[0], coordinates[1]])
      break
    case 'MultiPoint':
      parts.points.push(...positions(coordinates))
      break
    case 'LineString': {
      const line = positions(coordinates)
      if (line.length >= 2) parts.lines.push(line)
      break
    }
    case 'MultiLineString':
      if (Array.isArray(coordinates)) {
        for (const member of coordinates) {
          const line = positions(member)
          if (line.length >= 2) parts.lines.push(line)
        }
      }
      break
    case 'Polygon': {
      const polygon = rings(coordinates)
      if (polygon.length > 0) parts.polygons.push(polygon)
      break
    }
    case 'MultiPolygon':
      if (Array.isArray(coordinates)) {
        for (const member of coordinates) {
          const polygon = rings(member)
          if (polygon.length > 0) parts.polygons.push(polygon)
        }
      }
      break
    case 'GeometryCollection':
      if (depth >= MAX_COLLECTION_DEPTH) return false
      if (Array.isArray(geometry.geometries)) {
        for (const member of geometry.geometries as NoticeGeometryValue[]) {
          if (!addParts(parts, member, depth + 1)) return false
        }
      }
      break
    default:
      break
  }
  return true
}

/** The box around a geometry's parts, or null when it has none. */
export function partsBounds(parts: GeometryParts): Bounds | null {
  let minLon = Infinity
  let minLat = Infinity
  let maxLon = -Infinity
  let maxLat = -Infinity
  const take = (p: Position) => {
    if (p[0] < minLon) minLon = p[0]
    if (p[0] > maxLon) maxLon = p[0]
    if (p[1] < minLat) minLat = p[1]
    if (p[1] > maxLat) maxLat = p[1]
  }
  parts.points.forEach(take)
  parts.lines.forEach((line) => line.forEach(take))
  parts.polygons.forEach((polygon) => polygon[0]?.forEach(take))
  return Number.isFinite(minLon) ? { minLon, minLat, maxLon, maxLat } : null
}

/** A box grown by `feet` on every side, in degrees at its own latitude. */
export function grownBounds(bounds: Bounds, feet: number): Bounds {
  const metres = feet / FEET_PER_METRE
  const midLat = (bounds.minLat + bounds.maxLat) / 2
  const dLat = metres / METRES_PER_DEGREE_LAT
  const dLon =
    metres /
    (METRES_PER_DEGREE_LON_AT_EQUATOR *
      Math.max(Math.cos((midLat * Math.PI) / 180), 0.01))
  return {
    minLon: bounds.minLon - dLon,
    minLat: bounds.minLat - dLat,
    maxLon: bounds.maxLon + dLon,
    maxLat: bounds.maxLat + dLat,
  }
}

function segmentInBounds(a: Position, b: Position, box: Bounds): boolean {
  return !(
    Math.max(a[0], b[0]) < box.minLon ||
    Math.min(a[0], b[0]) > box.maxLon ||
    Math.max(a[1], b[1]) < box.minLat ||
    Math.min(a[1], b[1]) > box.maxLat
  )
}

/** Ray casting, on lon/lat as a plane: exact enough inside one notice's area. */
function inRing(p: Position, ring: readonly Position[]): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}

/** Inside the shell and outside every hole. */
export function inPolygon(
  p: Position,
  polygon: readonly (readonly Position[])[],
): boolean {
  if (polygon.length === 0 || !inRing(p, polygon[0])) return false
  for (let h = 1; h < polygon.length; h += 1) if (inRing(p, polygon[h])) return false
  return true
}

/** Local metres about a latitude: x east, y north. */
function projector(refLat: number) {
  const kx = METRES_PER_DEGREE_LON_AT_EQUATOR * Math.cos((refLat * Math.PI) / 180)
  return (p: Position): [number, number] => [p[0] * kx, p[1] * METRES_PER_DEGREE_LAT]
}

function cross(ax: number, ay: number, bx: number, by: number): number {
  return ax * by - ay * bx
}

function segmentsCross(
  a: [number, number],
  b: [number, number],
  c: [number, number],
  d: [number, number],
): boolean {
  const d1 = cross(d[0] - c[0], d[1] - c[1], a[0] - c[0], a[1] - c[1])
  const d2 = cross(d[0] - c[0], d[1] - c[1], b[0] - c[0], b[1] - c[1])
  const d3 = cross(b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1])
  const d4 = cross(b[0] - a[0], b[1] - a[1], d[0] - a[0], d[1] - a[1])
  return d1 * d2 <= 0 && d3 * d4 <= 0 && !(d1 === 0 && d2 === 0 && d3 === 0 && d4 === 0)
}

function pointSegmentMetres(
  p: [number, number],
  a: [number, number],
  b: [number, number],
): number {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const length2 = dx * dx + dy * dy
  const t =
    length2 === 0
      ? 0
      : Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
  const x = a[0] + t * dx - p[0]
  const y = a[1] + t * dy - p[1]
  return Math.sqrt(x * x + y * y)
}

function segmentSegmentMetres(
  a: [number, number],
  b: [number, number],
  c: [number, number],
  d: [number, number],
): number {
  if (segmentsCross(a, b, c, d)) return 0
  return Math.min(
    pointSegmentMetres(a, c, d),
    pointSegmentMetres(b, c, d),
    pointSegmentMetres(c, a, b),
    pointSegmentMetres(d, a, b),
  )
}

/**
 * Whether any of `lines` comes within `reachFeet` of the geometry: enters a
 * polygon or crosses its edge, or passes within reach of a line, a point or
 * a polygon's edge.
 *
 * A polygon a line runs inside is met at zero distance, so an area a trail
 * crosses is met whatever the reach. The reach exists for the rest: a point
 * notice or a line notice published on one organization's map of a tread
 * another organization drew a few metres away.
 */
export function linesMeetParts(
  lines: readonly (readonly Position[])[],
  parts: GeometryParts,
  reachFeet: number,
): boolean {
  const bounds = partsBounds(parts)
  if (bounds === null) return false
  const box = grownBounds(bounds, reachFeet)
  const reachMetres = reachFeet / FEET_PER_METRE
  const project = projector((bounds.minLat + bounds.maxLat) / 2)

  const pieces: Array<[Position, Position]> = []
  for (const line of lines) {
    for (let i = 0; i + 1 < line.length; i += 1) {
      if (segmentInBounds(line[i], line[i + 1], box)) pieces.push([line[i], line[i + 1]])
    }
    if (line.length === 1 && segmentInBounds(line[0], line[0], box)) {
      pieces.push([line[0], line[0]])
    }
  }
  if (pieces.length === 0) return false

  for (const polygon of parts.polygons) {
    for (const [a, b] of pieces) {
      if (inPolygon(a, polygon) || inPolygon(b, polygon)) return true
    }
  }

  const edges: Array<[Position, Position]> = []
  for (const polygon of parts.polygons) {
    for (const ring of polygon) {
      for (let i = 0; i + 1 < ring.length; i += 1) edges.push([ring[i], ring[i + 1]])
    }
  }
  for (const line of parts.lines) {
    for (let i = 0; i + 1 < line.length; i += 1) edges.push([line[i], line[i + 1]])
  }
  for (const point of parts.points) edges.push([point, point])

  for (const [a, b] of pieces) {
    const pa = project(a)
    const pb = project(b)
    for (const [c, d] of edges) {
      if (segmentSegmentMetres(pa, pb, project(c), project(d)) <= reachMetres) return true
    }
  }
  return false
}

/** {@link linesMeetParts} over a published geometry. */
export function linesMeetGeometry(
  lines: readonly (readonly Position[])[],
  geometry: NoticeGeometryValue | null | undefined,
  reachFeet: number,
): boolean {
  return linesMeetParts(lines, geometryParts(geometry), reachFeet)
}

/**
 * Whether a place is inside one of a geometry's polygons AND farther than
 * `marginMetres` from every edge of it - decision 76's question of a state's
 * simplified shape (lib/plannedNotices.ts). A place near an edge answers no,
 * on purpose: the shape is a simplification, and near its edge it cannot
 * tell one state from the next.
 *
 * Measured about the place's own latitude rather than the shape's, because
 * a state spans degrees of latitude and the margin is about the place.
 */
export function insideByMoreThan(
  at: Position,
  parts: GeometryParts,
  marginMetres: number,
): boolean {
  const project = projector(at[1])
  const here = project(at)
  for (const polygon of parts.polygons) {
    if (!inPolygon(at, polygon)) continue
    let nearEdge = false
    for (const ring of polygon) {
      for (let i = 0; i + 1 < ring.length && !nearEdge; i += 1) {
        nearEdge =
          pointSegmentMetres(here, project(ring[i]), project(ring[i + 1])) <= marginMetres
      }
      if (nearEdge) break
    }
    return !nearEdge
  }
  return false
}

/** Whether one place is inside one of a geometry's polygons, or within
 *  `reachFeet` of its points and lines - the tapped-line card's question. */
export function positionMeetsParts(
  at: Position,
  parts: GeometryParts,
  reachFeet: number,
): boolean {
  return linesMeetParts([[at, at]], parts, reachFeet)
}
