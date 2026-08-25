// Loading the junction graph (#975, pipeline/build_trail_graph.py).
//
// lib/nearbyTrailData.ts fetches the network's LINES for the map to draw. This
// fetches their TOPOLOGY for lib/trailGraph.ts to route over. Two artifacts
// derived from one, and the second is useless without the first, which is why
// they are read the same way and fail the same way.
//
// PARSED, NOT AN OBJECT URL, AND THAT IS THE ONE REAL DIFFERENCE
//
// nearbyTrailData hands MapLibre a Blob of the bytes it hashed, deliberately:
// re-serialising would draw something nobody checked. Nothing draws this file.
// It is read, indexed and searched, so it is parsed here - and the hash is
// still checked against the BYTES first, before anything is parsed out of them.
//
// A 404 IS AN ORDINARY ANSWER
//
// A release older than the artifact, a bucket a publish has not reached, a
// reviewer pointing the app at a local serve_processed.py, or no signal at all.
// All of them end the same way: no graph, so no day hikes, which
// chrome/PlanKindSheet.tsx states in a sentence rather than by offering a
// control that cannot work. Nothing about the chosen trail changes.
//
// IT IS HELD TO ITS PUBLISHED HASH (#197)
//
// Every artifact this app draws is, and this one decides where a router says a
// hiker can walk. Corrupted topology is not a cosmetic failure: it is a route
// down a trail that is not there, or a junction that does not exist, handed to
// somebody deciding where to go. Unverifiable bytes do not get routed on.
//
// A MANIFEST THAT NAMES NO HASH IS A REFUSAL HERE
//
// The same call lib/nearbyTrailData.ts makes, for a reason one step stronger.
// The module both of us departed from is lib/trailOverview.ts, which DOES draw
// unverifiable bytes - three seconds of a corridor sketch nobody reads a
// position off. nearbyTrailData refuses them because its lines sit under the
// hiker's dot; this refuses them because a graph decides where a router says
// somebody can walk, and there is no lesser use of one to fall back to.

import {
  DATA_CONFIGURED,
  dataUrl,
  TRAIL_GRAPH_ELEVATION_KEY,
  TRAIL_GRAPH_GEOMETRY_KEY,
  TRAIL_GRAPH_KEY,
} from './config'
import { publishedHash } from './dataManifest'
import { sha256Of } from './trailData'
import { buildGraphIndex, type TrailGraph, type TrailGraphIndex } from './trailGraph'

/** Whether the parsed JSON has the shape build_trail_graph.py writes. */
function isTrailGraph(value: unknown): value is TrailGraph {
  if (value === null || typeof value !== 'object') return false
  const candidate = value as { nodes?: unknown; edges?: unknown }
  if (!Array.isArray(candidate.nodes) || !Array.isArray(candidate.edges)) return false
  // Spot-check the first of each rather than every row. A generated artifact
  // is uniform or it is broken, and walking 3,000 edges to prove what the hash
  // already proved would cost a hiker time on a cold start.
  const firstNode = candidate.nodes[0]
  if (candidate.nodes.length > 0) {
    if (!Array.isArray(firstNode) || firstNode.length !== 2) return false
    if (typeof firstNode[0] !== 'number' || typeof firstNode[1] !== 'number') return false
  }
  const firstEdge = candidate.edges[0]
  if (candidate.edges.length > 0) {
    if (firstEdge === null || typeof firstEdge !== 'object') return false
    const edge = firstEdge as { from?: unknown; to?: unknown; length_m?: unknown }
    if (typeof edge.from !== 'number' || typeof edge.to !== 'number') return false
    if (typeof edge.length_m !== 'number') return false
  }
  return true
}

/**
 * The junction graph, indexed and ready to route on, or null when this phone
 * has not got one.
 *
 * Null is an ordinary state, not a failure - see the header. Every caller
 * treats it as "no day hikes yet" rather than as an error to report.
 */
export async function fetchTrailGraph(
  signal?: AbortSignal,
): Promise<TrailGraphIndex | null> {
  if (!DATA_CONFIGURED) return null

  try {
    const response = await fetch(dataUrl(TRAIL_GRAPH_KEY), { signal })
    if (!response.ok) return null

    const bytes = new Uint8Array(await response.arrayBuffer())
    const expected = await publishedHash(TRAIL_GRAPH_KEY, { signal })
    // No hash, no routing. There is no lesser use of a graph to fall back to.
    if (expected === null) return null
    if ((await sha256Of(bytes)) !== expected) return null

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes))
    // The hash proves the bytes are the published ones. This proves the
    // published ones are a graph - a manifest and an artifact can be right
    // about each other and still be the wrong file.
    if (!isTrailGraph(parsed)) return null

    return buildGraphIndex(parsed)
  } catch {
    // Every way a fetch, a decode or a parse can fail, the abort included.
    // None of them is worth a word to the hiker.
    return null
  }
}

