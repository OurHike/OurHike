// Routing a day hike over the junction graph, on the phone, with no backend
// (#975, features/HIKE_PLANNING.md "The day hike on a network",
// pipeline/build_trail_graph.py).
//
// #757 already closed the "routing runs on the phone" question for the A.T. -
// a shortest path over ~3,000 edges, no backend, no network. This is that
// precedent applied to a park, where the thing being searched is a real graph
// rather than one line's mile axis.
//
// The graph outgrew that estimate: 40,596 edges and 755,326 vertices on the
// published artifact (data.ourhike.org, 2026-08-27), thirteen times #757's
// figure. #1020 is where that was measured rather than feared, and the answer
// was not the one the issue expected. Timed here against those bytes, 400
// taps on real vertices and 200 fixed journeys:
//
//   a tap    85.5 ms  ->  0.021 ms   (median, {@link EdgeGrid})
//   a route   0.057 ms ->  0.041 ms  (median, Harriman-sized, {@link NodeHeap})
//   a long route  0.108 ms -> 0.055 ms   (median, >40 km apart)
//
// Both changes return the same answers - 400 of 400 taps identical, and the
// 200 journeys identical to six decimal places. The tap was the whole cost
// and the search was never it, which is worth stating because a reader coming
// from #757's sentence would assume the opposite.
//
// EVERY MILE HERE IS THE GRAPH'S METRE, CONVERTED ONCE
//
// HIKE_PLANNING.md Finding 1 exists because this codebase has two different
// measurements of a mile and summing across them drifts silently. This module
// adds no third one: build_trail_graph.py measures every edge in EPSG:5070
// metres, this converts at the boundary, and nothing here is ever compared
// against `lib/trailPosition.ts`'s centerline mile or `StoredPoi.mile`. A day
// hike in a park has no A.T. mile and does not want one.
//
// A TAP SPLITS THE SEGMENT
//
// The decision recorded in features/HIKE_PLANNING.md from #934, and the reason
// `GraphPoint` carries an edge and a fraction along it rather than a node id.
// The route runs exactly between the two tapped points. This builder does not
// decide the hiker meant the junction, or the trailhead, or the nearest
// shelter - #771 measured a junction every 1.2 trail-miles through
// Harriman-Bear Mountain, so snapping to one would move a start by ~0.6 mi on
// average, which is a material piece of a six-mile day and an arbitrary one.
//
// WHAT IT REFUSES, AND WHY THAT IS THE POINT
//
// A tap that is not on a maintained line is refused rather than placed. Frame
// `1j`'s copy is the specification: "That tap isn't on a marked hiking route.
// OurHike only builds routes on trails an organization maintains." That is
// `trailPosition.ts`'s existing off-corridor refusal - it declines rather than
// inventing a plausible mile - carried onto a network. A route that cannot be
// found is said, never approximated: FEATURES.md's "a confidently wrong
// prediction is more dangerous than an honest unknown", on the screen where a
// hiker decides where to walk.
//
// Closed trails never reach here at all. build_trail_graph.py refuses them at
// the artifact, so there is no code path in this module that could route down
// one, which is deliberate - a filter here would be a second place to get it
// wrong.

/** One end of an edge, indexed into {@link TrailGraph.nodes}. */
export interface GraphEdge {
  from: number
  to: number
  /** EPSG:5070 metres, as measured by pipeline/build_trail_graph.py. */
  length_m: number
  trail_id: string | null
  source: string | null
  name: string | null
  blaze_color: string | null
  /**
   * The piece's own vertices, `[lon, lat]` in from->to order. Optional
   * because a graph published before it existed still routes; without it an
   * edge projects and draws as the straight chord between its nodes, which
   * across a switchback is a picture of a trail that does not exist - so
   * {@link routeGeometry} returns null rather than drawing chords.
   */
  geometry?: Array<[number, number]>
  /**
   * `[gain_ft, loss_ft]` along the whole edge, from
   * pipeline/export_network_elevation.py, attached by
   * lib/trailGraphData.ts when the builder opens.
   *
   * `undefined` means this phone has not fetched the elevation artifact;
   * `null` means the artifact HAS it and nobody has measured this edge - a
   * DEM gap. Both stop {@link routeClimb} answering, and they must: the two
   * are different facts but the honest reply to a hiker is the same one.
   * Never 0, which would be the claim that the ground is flat.
   */
  climb?: [number, number] | null
}

/** The artifact as published: nodes are `[lon, lat]`. */
export interface TrailGraph {
  nodes: Array<[number, number]>
  edges: GraphEdge[]
}

// trailPosition.ts's own coordinate type, re-exported so this module's
// callers need not import from two places. The MILES of the two modules must
// never meet (Finding 1); their coordinates are the same thing.
export type { LonLat } from './trailPosition'
import type { LonLat } from './trailPosition'

/**
 * A place on the network: an edge, and how far along it.
 *
 * `fraction` is 0 at the edge's `from` and 1 at its `to`. A tap almost never
 * lands on a junction, and this is the type that lets it not have to.
 */
export interface GraphPoint {
  edgeIndex: number
  fraction: number
  /** Where the point actually is, after being pulled onto the line. */
  at: LonLat
  /** How far the tap was from the line, in feet. */
  offNetworkFeet: number
}

/** A run of consecutive edges along one named trail - what frame `1l` lists. */
export interface RouteLeg {
  name: string | null
  source: string | null
  blaze_color: string | null
  trail_id: string | null
  miles: number
  /**
   * Other organizations whose designation shares this leg's tread (#1115),
   * distinct and never containing `source` itself. Omitted - not `[]` - when
   * there are none, so a leg predating the field round-trips unchanged.
   *
   * Exists for the credit surfaces. Where the Long Path runs along the High
   * Point Trail, {@link holdDesignation} keeps the leg under one name, and
   * without this the org whose name was folded away would vanish from "N
   * organizations keep this loop walkable" - the silently-dropped steward
   * #1115 warns the merge must not produce. Which of the two names the leg
   * WEARS is arbitrary (whichever the walk entered on); who gets credit is
   * not.
   */
  concurrent_sources?: string[]
}

/**
 * One leg of a walk, between two consecutive taps, as the router built it.
 *
 * WHAT `edgeIndices` CANNOT SAY (#1040). That list is deduplicated across the
 * join between legs - the shared edge is drawn once - and an out-and-back
 * therefore collapses to the edges it used, losing the turnaround entirely.
 * Right for drawing a line twice over the same ground, and wrong as the ONLY
 * record of the walk: `routeGeometry` trims the first and last edges to the
 * tapped fractions, so the whole out-and-back gets trimmed to the span
 * between its first and last tap.
 *
 * Measured on a single edge with taps at fractions 0.2, 0.8 and 0.2: the
 * route is 0.62 mi and correct, and the drawing was NULL - a bar reading
 * "1 leg · 0.6 mi · ≈12m walking" over a map with no route on it. Stopping
 * partway back (0.2, 0.8, 0.5) drew only 0.2→0.5, silently omitting the
 * stretch the hiker walks twice.
 *
 * So each leg keeps its own ends, and {@link routeLines} draws leg by leg.
 */
export interface RouteSection {
  /** This leg's edges alone, in walking order - NOT deduplicated against its
   *  neighbours, because each leg is drawn on its own. */
  edgeIndices: number[]
  from: GraphPoint
  to: GraphPoint
}

export interface GraphRoute {
  legs: RouteLeg[]
  miles: number
  /**
   * Every edge the walk touches, in walking order, deduplicated across leg
   * joins.
   *
   * For asking WHICH TRAILS a walk uses - the org tally, the bail-outs, the
   * climb. NOT for drawing: see {@link RouteSection}, and use
   * {@link routeLines}.
   */
  edgeIndices: number[]
  /** The legs as walked, each with its own ends. What drawing follows. */
  sections: RouteSection[]
  /** Legs per organization, which frame `1j` tallies while the hiker builds. */
  legsBySource: Array<{ source: string | null; legs: number }>
  /**
   * Ascent and descent over this walk, or null when this phone cannot price it
   * - no elevation artifact fetched, or an edge of the walk that nobody has
   * measured. See {@link routeClimb}; the null carries all the way to the
   * card, which says so rather than printing a figure.
   */
  climb: RouteClimb | null
}

/**
 * How far off a line a tap may land and still count as being on it.
 *
 * @unvalidated - a fingertip on a phone at a planning zoom, not a measurement.
 * What would settle it: the smallest value at which taps on a drawn line stop
 * being refused in a real hand on a real device, which nobody has tried.
 *
 * Rounded small on purpose, and the reason is the same #771 number that shapes
 * the pipeline's tolerance: 48% of sampled A.T. points through Harriman sit
 * within 150 m of a DIFFERENT marked trail (features/NEARBY_TRAILS.md). A
 * generous tap radius in that corridor does not merely accept a sloppy tap, it
 * picks between two trails on the hiker's behalf and says nothing. A refused
 * tap costs one more tap; a silently reassigned one puts somebody on a
 * different trail than the one they pointed at.
 */
export const MAX_OFF_NETWORK_FEET = 150

