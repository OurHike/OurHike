// Routing a day hike over the junction graph, on the phone, with no backend
// (#975, features/HIKE_PLANNING.md "The day hike on a network",
// pipeline/build_trail_graph.py).
//
// #757 already closed the "routing runs on the phone" question for the A.T. -
// a shortest path over ~3,000 edges, no backend, no network. This is that
// precedent applied to a park, where the thing being searched is a real graph
// rather than one line's mile axis.
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
}

export interface GraphRoute {
  legs: RouteLeg[]
  miles: number
  /** Edge indices in walking order, for drawing the highlight. */
  edgeIndices: number[]
  /** Legs per organization, which frame `1j` tallies while the hiker builds. */
  legsBySource: Array<{ source: string | null; legs: number }>
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

const FEET_PER_METRE = 3.280839895
const METRES_PER_MILE = 1609.344

/** Metres to miles. The one conversion in this module, on purpose. */
export function metresToMiles(metres: number): number {
  return metres / METRES_PER_MILE
}

interface Adjacency {
  edgeIndex: number
  to: number
}

export interface TrailGraphIndex {
  graph: TrailGraph
  adjacency: Adjacency[][]
}

/** Adjacency lists, built once per loaded artifact. */
export function buildGraphIndex(graph: TrailGraph): TrailGraphIndex {
  const adjacency: Adjacency[][] = graph.nodes.map(() => [])
  graph.edges.forEach((edge, edgeIndex) => {
    if (!adjacency[edge.from] || !adjacency[edge.to]) return
    adjacency[edge.from].push({ edgeIndex, to: edge.to })
    adjacency[edge.to].push({ edgeIndex, to: edge.from })
  })
  return { graph, adjacency }
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
 * Where on this edge the point lies, as a fraction, plus how far off it was.
 *
 * Walks the edge's own vertices where the artifact carries them, so a tap on
 * the far side of a switchback measures its distance to the TRAIL and not to
 * the chord between two junctions - a chord could refuse a finger that was on
 * the ground the whole time. `fraction` is distance along the polyline over
 * its total, which is the same scale `length_m` prices.
 *
 * The chord remains as the fallback for a geometry-less edge (an artifact
 * published before geometry existed), stated rather than hidden.
 */
function projectOntoEdge(
  index: TrailGraphIndex,
  edgeIndex: number,
  at: LonLat,
): { fraction: number; offMetres: number; point: LonLat } {
  const edge = index.graph.edges[edgeIndex]
  const vertices: Array<[number, number]> =
    edge.geometry !== undefined && edge.geometry.length >= 2
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
 */
export function nearestPointOnGraph(
  index: TrailGraphIndex,
  at: LonLat,
  maxOffFeet: number = MAX_OFF_NETWORK_FEET,
): GraphPoint | null {
  let best: GraphPoint | null = null

  for (let edgeIndex = 0; edgeIndex < index.graph.edges.length; edgeIndex += 1) {
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

interface Reached {
  distance: number
  viaEdge: number
  fromNode: number
}

/**
 * Dijkstra from two seeded nodes - the ends of the edge the start point sits
 * on, each already `fraction` of that edge away.
 *
 * A plain binary-heap-free scan is used because #757's measurement is the
 * budget this module is written against: at ~3,000 edges the constant factor
 * of a heap costs more to maintain than it saves. pipeline/build_trail_graph.py
 * reports the ring's real edge count, and if that lands well past 3,000 this
 * is the function to revisit first.
 */
function shortestPath(
  index: TrailGraphIndex,
  seeds: Array<{ node: number; distance: number }>,
  targets: Map<number, number>,
): { node: number; total: number; reached: Map<number, Reached> } | null {
  const reached = new Map<number, Reached>()
  const settled = new Set<number>()
  const frontier = new Map<number, number>()

  for (const seed of seeds) {
    const existing = frontier.get(seed.node)
    if (existing === undefined || seed.distance < existing) {
      frontier.set(seed.node, seed.distance)
      reached.set(seed.node, { distance: seed.distance, viaEdge: -1, fromNode: -1 })
    }
  }

  let bestTarget: { node: number; total: number } | null = null

  while (frontier.size > 0) {
    let current = -1
    let currentDistance = Infinity
    for (const [node, distance] of frontier) {
      if (distance < currentDistance) {
        current = node
        currentDistance = distance
      }
    }
    if (current === -1) break
    frontier.delete(current)
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
      const known = reached.get(step.to)
      if (known !== undefined && known.distance <= next) continue
      reached.set(step.to, { distance: next, viaEdge: step.edgeIndex, fromNode: current })
      frontier.set(step.to, next)
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
 */
export function legsFromEdges(graph: TrailGraph, edgeIndices: number[]): RouteLeg[] {
  const legs: RouteLeg[] = []
  for (const edgeIndex of edgeIndices) {
    const edge = graph.edges[edgeIndex]
    const last = legs[legs.length - 1]
    if (
      last !== undefined &&
      last.trail_id === edge.trail_id &&
      last.name === edge.name
    ) {
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
  for (const leg of legs) counts.set(leg.source, (counts.get(leg.source) ?? 0) + 1)
  return [...counts].map(([source, count]) => ({ source, legs: count }))
}

function assemble(graph: TrailGraph, edgeIndices: number[], metres: number): GraphRoute {
  const legs = legsFromEdges(graph, edgeIndices)
  return {
    legs,
    miles: metresToMiles(metres),
    edgeIndices,
    legsBySource: tallyBySource(legs),
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
    return assemble(graph, [from.edgeIndex], metres)
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
  const edgeIndices = [from.edgeIndex, ...middle, to.edgeIndex]
  return assemble(graph, edgeIndices, found.total)
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
  let metres = 0
  for (let step = 0; step + 1 < points.length; step += 1) {
    const section = routeBetween(index, points[step], points[step + 1])
    if (section === null) return null
    metres += section.miles * METRES_PER_MILE
    for (const edgeIndex of section.edgeIndices) {
      // The join between two sections lands on the same edge twice; drawing it
      // once is right and counting it once already happened above.
      if (edgeIndices[edgeIndices.length - 1] === edgeIndex) continue
      edgeIndices.push(edgeIndex)
    }
  }
  return assemble(index.graph, edgeIndices, metres)
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
    if (edge === undefined || edge.geometry === undefined || edge.geometry.length < 2) {
      return null
    }
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

/** The piece of `coords` between two fractions of its polyline length. */
function cutPolyline(
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