/** Whether the parsed JSON is one coordinate list per edge. */
function isGraphGeometry(value: unknown): value is Array<Array<[number, number]>> {
  if (!Array.isArray(value)) return false
  const first = value[0]
  if (value.length > 0) {
    if (!Array.isArray(first) || first.length < 2) return false
    const vertex = first[0]
    if (
      !Array.isArray(vertex) ||
      typeof vertex[0] !== 'number' ||
      typeof vertex[1] !== 'number'
    ) {
      return false
    }
  }
  return true
}

/**
 * The graph's edge vertices, fetched lazily when the day-hike builder opens.
 *
 * `edgeCount` is the graph the caller already holds, and the check against it
 * is the point: the two artifacts are index-aligned, and edge 40 drawn from
 * edge 41's vertices is a route on the wrong trail. A count mismatch means
 * the pair on this phone came from two different publishes, and null - no
 * highlight, chords refused - beats drawing the wrong one.
 */
export async function fetchTrailGraphGeometry(
  edgeCount: number,
  signal?: AbortSignal,
): Promise<Array<Array<[number, number]>> | null> {
  if (!DATA_CONFIGURED) return null

  try {
    const response = await fetch(dataUrl(TRAIL_GRAPH_GEOMETRY_KEY), { signal })
    if (!response.ok) return null

    const bytes = new Uint8Array(await response.arrayBuffer())
    const expected = await publishedHash(TRAIL_GRAPH_GEOMETRY_KEY, { signal })
    if (expected === null) return null
    if ((await sha256Of(bytes)) !== expected) return null

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes))
    if (!isGraphGeometry(parsed)) return null
    if (parsed.length !== edgeCount) return null

    return parsed
  } catch {
    return null
  }
}

/**
 * The index with its edges carrying their vertices - a NEW index, the input
 * untouched, so a caller holding the routing-only index keeps it.
 */
export function attachTrailGraphGeometry(
  index: TrailGraphIndex,
  geometry: Array<Array<[number, number]>>,
): TrailGraphIndex {
  if (geometry.length !== index.graph.edges.length) return index
  const graph = {
    nodes: index.graph.nodes,
    edges: index.graph.edges.map((edge, edgeIndex) => ({
      ...edge,
      geometry: geometry[edgeIndex],
    })),
  }
  return buildGraphIndex(graph)
}

/** Whether the parsed JSON is one `[gain, loss]` pair (or null) per edge. */
function isGraphElevation(value: unknown): value is Array<[number, number] | null> {
  if (!Array.isArray(value)) return false
  // Spot-check the first ENTRY THAT IS NOT NULL, not simply the first entry:
  // a graph whose leading edges sit in a DEM gap is a real artifact, and
  // reading its leading null as "wrong shape" would throw the whole file away
  // over the one case it is designed to express.
  const first = value.find((entry) => entry !== null)
  if (first === undefined) return true
  if (!Array.isArray(first) || first.length !== 2) return false
  return typeof first[0] === 'number' && typeof first[1] === 'number'
}

/**
 * The climb along each edge, fetched lazily when the day-hike builder opens.
 *
 * Same shape as {@link fetchTrailGraphGeometry} and for the same reasons -
 * held to its published hash, refused outright when the manifest names no
 * hash, and refused when its length disagrees with the graph the caller
 * already holds. That last check is the one that matters most here: edge 40
 * priced from edge 41's climb is not a visible defect, it is a plausible
 * number against the wrong trail.
 *
 * Null - no elevation on this phone - is ordinary. The builder still routes
 * and the card still prints miles; only the climb and the ≈time go unsaid,
 * which is what they did before this artifact existed.
 */
export async function fetchTrailGraphElevation(
  edgeCount: number,
  signal?: AbortSignal,
): Promise<Array<[number, number] | null> | null> {
  if (!DATA_CONFIGURED) return null

  try {
    const response = await fetch(dataUrl(TRAIL_GRAPH_ELEVATION_KEY), { signal })
    if (!response.ok) return null

    const bytes = new Uint8Array(await response.arrayBuffer())
    const expected = await publishedHash(TRAIL_GRAPH_ELEVATION_KEY, { signal })
    if (expected === null) return null
    if ((await sha256Of(bytes)) !== expected) return null

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes))
    if (!isGraphElevation(parsed)) return null
    if (parsed.length !== edgeCount) return null

    return parsed
  } catch {
    return null
  }
}

/**
 * The index with its edges carrying their climb - a NEW index, the input
 * untouched, so a caller holding the elevation-free one keeps it.
 */
export function attachTrailGraphElevation(
  index: TrailGraphIndex,
  elevation: Array<[number, number] | null>,
): TrailGraphIndex {
  if (elevation.length !== index.graph.edges.length) return index
  const graph = {
    nodes: index.graph.nodes,
    edges: index.graph.edges.map((edge, edgeIndex) => ({
      ...edge,
      climb: elevation[edgeIndex],
    })),
  }
  return buildGraphIndex(graph)
}