/**
 * How far a DRAWN line may be from a trail and still be matched to it.
 *
 * The maintainer's answer on #935, 2026-08-27, verbatim: *"Ask which trail.
 * But only match to trails within 25M."*
 *
 * TIGHTER THAN A TAP, AND THAT IS THE POINT. {@link MAX_OFF_NETWORK_FEET} is
 * 150 ft (45.7 m) and governs a finger aimed at one spot; this governs a
 * stroke swept across a map, where every sample is a candidate and a generous
 * radius reaches two trails at once far more often than a single tap does.
 *
 * WHAT THE NUMBER DOES AND DOES NOT BUY, stated because the two are easy to
 * conflate. It is a REACH limit: past 25 m nothing matches, which under the
 * segments model ends a stretch rather than refusing the walk. It is NOT a
 * disambiguation rule - inside 25 m two marked trails can still both be
 * candidates, and #935's other half is that the app ASKS rather than taking
 * the nearer. See {@link trailsNear}.
 *
 * @unvalidated - nobody has drawn on this outdoors, which is what #935 says
 * would settle it. What can be said with evidence is the direction: through
 * Harriman-Bear Mountain, 48% of sampled A.T. points sit within 150 m of a
 * different marked trail (features/NEARBY_TRAILS.md, measured by #771), so 25
 * m reduces the ambiguous fraction - by how much, nobody has measured. What
 * would settle it is somebody drawing a route on a phone in that park.
 */
export const DRAWN_SNAP_METRES = 25

const FEET_PER_METRE = 3.280839895
const METRES_PER_MILE = 1609.344

/** Metres to miles. The one conversion in this module, on purpose. */
export function metresToMiles(metres: number): number {
  return metres / METRES_PER_MILE
}

/** The two fields that decide whether two pieces of tread are one trail. */
export interface TrailIdentity {
  trail_id: string | null
  name: string | null
}

/**
 * Whether two pieces of tread belong to the same trail.
 *
 * Extracted rather than written out a fourth time, because FOUR things read
 * this rule and one of them is new: where a leg ends ({@link legsFromEdges},
 * `legsFromWalk`, {@link routeThrough}'s merge across a join) and where a TURN
 * happens (lib/dayHikeTurns.ts). A turn list that disagreed with the leg list
 * about where Pine Meadow becomes Seven Hills would print "leg 2 of 3" over a
 * card naming the wrong trail - one predicate makes them agree by
 * construction rather than by three call sites staying in step.
 *
 * BOTH fields, and `trail_id` alone will not do: the artifact carries a null
 * id for every piece no source numbered, and comparing ids alone would
 * collapse all of those into one leg spanning four trails. Comparing NAMES
 * alone has the mirror fault where two sources both publish "Blue Trail".
 */
export function sameTrail(a: TrailIdentity, b: TrailIdentity): boolean {
  return a.trail_id === b.trail_id && a.name === b.name
}

/**
 * How much two same-tread edges' lengths may differ beyond
 * {@link SAME_TREAD_METRES}' absolute allowance: 5% of the longer.
 *
 * The relative half of {@link sameTread}'s length probe, and the only number
 * that gate adds - both of its distances reuse `SAME_TREAD_METRES`, which is
 * already the module's one derived answer to "the same place". Measured on
 * the 2026-08-27 population `sameTread` documents: within the 8 m separation
 * gate, absolute length differences run median 0.1 m / p99 6.7 m, so the 8 m
 * floor covers the tracing noise; this ceiling is what keeps that floor from
 * swallowing long edges, where 5% of a mile is ~80 m of extra ground - a
 * different path, not a different tracing of one.
 */
export const SAME_TREAD_MAX_LENGTH_DELTA_RATIO = 0.05

/** The point this far along an edge's own polyline, by arc length. */
function pointAtFraction(vertices: Array<[number, number]>, fraction: number): LonLat {
  const points: LonLat[] = vertices.map(([lon, lat]) => ({ lon, lat }))
  const segments: number[] = []
  let total = 0
  for (let step = 0; step + 1 < points.length; step += 1) {
    const span = localMetres(points[step], points[step + 1])
    const length = Math.hypot(span.x, span.y)
    segments.push(length)
    total += length
  }
  let remaining = total * fraction
  for (let step = 0; step < segments.length; step += 1) {
    if (remaining <= segments[step] || step === segments.length - 1) {
      const t = segments[step] === 0 ? 0 : remaining / segments[step]
      const a = points[step]
      const b = points[step + 1]
      return { lon: a.lon + (b.lon - a.lon) * t, lat: a.lat + (b.lat - a.lat) * t }
    }
    remaining -= segments[step]
  }
  return points[points.length - 1]
}

/**
 * Whether two edges between the same pair of nodes are the same physical
 * ground - two organizations' digitisations of one tread - rather than two
 * different paths that happen to share both junctions.
 *
 * The distinction is what makes swapping between them safe. A concurrency
 * (the Long Path riding the High Point Trail) is one tread wearing two names,
 * and either edge honestly stands for the walk; a fork that rejoins is two
 * treads, and swapping onto the unrouted one would draw a hiker a line they
 * are not on. False negatives here cost a fragmented leg list - today's
 * behaviour; false positives put the route on the wrong ground. So every
 * probe rounds toward refusal, including the geometry requirement: an edge
 * without vertices offers no evidence it is the same ground, and no evidence
 * reads as "no".
 *
 * Both distances are {@link SAME_TREAD_METRES} - the module's one derived
 * answer to "the same place", now read a third time - and both probes are
 * MEASURED to carry their weight, 2026-08-27, against every
 * different-identity edge pair sharing a node pair in the published
 * trail_graph.json + geometry (data.ourhike.org UA, 42,103 edges; 7,407 such
 * pairs, of which this gate passes 6,637):
 *
 * - Geometry, probed at 1/4, 1/2 and 3/4 of each polyline: the passing
 *   population sits at median 0.0 m separation; past the gate the pairs are
 *   different ground between the same junctions ("Ice Caves Trail", 912 m,
 *   beside its 27 m access road; "Lenape Ridge Trail" beside "Minisink",
 *   276 m apart at the probes with lengths 1.9% alike - the pair proving
 *   length alone cannot answer this).
 * - Length, within `SAME_TREAD_METRES` absolute or 5% relative: the absolute
 *   floor is what makes short edges judgeable at all. On the Long Path /
 *   High Point Trail concurrency #1115 reports, two digitisations of one
 *   ~20 m piece differ by up to 20% RELATIVE while sitting 1-6 m apart, so a
 *   purely relative gate refused half the exact case this exists for (64 of
 *   its 132 pairs; this gate passes all 132). Within the separation gate,
 *   absolute differences run median 0.1 m / p99 6.7 m - under the floor.
 *
 * The eventual honest home for this fact is the artifact - one edge carrying
 * both designations, #1115's third option - at which point this measured
 * bridge retires.
 */
export function sameTread(graph: TrailGraph, aIndex: number, bIndex: number): boolean {
  const a = graph.edges[aIndex]
  const b = graph.edges[bIndex]
  const samePair =
    (a.from === b.from && a.to === b.to) || (a.from === b.to && a.to === b.from)
  if (!samePair || a.from === a.to) return false

  const longer = Math.max(a.length_m, b.length_m)
  const allowed = Math.max(SAME_TREAD_METRES, SAME_TREAD_MAX_LENGTH_DELTA_RATIO * longer)
  if (Math.abs(a.length_m - b.length_m) > allowed) return false

  if (!hasVertices(a) || !hasVertices(b)) return false
  for (const fraction of [0.25, 0.5, 0.75]) {
    const here = pointAtFraction(a.geometry, fraction)
    // The two digitisations may store their vertices in opposite orders, so
    // the matching point on b is at `fraction` from one end or the other.
    const separation = Math.min(
      metresBetween(here, pointAtFraction(b.geometry, fraction)),
      metresBetween(here, pointAtFraction(b.geometry, 1 - fraction)),
    )
    if (separation > SAME_TREAD_METRES) return false
  }
  return true
}

function metresBetween(a: LonLat, b: LonLat): number {
  const span = localMetres(a, b)
  return Math.hypot(span.x, span.y)
}

/** Every other edge between the same pair of nodes, via the adjacency lists. */
function parallelsOf(index: TrailGraphIndex, edgeIndex: number): number[] {
  const edge = index.graph.edges[edgeIndex]
  if (edge.from === edge.to) return []
  const out: number[] = []
  for (const step of index.adjacency[edge.from] ?? []) {
    if (step.to === edge.to && step.edgeIndex !== edgeIndex) out.push(step.edgeIndex)
  }
  return out
}

/**
 * The routed edges, re-picked to stay on the designation the walk is already
 * on wherever the same tread carries it (#1115).
 *
 * Where two organizations' trails run together, the artifact holds the shared
 * tread twice - 7,407 different-identity edge pairs share a node pair in the
 * published graph - and the shortest-path search picks between the near-equal
 * twins arbitrarily, hopping designation every few metres. Every reader of
 * the result inherits the hops: the leg list fragments into "0.0 mi" rows,
 * and {@link sameTrail}'s other callers (the turn list, the follow matcher)
 * see a trail change on every one.
 *
 * This is #1115's router option, done as a pass over the found path rather
 * than inside Dijkstra: for each interior edge that changes designation,
 * swap in a {@link sameTread} twin that keeps it, if one exists. The first
 * and last edges are never touched - a tap's `fraction` is a fraction of that
 * specific edge's geometry. Swapping trades one digitisation of the ground
 * for another, so lengths shift by tracing noise (median 0.1 m per edge on
 * the same-tread population); the caller re-prices the walk from the swapped
 * list rather than keeping the search's total.
 */
export function holdDesignation(index: TrailGraphIndex, edgeIndices: number[]): number[] {
  if (edgeIndices.length < 3) return edgeIndices
  const out = edgeIndices.slice()
  for (let at = 1; at + 1 < out.length; at += 1) {
    const previous = index.graph.edges[out[at - 1]]
    if (sameTrail(previous, index.graph.edges[out[at]])) continue
    for (const candidate of parallelsOf(index, out[at])) {
      if (!sameTrail(previous, index.graph.edges[candidate])) continue
      if (!sameTread(index.graph, out[at], candidate)) continue
      out[at] = candidate
      break
    }
  }
  return out
}

/**
 * The other organizations sharing this edge's tread, for the leg's
 * `concurrent_sources` - see that field's comment for why credit must survive
 * the designation being folded away.
 */
function concurrentSourcesOf(index: TrailGraphIndex, edgeIndex: number): string[] {
  const edge = index.graph.edges[edgeIndex]
  const sources = new Set<string>()
  for (const candidate of parallelsOf(index, edgeIndex)) {
    const other = index.graph.edges[candidate]
    if (other.source === null || other.source === edge.source) continue
    if (sameTrail(edge, other)) continue
    if (!sameTread(index.graph, edgeIndex, candidate)) continue
    sources.add(other.source)
  }
  return [...sources]
}

/**
 * The compass bearing from one point to another - degrees clockwise from
 * north, in [0, 360).
 *
 * Equirectangular through {@link localMetres}, like every other distance in
 * this module and for the same reason: the only points a bearing is taken
 * between here are two vertices of one piece of trail, tens of metres apart,
 * where the difference from a great-circle bearing is orders of magnitude
 * below the question being asked of it (which side of a junction a trail
 * leaves on).
 */
export function bearingDegrees(from: LonLat, to: LonLat): number {
  const span = localMetres(from, to)
  // atan2(x, y) rather than the usual (y, x): this is a compass bearing, so
  // it is measured clockwise from north (+y) rather than counter-clockwise
  // from east.
  return ((Math.atan2(span.x, span.y) * 180) / Math.PI + 360) % 360
}

interface Adjacency {
  edgeIndex: number
  to: number
}

export interface TrailGraphIndex {
  graph: TrailGraph
  adjacency: Adjacency[][]
  /**
   * The edges that carry vertices, bucketed by where they are (#1020).
   *
   * Null until geometry attaches, which is not a degraded state: an edge with
   * no vertices is not a snap candidate at all ({@link nearestPointOnGraph}),
   * so before `trail_graph_geometry.json` lands there is nothing to index and
   * nothing to search.
   */
  grid: EdgeGrid | null
}

/**
 * Adjacency lists and the spatial grid, built once per loaded artifact.
 *
 * Called again by lib/trailGraphData.ts when geometry attaches, which is
 * where the grid actually gets built - see {@link buildEdgeGrid}.
 */
export function buildGraphIndex(graph: TrailGraph): TrailGraphIndex {
  const adjacency: Adjacency[][] = graph.nodes.map(() => [])
  graph.edges.forEach((edge, edgeIndex) => {
    if (!adjacency[edge.from] || !adjacency[edge.to]) return
    adjacency[edge.from].push({ edgeIndex, to: edge.to })
    adjacency[edge.to].push({ edgeIndex, to: edge.from })
  })
  return { graph, adjacency, grid: buildEdgeGrid(graph) }
}

/**
 * A cell of the search grid, in degrees.
 *
 * The same 0.05 deg lib/trailPosition.ts buckets the A.T. centerline into,
 * and picked there for the same reason: it is comfortably larger than any
 * search radius this module uses, so a query reads one or two cells rather
 * than a neighbourhood of them. About 5.5 km of latitude, and 4.2 km of
 * longitude at Harriman's 41.2 deg.
 *
 * Unlike trailPosition.ts, this buckets on BOTH axes. That file indexes one
 * linear trail, where a band of latitude holds only the piece of trail at
 * that latitude; this indexes a statewide network, where a band at 41.2 deg
 * would hold every edge from the Delaware Water Gap to the Connecticut line.
 */
const GRID_DEGREES = 0.05

/** Key range wide enough for every longitude bucket on Earth (-3600..3600). */
const GRID_STRIDE = 20_000

/**
 * Every edge that carries vertices, filed under each grid cell its bounding
 * box touches, with those bounding boxes kept alongside.
 *
 * WHY THIS EXISTS. {@link nearestPointOnGraph} projected a tap onto every
 * edge in the graph and kept the nearest - 40,596 edges and 755,326 vertices
 * on the published artifact (data.ourhike.org, 2026-08-27), for an answer
 * that can only come from the handful of edges within 150 ft of the finger.
 * #1093 made that worse rather than better by moving the projection onto each
 * edge's own vertices, which is the right rule and the more expensive one.
 *
 * The cost was never noticeable while a tap was the only thing that asked.
 * A drawn line (#983) asks once per sample.
 *
 * An edge is filed under every cell its BOX touches rather than every cell it
 * crosses, so a long diagonal edge is over-filed and never under-filed. The
 * error is candidates that the box test then rejects, which is the direction
 * that cannot lose an answer.
 */
export interface EdgeGrid {
  cells: Map<number, number[]>
  minLon: Float64Array
  minLat: Float64Array
  maxLon: Float64Array
  maxLat: Float64Array
}

function buildEdgeGrid(graph: TrailGraph): EdgeGrid | null {
  const count = graph.edges.length
  const minLon = new Float64Array(count)
  const minLat = new Float64Array(count)
  const maxLon = new Float64Array(count)
  const maxLat = new Float64Array(count)
  const cells = new Map<number, number[]>()
  let indexed = 0

  for (let edgeIndex = 0; edgeIndex < count; edgeIndex += 1) {
    const edge = graph.edges[edgeIndex]
    if (!hasVertices(edge)) continue
    indexed += 1

    let loLon = Infinity
    let loLat = Infinity
    let hiLon = -Infinity
    let hiLat = -Infinity
    for (const [lon, lat] of edge.geometry) {
      if (lon < loLon) loLon = lon
      if (lat < loLat) loLat = lat
      if (lon > hiLon) hiLon = lon
      if (lat > hiLat) hiLat = lat
    }
    minLon[edgeIndex] = loLon
    minLat[edgeIndex] = loLat
    maxLon[edgeIndex] = hiLon
    maxLat[edgeIndex] = hiLat

    const latFrom = Math.floor(loLat / GRID_DEGREES)
    const latTo = Math.floor(hiLat / GRID_DEGREES)
    const lonFrom = Math.floor(loLon / GRID_DEGREES)
    const lonTo = Math.floor(hiLon / GRID_DEGREES)
    for (let latBucket = latFrom; latBucket <= latTo; latBucket += 1) {
      for (let lonBucket = lonFrom; lonBucket <= lonTo; lonBucket += 1) {
        const key = latBucket * GRID_STRIDE + lonBucket + GRID_STRIDE / 2
        const cell = cells.get(key)
        if (cell === undefined) cells.set(key, [edgeIndex])
        else cell.push(edgeIndex)
      }
    }
  }

  if (indexed === 0) return null
  return { cells, minLon, minLat, maxLon, maxLat }
}

/**
 * The edges worth projecting a point onto, in ASCENDING EDGE ORDER.
 *
 * The order is not a tidiness preference. {@link nearestPointOnGraph} keeps
 * the first of two edges at an equal distance (its comparison is `>=`), so
 * handing it candidates in cell order rather than edge order would change
 * which trail an exactly-ambiguous tap lands on. Cells are read in an order
 * that depends on the query point; edge order does not.
 */
function edgesNear(grid: EdgeGrid, at: LonLat, marginMetres: number): number[] {
  const latMargin = marginMetres / 111_320
  const cosLat = Math.max(0.01, Math.cos((at.lat * Math.PI) / 180))
  const lonMargin = latMargin / cosLat

  const found = new Set<number>()
  const latFrom = Math.floor((at.lat - latMargin) / GRID_DEGREES)
  const latTo = Math.floor((at.lat + latMargin) / GRID_DEGREES)
  const lonFrom = Math.floor((at.lon - lonMargin) / GRID_DEGREES)
  const lonTo = Math.floor((at.lon + lonMargin) / GRID_DEGREES)

  for (let latBucket = latFrom; latBucket <= latTo; latBucket += 1) {
    for (let lonBucket = lonFrom; lonBucket <= lonTo; lonBucket += 1) {
      const cell = grid.cells.get(latBucket * GRID_STRIDE + lonBucket + GRID_STRIDE / 2)
      if (cell === undefined) continue
      for (const edgeIndex of cell) {
        // The box test, which is what makes an over-filed long edge cheap:
        // a diagonal edge spanning ten cells is in all of them and near the
        // point in at most one.
        if (
          at.lon < grid.minLon[edgeIndex] - lonMargin ||
          at.lon > grid.maxLon[edgeIndex] + lonMargin ||
          at.lat < grid.minLat[edgeIndex] - latMargin ||
          at.lat > grid.maxLat[edgeIndex] + latMargin
        )
          continue
        found.add(edgeIndex)
      }
    }
  }

  return Array.from(found).sort((a, b) => a - b)
}

// Equirectangular metres, which is what every distance in this module's
// nearest-point search wants: the comparisons are all local, over a few
// hundred metres at most, and the alternative is a projection library on the
// phone for an answer that does not change.
const EARTH_RADIUS_M = 6_378_137

function localMetres(from: LonLat, to: LonLat): { x: number; y: number } {
  const meanLatitude = ((from.lat + to.lat) / 2) * (Math.PI / 180)
  return {
    x: (to.lon - from.lon) * (Math.PI / 180) * EARTH_RADIUS_M * Math.cos(meanLatitude),
    y: (to.lat - from.lat) * (Math.PI / 180) * EARTH_RADIUS_M,
  }
}

/**
 * Whether this edge carries its own vertices.
 *
 * The one predicate five things read, on `sameTrail`'s reasoning a few
 * hundred lines up: "has the phone got the lines, or only the topology" is
 * asked at five different altitudes and has to be answered the same way each
 * time. {@link nearestPointOnGraph} asks it to decide whether an edge may be
 * snapped to at all, {@link routeGeometry} to decide whether a leg may be
 * drawn, lib/dayHikeWalk.ts's `stepPolyline` to decide whether a walked
 * stretch has a shape, lib/dayHikeTurns.ts to decide whether a turn may be
 * given a side, and {@link sameTread} to decide whether two twins of one
 * tread can be told apart from a fork at all.
 */
export function hasVertices(
  edge: GraphEdge,
): edge is GraphEdge & { geometry: Array<[number, number]> } {
  return edge.geometry !== undefined && edge.geometry.length >= 2
}

/**
 * Whether this index can be snapped against at all.
 *
 * The two artifacts are index-aligned and attached all-or-nothing
 * (lib/trailGraphData.ts refuses a geometry whose edge count disagrees), so
 * in practice one edge answers for the whole graph. Asked of every edge
 * anyway rather than of `edges[0]`, so that a graph half-attached by some
 * future change degrades to "some of it" instead of to whichever edge
 * happens to be first.
 *
 * A caller that gets `false` holds the TOPOLOGY and not the LINES, which is
 * a different thing from a tap being off the network and has to be said
 * differently - see lib/dayHikeDraft.ts's two sentences.
 */
export function canSnapToGraph(index: TrailGraphIndex): boolean {
  return index.graph.edges.some(hasVertices)
}

/**
 * Where on this edge the point lies, as a fraction, plus how far off it was.
 *
 * Walks the edge's own vertices where the artifact carries them, so a tap on
 * the far side of a switchback measures its distance to the TRAIL and not to
 * the chord between two junctions - a chord could refuse a finger that was on
 * the ground the whole time. `fraction` is distance along the polyline over
 * its total, which is the same scale `length_m` prices.
 *
 * The chord remains as the fallback here for a geometry-less edge, and no
 * caller that could act on one still asks: {@link nearestPointOnGraph} skips
 * those edges outright. It is left rather than removed for
 * {@link projectOntoEdges}, whose whole contract is answering "how far off am
 * I" with no refusal in it - though that function has no callers in the app
 * today, lib/dayHikeFollow.ts having replaced its use of it with a loop over
 * the ground actually walked.
 */
function projectOntoEdge(
  index: TrailGraphIndex,
  edgeIndex: number,
  at: LonLat,
): { fraction: number; offMetres: number; point: LonLat } {
  const edge = index.graph.edges[edgeIndex]
  const vertices: Array<[number, number]> = hasVertices(edge)
    ? edge.geometry
    : [index.graph.nodes[edge.from], index.graph.nodes[edge.to]]

  let best: { offMetres: number; point: LonLat; along: number } | null = null
  let walked = 0
  let total = 0

  for (let step = 0; step + 1 < vertices.length; step += 1) {
    const start: LonLat = { lon: vertices[step][0], lat: vertices[step][1] }
    const end: LonLat = { lon: vertices[step + 1][0], lat: vertices[step + 1][1] }
    const span = localMetres(start, end)
    const spanLength = Math.hypot(span.x, span.y)
    const offset = localMetres(start, at)

    let along = 0
    if (spanLength > 0) {
      along = (offset.x * span.x + offset.y * span.y) / (spanLength * spanLength)
      along = Math.min(1, Math.max(0, along))
    }
    const offMetres = Math.hypot(offset.x - span.x * along, offset.y - span.y * along)
    if (best === null || offMetres < best.offMetres) {
      best = {
        offMetres,
        point: {
          lon: start.lon + (end.lon - start.lon) * along,
          lat: start.lat + (end.lat - start.lat) * along,
        },
        along: walked + spanLength * along,
      }
    }
    walked += spanLength
    total += spanLength
  }

  if (best === null || total === 0) {
    const node = index.graph.nodes[edge.from]
    return { fraction: 0, offMetres: Infinity, point: { lon: node[0], lat: node[1] } }
  }
  return { fraction: best.along / total, offMetres: best.offMetres, point: best.point }
}

/**
 * The nearest place on the network to a tap, or null when the tap is not on
 * one.
 *
 * Null is frame `1j`'s refusal, and it is the honest answer rather than a
 * failure: OurHike only builds routes on trails an organization maintains.
 *
 * AN EDGE WITH NO VERTICES IS NOT A CANDIDATE, and that is the whole of
 * #1093. A geometry-less edge offers only the straight chord between its two
 * junctions, and the map beside the finger is drawing the published line -
 * so measuring a tap against the chord asks a hiker to aim at something that
 * is not on their screen.
 *
 * Measured against THE PUBLISHED ARTIFACT, not a re-derivation of one:
 * `trail_graph.json` and `trail_graph_geometry.json` as served by
 * data.ourhike.org on 2026-08-27 (release a6292547) - 31,545 nodes, 40,596
 * edges, median edge 68 m, p90 996 m, longest 58,615 m. Five points along
 * each of 4,000 randomly chosen edges (seed 1093) - 20,000 taps, every one
 * landing exactly on the line the map draws:
 *
 *   against the chords    11.3% refused as off-network, 19.7% placed on a
 *                         DIFFERENT trail than the one tapped
 *   against the vertices  0.0% refused, 5.9% on a different trail
 *
 * The trail leaves the 150 ft chord tolerance somewhere along 8,297 of those
 * edges - 21% - with a p90 worst-case deviation of 462 ft and a worst of
 * 46,461 ft.
 *
 * Two things the figures are not. The 5.9% floor is an UPPER BOUND on real
 * error: "different trail" compares `trail_id` and `name`, so two stewards
 * publishing the same ground as separate lines counts against it, and what
 * remains is the corridor ambiguity {@link MAX_OFF_NETWORK_FEET} already
 * names - #771's 48% of A.T. points within 150 m of a different marked
 * trail. And 887 self-loop edges are excluded from the comparison, because a
 * chord from a node to itself is degenerate and gives the baseline nothing
 * to be compared against; every published edge carries at least two
 * vertices, so the rule below excludes none of them.
 *
 * What the numbers say is that the chord more than triples the rate at which
 * a tap lands on a trail the hiker did not point at, and refuses one tap in
 * nine on top - and that is exactly what {@link MAX_OFF_NETWORK_FEET} is
 * rounded small to prevent, arriving by a route the tolerance cannot govern.
 *
 * This is the rule lib/dayHikeFollow.ts already applies ("the geometry is a
 * requirement, not a nicety") and {@link routeGeometry} already applies to
 * drawing. Snapping was the last place a chord was still accepted, and it is
 * the place a finger meets.
 *
 * Null therefore covers two situations the CALLER must tell apart, which is
 * what {@link canSnapToGraph} is for: a tap genuinely off every maintained
 * line, and a phone that holds the topology and not yet the lines. The first
 * is frame `1j`'s refusal; the second is not the hiker's aim being wrong and
 * must not be reported as though it were.
 */
export function nearestPointOnGraph(
  index: TrailGraphIndex,
  at: LonLat,
  maxOffFeet: number = MAX_OFF_NETWORK_FEET,
): GraphPoint | null {
  let best: GraphPoint | null = null

  for (const edgeIndex of snapCandidates(index, at, maxOffFeet)) {
    const projected = projectOntoEdge(index, edgeIndex, at)
    const offNetworkFeet = projected.offMetres * FEET_PER_METRE
    if (best !== null && offNetworkFeet >= best.offNetworkFeet) continue
    best = {
      edgeIndex,
      fraction: projected.fraction,
      at: projected.point,
      offNetworkFeet,
    }
  }

  if (best === null || best.offNetworkFeet > maxOffFeet) return null
  return best
}

/**
 * The edges a point could possibly snap to, in ascending edge order.
 *
 * Exactly the edges the full scan would have considered and kept, because
 * everything the grid drops is further than `maxOffFeet` and the caller
 * refuses that anyway. The fallback is the full scan, for a graph with no
 * grid - which today means a graph with no geometry, where the vertex rule
 * leaves nothing to consider either way.
 */
function snapCandidates(
  index: TrailGraphIndex,
  at: LonLat,
  maxOffFeet: number,
): number[] {
  if (index.grid !== null) {
    return edgesNear(index.grid, at, maxOffFeet / FEET_PER_METRE)
  }
  const all: number[] = []
  for (let edgeIndex = 0; edgeIndex < index.graph.edges.length; edgeIndex += 1) {
    if (hasVertices(index.graph.edges[edgeIndex])) all.push(edgeIndex)
  }
  return all
}

/**
 * Every distinct TRAIL within reach of a point, nearest first.
 *
 * WHY TRAILS RATHER THAN EDGES. `build_trail_graph.py` splits a line at every
 * crossing, so one trail near a point is typically several edges of it, and a
 * list of edges would ask a hiker "which of these four pieces of the Pine
 * Meadow Trail did you mean" - a question about the artifact rather than about
 * the ground. Grouping on `trail_id` asks the question they can answer, which
 * is which blaze they were following.
 *
 * WHY IT EXISTS. {@link nearestPointOnGraph} keeps one `best` and drops every
 * other candidate inside its loop, so it cannot express "two trails are
 * equally plausible" - it just picks. That is fine for a tap, which is one
 * deliberate aim, and it is #935's whole problem for a drawn line: through
 * Harriman-Bear Mountain 48% of sampled A.T. points have a second marked trail
 * within 150 m (#771), so a stroke sweeping that corridor is repeatedly
 * choosing between two real trails on a margin of metres and saying nothing.
 * The maintainer's answer (2026-08-27) is that the app asks, and this is what
 * it asks with.
 *
 * The best point on each trail is returned - not the trail's nearest edge but
 * the nearest point on it - so a caller that takes one can use it directly.
 */
/**
 * What makes two pieces of tread the SAME ANSWER to "which trail did you
 * mean" - which is not the same question {@link sameTrail} answers.
 *
 * `sameTrail` compares `trail_id` and `name`, and it is right to: it decides
 * where one LEG ends and the next begins, and a leg is a run of one published
 * line. But a publisher routinely splits one trail into many lines with
 * different ids, and asking a hiker to choose between four candidates all
 * labelled "Pine Meadow Trail" is a question about the artifact rather than
 * about the ground. Measured on the published network (data.ourhike.org,
 * 2026-08-27): grouping on `trail_id` made 68.5% of sampled Harriman points
 * ambiguous; grouping on what a hiker can read - the name, the blaze and the
 * organization - is what the figure recorded in features/HIKE_PLANNING.md
 * measures instead.
 *
 * An UNNAMED piece falls back to its own edge, which is the conservative
 * direction: two unnamed trails stay two candidates rather than collapsing
 * into one answer that would be wrong for at least one of them. The cost is a
 * choice a hiker cannot make well, and it is the lesser cost - the app never
 * pretends to know which unnamed line somebody meant.
 */
function askableIdentity(edge: GraphEdge, edgeIndex: number): string {
  if (edge.name === null) return `edge:${edgeIndex}`
  return `${edge.source ?? ''}\u0000${edge.name}\u0000${edge.blaze_color ?? ''}`
}

export function trailsNear(
  index: TrailGraphIndex,
  at: LonLat,
  maxOffMetres: number = DRAWN_SNAP_METRES,
): GraphPoint[] {
  const maxOffFeet = maxOffMetres * FEET_PER_METRE
  const best = new Map<string, GraphPoint>()

  for (const edgeIndex of snapCandidates(index, at, maxOffFeet)) {
    const projected = projectOntoEdge(index, edgeIndex, at)
    const offNetworkFeet = projected.offMetres * FEET_PER_METRE
    if (offNetworkFeet > maxOffFeet) continue
    const key = askableIdentity(index.graph.edges[edgeIndex], edgeIndex)
    const known = best.get(key)
    if (known !== undefined && known.offNetworkFeet <= offNetworkFeet) continue
    best.set(key, {
      edgeIndex,
      fraction: projected.fraction,
      at: projected.point,
      offNetworkFeet,
    })
  }

  return Array.from(best.values()).sort((a, b) => {
    if (a.offNetworkFeet !== b.offNetworkFeet) return a.offNetworkFeet - b.offNetworkFeet
    // A stable order for an exact tie, for the reason NodeHeap gives: input
    // order here is edge numbering, which the pipeline rewrites on every
    // publish.
    return a.edgeIndex - b.edgeIndex
  })
}

/**
 * When two candidate trails are close enough that choosing between them does
 * not change where a hiker walks.
 *
 * DERIVED, NOT PICKED. `pipeline/build_trail_graph.py`'s `ENDPOINT_SNAP_M` is
 * 8.0 m and its own comment states what the number means: "Two vertices closer
 * together than this are the same place." This is that sentence read from the
 * other end - if the pipeline would weld two line-ends this far apart into one
 * node, the app has no business asking a hiker which of two lines this far
 * apart they meant. One home for "the same place", used three times:
 * {@link trailChoice}'s ask filter, and both of {@link sameTread}'s probes.
 *
 * WHY IT MATTERS, MEASURED. Against the published network on 2026-08-27,
 * 4,000 points sampled on real trail vertices inside Harriman-Bear Mountain:
 * 64.3% have more than one marked trail within #935's 25 m, and the median
 * separation between the top two candidates is **0.0 m**. 70% of those pairs
 * are within 1 m of each other. They are trails sharing tread - the A.T. runs
 * concurrently with Ramapo-Dunderberg (red), 1777 East (white) and the Long
 * Path (aqua) through that park, and OPRHP publishes its own line for ground
 * ATC's centerline already covers. Asking "which trail did you mean" there is
 * asking about a label, not about a walk: both answers route the hiker over
 * the identical ground.
 *
 * Filtering on this threshold takes the ask from 64.3% of sampled points to
 * **17.3%** in Harriman and 20.6% across the whole network - measured, not
 * predicted, by running {@link trailChoice} over the same 4,000 points.
 *
 * Two things that figure is NOT. It is not the rate at which a hiker gets
 * asked: these are points sampled exactly on a trail's own vertices, one
 * question per point, and a drawn stroke resolves a run of samples into one
 * stretch before anything is asked - so this is an upper bound on the ask
 * rate, not the ask rate. And it is not a claim about a real drawn line,
 * because nobody has drawn one on this yet, which is what #935 says would
 * settle the tolerance.
 */
export const SAME_TREAD_METRES = 8.0

/**
 * What the app should do about a point on a drawn line: take it, ask about it,
 * or refuse it.
 *
 * #935's decision (maintainer, 2026-08-27) in one function - *"Ask which
 * trail. But only match to trails within 25M."* Both halves, and a third rule
 * that follows from measuring the first two rather than from anybody's
 * preference: **an ask is only worth making when the answer changes where
 * somebody walks.** See {@link SAME_TREAD_METRES} for the figures.
 *
 * `ask` hands back every distinct candidate, nearest first, and the caller
 * puts them in front of the hiker with the blaze colour - which is the thing
 * they will be checking against the paint on the tree, and the only thing that
 * tells two concurrent trails apart on the ground.
 */
export type TrailChoice =
  | { kind: 'none' }
  | { kind: 'one'; point: GraphPoint }
  | { kind: 'ask'; options: GraphPoint[] }

export function trailChoice(
  index: TrailGraphIndex,
  at: LonLat,
  maxOffMetres: number = DRAWN_SNAP_METRES,
): TrailChoice {
  const near = trailsNear(index, at, maxOffMetres)
  if (near.length === 0) return { kind: 'none' }

  const nearest = near[0]
  const elsewhere = near.filter(
    (candidate) =>
      Math.hypot(
        localMetres(nearest.at, candidate.at).x,
        localMetres(nearest.at, candidate.at).y,
      ) > SAME_TREAD_METRES,
  )
  if (elsewhere.length === 0) return { kind: 'one', point: nearest }
  return { kind: 'ask', options: [nearest, ...elsewhere] }
}

/**
 * How far a point is from every piece of a walk, one answer per POSITION in
 * the edge list rather than per edge.
 *
 * The distinction is the whole reason this returns a list instead of a
 * nearest: a route walks some edges twice - every out-and-back does, and
 * `closeTheLoop` can - and the two passes are different places in the day,
 * reached at different miles, with different turns still to come. Handing
 * back only the nearest projection would make a hiker on the way home read as
 * being on the way out.
 *
 * No threshold and no refusal here, unlike {@link nearestPointOnGraph}: this
 * is asked "how far off am I", and "very" is a real answer that the caller
 * needs the number for (lib/dayHikeFollow.ts prints it).
 */
export function projectOntoEdges(
  index: TrailGraphIndex,
  at: LonLat,
  edgeIndices: readonly number[],
): EdgeProjection[] {
  return edgeIndices.map((edgeIndex, position) => {
    const projected = projectOntoEdge(index, edgeIndex, at)
    return {
      at: position,
      edgeIndex,
      fraction: projected.fraction,
      point: projected.point,
      offFeet: projected.offMetres * FEET_PER_METRE,
    }
  })
}

/** Where one point falls against one position in an edge list. */
export interface EdgeProjection {
  /** Position in the list handed to {@link projectOntoEdges} - not the edge
   *  index, for the reason that function's own note gives. */
  at: number
  edgeIndex: number
  /** Fraction along the edge, measured from its `from` end. */
  fraction: number
  /** The point after being pulled onto the line. */
  point: LonLat
  /** How far the point was from the line, in feet. */
  offFeet: number
}

interface Reached {
  distance: number
  viaEdge: number
  fromNode: number
}

/**
 * A binary min-heap over (distance, node), ties broken by the lower node id.
 *
 * WHY THE TIE-BREAK IS PART OF THE STRUCTURE. The scan this replaced took the
 * first node in Map insertion order at the lowest distance, so which of two
 * equal-length routes came back depended on the order nodes happened to be
 * discovered - which depends on adjacency order, which depends on edge
 * numbering, which `build_trail_graph.py` renumbers wholesale between
 * publishes. That is not a stable answer, it only looked like one. Ordering
 * on the node id instead is stable for as long as the artifact is, which is
 * the most any tie-break here can honestly promise.
 *
 * Lazy deletion rather than a decrease-key: a node whose distance improves is
 * pushed again and the stale entry is skipped when it surfaces, which is
 * cheaper than maintaining positions and is why `settled` is consulted on pop
 * rather than only on relax.
 */
class NodeHeap {
  private nodes: number[] = []
  private distances: number[] = []

  get size(): number {
    return this.nodes.length
  }

  private before(a: number, b: number): boolean {
    if (this.distances[a] !== this.distances[b])
      return this.distances[a] < this.distances[b]
    return this.nodes[a] < this.nodes[b]
  }

  private swap(a: number, b: number): void {
    const node = this.nodes[a]
    const distance = this.distances[a]
    this.nodes[a] = this.nodes[b]
    this.distances[a] = this.distances[b]
    this.nodes[b] = node
    this.distances[b] = distance
  }

  push(node: number, distance: number): void {
    this.nodes.push(node)
    this.distances.push(distance)
    let at = this.nodes.length - 1
    while (at > 0) {
      const parent = (at - 1) >> 1
      if (!this.before(at, parent)) break
      this.swap(at, parent)
      at = parent
    }
  }

  pop(): { node: number; distance: number } | null {
    if (this.nodes.length === 0) return null
    const node = this.nodes[0]
    const distance = this.distances[0]
    const lastNode = this.nodes.pop() as number
    const lastDistance = this.distances.pop() as number
    if (this.nodes.length > 0) {
      this.nodes[0] = lastNode
      this.distances[0] = lastDistance
      let at = 0
      for (;;) {
        const left = at * 2 + 1
        const right = left + 1
        let smallest = at
        if (left < this.nodes.length && this.before(left, smallest)) smallest = left
        if (right < this.nodes.length && this.before(right, smallest)) smallest = right
        if (smallest === at) break
        this.swap(at, smallest)
        at = smallest
      }
    }
    return { node, distance }
  }
}

/**
 * Dijkstra from two seeded nodes - the ends of the edge the start point sits
 * on, each already `fraction` of that edge away.
 *
 * WAS a heap-free scan over the whole frontier, on #757's budget: "at ~3,000
 * edges the constant factor of a heap costs more to maintain than it saves."
 * The published graph is 40,596 edges (data.ourhike.org, 2026-08-27) and the
 * scan is O(frontier) per pop, so #1020 is where that budget was revisited.
 *
 * Worth being straight about the size of the win, because the issue's own
 * framing expected it to be the headline and it is not: a heap is worth
 * roughly 15% of the search, and the search was never the expensive half of
 * answering a tap. {@link EdgeGrid} is. Both landed together and the grid is
 * the one a hiker would have felt.
 */
function shortestPath(
  index: TrailGraphIndex,
  seeds: Array<{ node: number; distance: number }>,
  targets: Map<number, number>,
): { node: number; total: number; reached: Map<number, Reached> } | null {
  const reached = new Map<number, Reached>()
  const settled = new Set<number>()
  const frontier = new NodeHeap()

  for (const seed of seeds) {
    const existing = reached.get(seed.node)
    if (existing === undefined || seed.distance < existing.distance) {
      reached.set(seed.node, { distance: seed.distance, viaEdge: -1, fromNode: -1 })
      frontier.push(seed.node, seed.distance)
    }
  }

  let bestTarget: { node: number; total: number } | null = null

  while (frontier.size > 0) {
    const top = frontier.pop()
    if (top === null) break
    const current = top.node
    const currentDistance = top.distance
    // A stale entry: this node was reached again more cheaply after this one
    // was pushed, or has already been settled from a better pop.
    if (settled.has(current)) continue
    const known = reached.get(current)
    if (known !== undefined && known.distance < currentDistance) continue
    settled.add(current)

    const tail = targets.get(current)
    if (tail !== undefined) {
      const total = currentDistance + tail
      if (bestTarget === null || total < bestTarget.total)
        bestTarget = { node: current, total }
    }

    // Nothing further from here can beat a finished target.
    if (bestTarget !== null && currentDistance >= bestTarget.total) break

    for (const step of index.adjacency[current] ?? []) {
      if (settled.has(step.to)) continue
      const next = currentDistance + index.graph.edges[step.edgeIndex].length_m
      const reachedTo = reached.get(step.to)
      if (reachedTo !== undefined && reachedTo.distance <= next) continue
      reached.set(step.to, { distance: next, viaEdge: step.edgeIndex, fromNode: current })
      frontier.push(step.to, next)
    }
  }

  if (bestTarget === null) return null
  return { ...bestTarget, reached }
}

function walkBack(reached: Map<number, Reached>, node: number): number[] {
  const edges: number[] = []
  let current = node
  for (;;) {
    const step = reached.get(current)
    if (step === undefined || step.viaEdge === -1) break
    edges.push(step.viaEdge)
    current = step.fromNode
  }
  return edges.reverse()
}

/**
 * Consecutive edges on one trail collapsed into a leg.
 *
 * A leg is what frame `1l` prints and what frame `1j` counts, and it is a run
 * of the same TRAIL rather than of the same organization: walking the A.T. and
 * then the Long Path is two legs even where one steward maintains both.
 *
 * The plain merge, with no concurrency handling: it neither re-picks edges
 * ({@link holdDesignation}) nor carries `concurrent_sources` - the routed
 * paths get both via {@link routeBetween}. Callers handing this a raw edge
 * list get exactly the runs that list already has.
 */
export function legsFromEdges(graph: TrailGraph, edgeIndices: number[]): RouteLeg[] {
  const legs: RouteLeg[] = []
  for (const edgeIndex of edgeIndices) {
    const edge = graph.edges[edgeIndex]
    const last = legs[legs.length - 1]
    if (last !== undefined && sameTrail(last, edge)) {
      last.miles += metresToMiles(edge.length_m)
      continue
    }
    legs.push({
      name: edge.name,
      source: edge.source,
      blaze_color: edge.blaze_color,
      trail_id: edge.trail_id,
      miles: metresToMiles(edge.length_m),
    })
  }
  return legs
}

function tallyBySource(legs: RouteLeg[]): Array<{ source: string | null; legs: number }> {
  const counts = new Map<string | null, number>()
  const bump = (source: string | null) =>
    counts.set(source, (counts.get(source) ?? 0) + 1)
  for (const leg of legs) {
    bump(leg.source)
    // A concurrent org's ground is in this leg even though the leg wears the
    // other name (#1115) - see RouteLeg.concurrent_sources. Counted once per
    // org per leg, same as the org whose name it wears.
    for (const source of leg.concurrent_sources ?? []) {
      if (source !== leg.source) bump(source)
    }
  }
  return [...counts].map(([source, count]) => ({ source, legs: count }))
}

/**
 * Fold one position's concurrent organizations into the leg being built,
 * keeping the field absent - not `[]` - while there is nothing to say.
 */
function addConcurrents(leg: RouteLeg, sources: string[]): void {
  for (const source of sources) {
    if (source === leg.source) continue
    if (leg.concurrent_sources === undefined) leg.concurrent_sources = []
    if (!leg.concurrent_sources.includes(source)) leg.concurrent_sources.push(source)
  }
}

/**
 * legsFromEdges' merge, pricing each edge at the metres actually walked on it
 * rather than its whole length (#1002): a walk enters its first edge and
 * leaves its last mid-way, and a leg billing those edges whole overstates the
 * ends - 0.5 mi of trail wearing a 1.0 mi leg, side by side on one card.
 */
function legsFromWalk(
  graph: TrailGraph,
  edgeIndices: number[],
  walkedMetres: number[],
  concurrents: string[][],
): RouteLeg[] {
  const legs: RouteLeg[] = []
  edgeIndices.forEach((edgeIndex, at) => {
    const edge = graph.edges[edgeIndex]
    const last = legs[legs.length - 1]
    if (last !== undefined && sameTrail(last, edge)) {
      last.miles += metresToMiles(walkedMetres[at])
      addConcurrents(last, concurrents[at] ?? [])
      return
    }
    const leg: RouteLeg = {
      name: edge.name,
      source: edge.source,
      blaze_color: edge.blaze_color,
      trail_id: edge.trail_id,
      miles: metresToMiles(walkedMetres[at]),
    }
    addConcurrents(leg, concurrents[at] ?? [])
    legs.push(leg)
  })
  return legs
}

function assemble(
  graph: TrailGraph,
  edgeIndices: number[],
  metres: number,
  walkedMetres: number[],
  entered: number[],
  section: RouteSection,
  concurrents: string[][],
): GraphRoute {
  const legs = legsFromWalk(graph, edgeIndices, walkedMetres, concurrents)
  return {
    legs,
    miles: metresToMiles(metres),
    edgeIndices,
    // One leg, which is what routeBetween builds. routeThrough concatenates
    // these across its taps and never merges them.
    sections: [section],
    legsBySource: tallyBySource(legs),
    // Priced here rather than by the caller, off the SAME walkedMetres the
    // legs are priced from - a second opinion about how much of an edge was
    // walked is the drift #1002 was about.
    climb: routeClimb(graph, edgeIndices, walkedMetres, entered),
  }
}

/**
 * The shortest walk between two points on the network, or null when the graph
 * holds no path between them.
 *
 * Null happens for real and is not a bug: the published network is clipped to a
 * ring, two parks can be genuinely unconnected by maintained trail, and
 * build_trail_graph.py's endpoint tolerance deliberately rounds toward leaving
 * a junction unmade rather than inventing one. The caller says so rather than
 * drawing a straight line, which would be the app claiming ground it has no
 * evidence for.
 */
export function routeBetween(
  index: TrailGraphIndex,
  from: GraphPoint,
  to: GraphPoint,
): GraphRoute | null {
  const graph = index.graph

  if (from.edgeIndex === to.edgeIndex) {
    // Both taps on one edge: the walk is the piece between them and there is
    // nothing to search.
    const edge = graph.edges[from.edgeIndex]
    const metres = Math.abs(to.fraction - from.fraction) * edge.length_m
    return assemble(
      graph,
      [from.edgeIndex],
      metres,
      [metres],
      enteredNodes(graph, [from.edgeIndex], from, to),
      { edgeIndices: [from.edgeIndex], from, to },
      [concurrentSourcesOf(index, from.edgeIndex)],
    )
  }

  const fromEdge = graph.edges[from.edgeIndex]
  const toEdge = graph.edges[to.edgeIndex]

  const seeds = [
    { node: fromEdge.from, distance: from.fraction * fromEdge.length_m },
    { node: fromEdge.to, distance: (1 - from.fraction) * fromEdge.length_m },
  ]
  const targets = new Map<number, number>([
    [toEdge.from, to.fraction * toEdge.length_m],
    [toEdge.to, (1 - to.fraction) * toEdge.length_m],
  ])

  const found = shortestPath(index, seeds, targets)
  if (found === null) return null

  // The partial first and last edges bookend the whole edges between them.
  const middle = walkBack(found.reached, found.node)
  const edgeIndices = holdDesignation(index, [from.edgeIndex, ...middle, to.edgeIndex])
  // Re-priced from the swapped list rather than carrying `found.total`:
  // holdDesignation may have traded an edge for its same-tread twin, whose
  // digitisation differs by tracing noise, and the walk's total must be the
  // sum of the edges the walk now actually names. Pre-swap the two are the
  // same number - the seeds and targets are these ends' own partials.
  const walkedMetres = walkedMetresPerEdge(graph, edgeIndices, from, to)
  return assemble(
    graph,
    edgeIndices,
    walkedMetres.reduce((total, part) => total + part, 0),
    walkedMetres,
    enteredNodes(graph, edgeIndices, from, to),
    { edgeIndices, from, to },
    edgeIndices.map((edgeIndex) => concurrentSourcesOf(index, edgeIndex)),
  )
}

/**
 * A walk through every tapped point in order.
 *
 * Returns null if ANY leg of it cannot be routed, rather than a partial route
 * with a silent hole in it. A hiker handed four legs of a five-leg walk has
 * been told something false about the fifth.
 */
export function routeThrough(
  index: TrailGraphIndex,
  points: GraphPoint[],
): GraphRoute | null {
  if (points.length < 2) return null

  const edgeIndices: number[] = []
  const sections: RouteSection[] = []
  const legs: RouteLeg[] = []
  const sectionClimbs: Array<RouteClimb | null> = []
  let metres = 0
  for (let step = 0; step + 1 < points.length; step += 1) {
    const section = routeBetween(index, points[step], points[step + 1])
    if (section === null) return null
    metres += section.miles * METRES_PER_MILE
    sectionClimbs.push(section.climb)
    // Kept whole, never deduplicated against its neighbour: this is the walk
    // as walked, and it is what the drawing follows (#1040).
    sections.push(...section.sections)
    for (const edgeIndex of section.edgeIndices) {
      // The join between two sections lands on the same edge twice; drawing it
      // once is right and counting it once already happened above.
      if (edgeIndices[edgeIndices.length - 1] === edgeIndex) continue
      edgeIndices.push(edgeIndex)
    }
    // Each section's own priced legs, merged across the join. The shared edge
    // was deduplicated above for DRAWING, but both sections' walked spans of
    // it are real distance, so their legs ADD - the out-and-back half of
    // #1002, where a leg priced off the deduplicated list undercounted every
    // re-walked stretch.
    for (const leg of section.legs) {
      const last = legs[legs.length - 1]
      if (last !== undefined && sameTrail(last, leg)) {
        last.miles += leg.miles
        addConcurrents(last, leg.concurrent_sources ?? [])
        continue
      }
      const copied: RouteLeg = { ...leg }
      // A copy of the array too: addConcurrents mutates it when a later
      // section merges in, and the section's own leg must not change under it.
      if (leg.concurrent_sources !== undefined) {
        copied.concurrent_sources = [...leg.concurrent_sources]
      }
      legs.push(copied)
    }
  }
  return {
    legs,
    miles: metresToMiles(metres),
    edgeIndices,
    sections,
    legsBySource: tallyBySource(legs),
    // Sections ADD, exactly as their legs do above and for the same reason:
    // the edge shared across a join was deduplicated for DRAWING, but both
    // sections really walked their span of it and really climbed it. One
    // unpriceable section makes the whole walk unpriceable - the same refusal
    // routeClimb applies per edge, one level up.
    climb: climbAcross(sectionClimbs),
  }
}

/** Sum of every section's climb, or null if any one of them had none. */
function climbAcross(climbs: Array<RouteClimb | null>): RouteClimb | null {
  let gainFt = 0
  let lossFt = 0
  for (const climb of climbs) {
    if (climb === null) return null
    gainFt += climb.gainFt
    lossFt += climb.lossFt
  }
  return { gainFt, lossFt }
}

/**
 * Which node each edge is entered FROM, walking the route in order - the
 * orientation every consumer of an edge list needs, whether it is drawing the
 * line (routeGeometry) or accumulating miles to a junction (the finished-hike
 * card's bail-outs, #980).
 *
 * CHAINED BY NODE ID, NOT BY COORDINATE. Two edges meeting at an
 * endpoint-welded junction (pipeline/build_trail_graph.py) share a NODE while
 * their published coordinates still disagree by metres - the weld unifies
 * identity and edits nobody's line. Comparing coordinates would break the
 * chain at exactly those junctions; the node ids cannot. The single-edge
 * direction falls back to the tapped fractions, the only orientation evidence
 * one edge carries.
 */
export function enteredNodes(
  graph: TrailGraph,
  edgeIndices: number[],
  start?: GraphPoint,
  end?: GraphPoint,
): number[] {
  const entered: number[] = []
  if (edgeIndices.length === 1) {
    const only = graph.edges[edgeIndices[0]]
    const forward =
      start === undefined || end === undefined || start.fraction <= end.fraction
    entered.push(forward ? only.from : only.to)
  } else {
    for (let step = 0; step < edgeIndices.length; step += 1) {
      const edge = graph.edges[edgeIndices[step]]
      if (step === 0) {
        const next = graph.edges[edgeIndices[1]]
        const fromShared = edge.from === next.from || edge.from === next.to
        entered.push(fromShared ? edge.to : edge.from)
      } else {
        const previous = graph.edges[edgeIndices[step - 1]]
        const cameFrom =
          edge.from === previous.from || edge.from === previous.to ? edge.from : edge.to
        entered.push(cameFrom)
      }
    }
  }
  return entered
}

/**
 * How many metres of each edge one tapped pair actually walks: the first and
 * last scaled by the tap fractions, everything between whole. The arithmetic
 * #1002 exists about - shared by leg pricing (routeBetween) and the
 * finished-hike card's bail-out miles (lib/dayHikeCard.ts), so the two
 * cannot drift apart.
 */
export function walkedMetresPerEdge(
  graph: TrailGraph,
  edgeIndices: number[],
  from: GraphPoint,
  to: GraphPoint,
): number[] {
  const entered = enteredNodes(graph, edgeIndices, from, to)
  return edgeIndices.map((edgeIndex, at) => {
    const edge = graph.edges[edgeIndex]
    if (edgeIndices.length === 1) {
      return Math.abs(to.fraction - from.fraction) * edge.length_m
    }
    const forward = entered[at] === edge.from
    if (at === 0) return (forward ? 1 - from.fraction : from.fraction) * edge.length_m
    if (at === edgeIndices.length - 1) {
      return (forward ? to.fraction : 1 - to.fraction) * edge.length_m
    }
    return edge.length_m
  })
}

/** Confirmed ascent and descent over a walk, both positive, in feet. */
export interface RouteClimb {
  gainFt: number
  lossFt: number
}

/**
 * The climb over one walk, or null when any edge of it was never measured.
 *
 * NULL RATHER THAN A TOTAL WITH A HOLE IN IT. The same rule
 * {@link routeThrough} applies to an unroutable leg, for the same reason: a
 * hiker handed "+800 ft" for a walk whose third edge has no elevation has been
 * told something false, and the error is silently in the optimistic direction.
 * "We cannot price this climb" is a sentence the card can print; a wrong number
 * is not.
 *
 * PARTIAL EDGES ARE PRO-RATED BY DISTANCE, WHICH IS AN APPROXIMATION AND IS
 * SAID SO HERE. `walkedMetres` scales the first and last edges by where the
 * hiker tapped, and this scales their climb by the same share - so it assumes
 * an edge's gradient is uniform along it, which no trail's is.
 *
 * What bounds the error: only the two END edges of a walk are ever partial -
 * every edge between them is walked whole - so the worst case is a fraction of
 * two edges' own relief, not of the route's. Edges here are short, because
 * build_trail_graph.py splits a line at every crossing. The alternative was
 * counting a partial edge whole, which over-states, or refusing to price any
 * walk that does not start and end on a junction, which is nearly all of them.
 *
 * It is deliberately the SAME share `walkedMetresPerEdge` already computes,
 * rather than a second opinion about how much of an edge was walked - the
 * drift #1002 was about.
 *
 * DIRECTION, and the approximation in handling it (#1034). An edge's
 * `[gain, loss]` is measured along its STORED direction, which
 * build_trail_graph.py inherits from whichever way the source line was
 * digitised - unrelated to which way is uphill, and unrelated to which way
 * anybody walks. `buildGraphIndex` makes the graph undirected, so roughly
 * half of all edges are walked against that direction, and this used to add
 * `climb[0]` to gain regardless. A downhill walk reported the ascent of the
 * climb, and an out-and-back reported gain with no loss at all - a walk
 * ending where it started, finishing thousands of feet above its own
 * trailhead.
 *
 * Swapping the pair is the closest available answer and NOT the exact one.
 * Confirmed ascent is walked sample by sample through a dead band
 * (`elevationGain.ts`), and reversing that run is not the same operation as
 * exchanging its two totals: a run whose small rises were absorbed by the
 * band in one direction can have different ones absorbed in the other. Two
 * scalars per edge cannot carry that, so this is an approximation, and
 * closing it properly means `export_network_elevation.py` publishing both
 * directions rather than the client inferring one.
 *
 * What is exact either way, and what the test asserts: a walk that returns
 * to where it started has gain equal to loss. That is arithmetic about the
 * ground rather than about the dead band, and it is the invariant the old
 * behaviour broke visibly.
 */
export function routeClimb(
  graph: TrailGraph,
  edgeIndices: number[],
  walkedMetres: number[],
  entered: number[],
): RouteClimb | null {
  if (edgeIndices.length === 0) return null
  let gainFt = 0
  let lossFt = 0
  for (let at = 0; at < edgeIndices.length; at += 1) {
    const edge = graph.edges[edgeIndices[at]]
    if (edge === undefined) return null
    const climb = edge.climb
    // undefined (not fetched) and null (fetched, unmeasured) both stop here.
    if (climb === undefined || climb === null) return null
    const walked = walkedMetres[at]
    // A zero-length edge contributes nothing rather than dividing by zero.
    const share =
      edge.length_m > 0 && walked !== undefined
        ? Math.min(Math.max(walked / edge.length_m, 0), 1)
        : 0
    // Walked against the edge's stored direction, this edge's ascent is its
    // descent (#1034). `entered` is the same orientation walkedMetresPerEdge
    // uses to decide which end of a partial edge was covered, so the two
    // cannot disagree about which way the hiker went.
    const forward = entered[at] === undefined || entered[at] === edge.from
    gainFt += (forward ? climb[0] : climb[1]) * share
    lossFt += (forward ? climb[1] : climb[0]) * share
  }
  return { gainFt, lossFt }
}

/**
 * The drawn shape of a route: one coordinate line per edge, oriented in
 * walking order, with the partial first and last edges trimmed to where the
 * hiker actually tapped.
 *
 * Null when any edge lacks geometry, rather than a straight chord between its
 * junctions - across a switchback a chord is a picture of a trail that does
 * not exist, and this surface exists to be believed.
 *
 * Orientation comes from {@link enteredNodes}, one line per edge rather than
 * one concatenated line for the same welded-junction reason it states: at a
 * welded junction the small published gap stays visible, which is true.
 */
export function routeGeometry(
  graph: TrailGraph,
  edgeIndices: number[],
  start?: GraphPoint,
  end?: GraphPoint,
): Array<Array<[number, number]>> | null {
  if (edgeIndices.length === 0) return null
  for (const edgeIndex of edgeIndices) {
    const edge = graph.edges[edgeIndex]
    if (edge === undefined || !hasVertices(edge)) return null
  }

  // Which node each edge is entered FROM, chained by shared node ids.
  const entered = enteredNodes(graph, edgeIndices, start, end)

  const lines: Array<Array<[number, number]>> = []
  for (let step = 0; step < edgeIndices.length; step += 1) {
    const edge = graph.edges[edgeIndices[step]]
    const geometry = edge.geometry as Array<[number, number]>
    const forward = entered[step] === edge.from
    let coords = forward ? geometry : [...geometry].reverse()

    // Trim the partial edges to the tapped fractions. Fractions are measured
    // from the edge's `from` end, so a reversed traversal flips them.
    const isFirst = step === 0
    const isLast = step === edgeIndices.length - 1
    let fromFraction = 0
    let toFraction = 1
    if (isFirst && start !== undefined && start.edgeIndex === edgeIndices[step]) {
      fromFraction = forward ? start.fraction : 1 - start.fraction
    }
    if (isLast && end !== undefined && end.edgeIndex === edgeIndices[step]) {
      toFraction = forward ? end.fraction : 1 - end.fraction
    }
    if (isFirst && isLast && fromFraction > toFraction) {
      ;[fromFraction, toFraction] = [toFraction, fromFraction]
    }
    if (fromFraction > 0 || toFraction < 1) {
      coords = cutPolyline(coords, fromFraction, toFraction)
    }
    if (coords.length >= 2) lines.push(coords)
  }
  return lines.length > 0 ? lines : null
}

/**
 * The whole walk's drawn shape, leg by leg.
 *
 * WHY NOT `routeGeometry(graph, route.edgeIndices, first, last)`, which is
 * what App.tsx did until #1040. That list is deduplicated across leg joins,
 * so an out-and-back over one edge collapses to `[edge]` and the two tapped
 * fractions handed in are the FIRST and LAST tap - which for a walk returning
 * to where it started are the same point. `routeGeometry` then trims the edge
 * to a zero-length span and returns null, and the map draws nothing at all
 * under a bar reading "1 leg · 0.6 mi · ≈12m walking". Stopping partway back
 * drew the span between the outer taps and silently omitted the ground walked
 * twice. Both measured on a single 836 m edge.
 *
 * Drawing leg by leg is the fix and also the honest picture: a leg re-walked
 * is drawn again over itself, which is what happened on the ground.
 *
 * Null on the same terms `routeGeometry` uses - if ANY leg cannot be drawn,
 * the whole thing refuses rather than handing back a walk with a hole in it.
 * A hiker shown four legs of a five-leg walk has been told something false
 * about the fifth.
 */
export function routeLines(
  graph: TrailGraph,
  route: GraphRoute,
): Array<Array<[number, number]>> | null {
  const lines: Array<Array<[number, number]>> = []
  for (const section of route.sections) {
    const drawn = routeGeometry(graph, section.edgeIndices, section.from, section.to)
    if (drawn === null) return null
    lines.push(...drawn)
  }
  return lines.length > 0 ? lines : null
}

/**
 * The piece of `coords` between two fractions of its polyline length.
 *
 * Exported since #1044: lib/dayHikeWalk.ts needs the same cut to build the
 * stretch of an edge one traversal actually covers, and a second
 * implementation of it would be a second opinion about which ground a hiker
 * walked.
 */
export function cutPolyline(
  coords: Array<[number, number]>,
  fromFraction: number,
  toFraction: number,
): Array<[number, number]> {
  const lengths: number[] = []
  let total = 0
  for (let step = 0; step + 1 < coords.length; step += 1) {
    const span = localMetres(
      { lon: coords[step][0], lat: coords[step][1] },
      { lon: coords[step + 1][0], lat: coords[step + 1][1] },
    )
    const length = Math.hypot(span.x, span.y)
    lengths.push(length)
    total += length
  }
  if (total === 0) return coords

  const startAt = Math.max(0, Math.min(1, fromFraction)) * total
  const endAt = Math.max(0, Math.min(1, toFraction)) * total
  if (endAt <= startAt) return []

  const out: Array<[number, number]> = []
  let walked = 0
  for (let step = 0; step < lengths.length; step += 1) {
    const segmentStart = walked
    const segmentEnd = walked + lengths[step]
    const a = coords[step]
    const b = coords[step + 1]
    const pointAt = (distance: number): [number, number] => {
      const t = lengths[step] === 0 ? 0 : (distance - segmentStart) / lengths[step]
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    }
    // The segment overlaps [startAt, endAt] when it ends past the start and
    // begins before the end; emit the clipped piece's vertices exactly once.
    if (segmentEnd > startAt && segmentStart < endAt) {
      if (out.length === 0) out.push(pointAt(Math.max(startAt, segmentStart)))
      if (segmentEnd <= endAt) {
        out.push(b)
      } else {
        out.push(pointAt(endAt))
        break
      }
    }
    walked = segmentEnd
  }
  return out
}

/**
 * Frame `1j`'s "Close the loop": the walk back from the last tap to the first.
 *
 * A router query rather than a button's business logic, and it is here because
 * most Harriman day hikes are loops - frame `1l` badges one `LOOP`. Null when
 * there is no way back that is not the way out, which the caller says plainly.
 */
export function closeTheLoop(
  index: TrailGraphIndex,
  points: GraphPoint[],
): GraphRoute | null {
  if (points.length < 2) return null
  return routeThrough(index, [...points, points[0]])
}
