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
// A 404 IS AN ORDINARY ANSWER, AND IT IS NOT THE ONLY ONE (#1049)
//
// A release older than the artifact, a bucket a publish has not reached, a
// reviewer pointing the app at a local serve_processed.py, or no signal at
// all. All of them end the same way for the ROUTER - no graph, so no day
// hikes - and they are emphatically not the same answer for the HIKER, which
// is what this module used to get wrong.
//
// It returned bare `null` for six different situations under a comment saying
// none of them was worth a word, and chrome/PlanKindSheet.tsx then told all
// six "It arrives with the next data sync." Four of the six never resolve by
// waiting: a build with no bucket, a release with no graph in it, a manifest
// that names no hash, and bytes that fail it. #1048 is the fifth - the graph
// published to UA and never promoted - and a hiker was told to wait for a
// sync that was never coming, which is #312's bug one surface over.
//
// So {@link loadTrailGraph} carries the REASON, and the sheet says the true
// sentence for each. What the router does is unchanged: no graph is no graph.
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
import { publishedHash, publishedSnapshot } from './dataManifest'
import {
  readStoredGraph,
  writeStoredGraph,
  type StoredGraphArtifact,
} from './trailGraphStore'
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
 * Why this phone has no junction graph.
 *
 * The distinction that matters to a hiker is not which of these it is; it is
 * whether WAITING FIXES IT. Exactly one of them resolves on its own, and
 * {@link isSettledAbsence} is the single place that says which - so the copy,
 * the retry and the tests all read one rule rather than three copies of it.
 */
export type TrailNetworkAbsence =
  /** This build names no bucket at all (`DATA_CONFIGURED` false). A
   *  developer's checkout without a .env; never a hiker's phone. */
  | 'unconfigured'
  /** The request did not complete - no signal, DNS, a reset, an abort. The
   *  one absence a connection cures. */
  | 'unreachable'
  /** The bucket answered, and this release has no graph in it. A fact about
   *  the release, not about the device: #1048 is this, on production, today. */
  | 'not-in-release'
  /** The manifest names no hash for the key, or the bytes do not match the one
   *  it names. Unverifiable topology does not get routed on - see the header. */
  | 'unverifiable'
  /** Verified bytes that are not a graph. A manifest and an artifact can be
   *  right about each other and still be the wrong file. */
  | 'not-a-graph'
  /**
   * A real, valid graph with no routable trail in it.
   *
   * A ring with nothing maintained inside it publishes empty, and the loader
   * accepts that deliberately - it is a fact about the ground, not a broken
   * file, and the test pinning it says so. But `graphIndex !== null` then
   * means "holds a file shaped like a graph", not "can route", so the door
   * opened onto a builder that could find no route for any tap (#1044
   * review). An enabled control that answers nothing is strictly worse for a
   * hiker than an honest refusal, and harder to recognise as a data problem.
   */
  | 'empty'

/**
 * What a surface that SPEAKS about the graph needs to know.
 *
 * Three states rather than two, because "nothing has answered yet" and "there
 * isn't one" are different sentences and a launch spends its first moments in
 * the first. Collapsing them is how a door that is about to open reads as a
 * door that never will.
 */
export type TrailNetworkState =
  | { kind: 'ready' }
  | { kind: 'looking' }
  | { kind: 'absent'; because: TrailNetworkAbsence }

/** The graph, or why there isn't one. */
export type TrailGraphLoad =
  | { kind: 'graph'; index: TrailGraphIndex }
  | { kind: 'absent'; because: TrailNetworkAbsence }

/**
 * Whether an absence is one that waiting will not cure.
 *
 * Load-bearing twice over: it decides whether the sheet may say "it needs a
 * connection", and it decides whether the shell asks the bucket again. A
 * settled absence re-requested on every render is a hammer on a bucket that
 * has already answered.
 */
export function isSettledAbsence(because: TrailNetworkAbsence): boolean {
  return because !== 'unreachable'
}

/**
 * The junction graph, indexed and ready to route on - or the reason there is
 * none.
 *
 * An absence is an ordinary state, not an error to report. What is new (#1049)
 * is that it is a DIFFERENT ordinary state each time, and the caller is told
 * which.
 */
export async function loadTrailGraph(
  signal?: AbortSignal,
  online = true,
): Promise<TrailGraphLoad> {
  if (!DATA_CONFIGURED) return { kind: 'absent', because: 'unconfigured' }

  // STORE FIRST WHEN THERE IS NO CONNECTION (#1050), which is the whole point
  // of the store: a hiker at a trailhead with no signal is the situation this
  // app exists for, and until this branch existed they got the builder's
  // refusal there and a working one at the hostel.
  //
  // The stored bytes are trusted without re-asking the manifest, because a
  // phone offline cannot reach it - and nothing is ever written that did not
  // match the manifest when it was fetched. See lib/trailGraphStore.ts.
  if (!online) {
    const stored = await readStoredGraph(TRAIL_GRAPH_KEY)
    if (stored === null) return { kind: 'absent', because: 'unreachable' }
    const parsed = await parseStoredGraph(stored)
    return parsed === null
      ? { kind: 'absent', because: 'not-a-graph' }
      : { kind: 'graph', index: parsed }
  }

  try {
    const response = await fetch(dataUrl(TRAIL_GRAPH_KEY), { signal })
    // Any non-2xx, not only 404. A 403 on a misconfigured bucket and a 500
    // from the edge are both "this bucket is not serving a graph", and
    // neither is cured by waiting for a connection the phone already has.
    if (!response.ok) return { kind: 'absent', because: 'not-in-release' }

    const bytes = new Uint8Array(await response.arrayBuffer())
    const expected = await publishedHash(TRAIL_GRAPH_KEY, { signal })
    // No hash, no routing. There is no lesser use of a graph to fall back to.
    if (expected === null) return { kind: 'absent', because: 'unverifiable' }
    if ((await sha256Of(bytes)) !== expected) {
      return { kind: 'absent', because: 'unverifiable' }
    }

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes))
    // The hash proves the bytes are the published ones. This proves the
    // published ones are a graph - a manifest and an artifact can be right
    // about each other and still be the wrong file.
    if (!isTrailGraph(parsed)) return { kind: 'absent', because: 'not-a-graph' }

    // Kept for the next launch, verified. A refusal here costs nothing: the
    // bytes in hand still route this session, exactly as they did before the
    // store existed.
    void keepVerified(TRAIL_GRAPH_KEY, bytes, expected, response, signal)

    return { kind: 'graph', index: buildGraphIndex(parsed) }
  } catch {
    // Every way a fetch can fail to complete, the abort included. Reported as
    // reachability rather than as a fault, because that is the honest reading
    // of a request that never got an answer - and it is the one absence the
    // shell will try again.
    //
    // A JSON.parse throw lands here too and is NOT reachability. It is
    // unreachable in practice: the bytes matched a published hash one line
    // above, so a release whose graph does not parse is one whose manifest
    // signed off on it. Rather than a second try/catch for a case nobody can
    // produce, it costs one retry on reconnect and then settles.
    return { kind: 'absent', because: 'unreachable' }
  }
}

/**
 * The graph or null - {@link loadTrailGraph} for a caller that only needs to
 * know whether it has one.
 *
 * Kept because most of them genuinely do not care why: the router either has
 * topology to walk or it has not. Only the surfaces that SPEAK to a hiker
 * about the absence need the reason.
 */
export async function fetchTrailGraph(
  signal?: AbortSignal,
): Promise<TrailGraphIndex | null> {
  const load = await loadTrailGraph(signal)
  return load.kind === 'graph' ? load.index : null
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
  online = true,
): Promise<Array<Array<[number, number]>> | null> {
  if (!DATA_CONFIGURED) return null

  if (!online)
    return await readStoredJson(TRAIL_GRAPH_GEOMETRY_KEY, isGraphGeometry, edgeCount)

  try {
    const response = await fetch(dataUrl(TRAIL_GRAPH_GEOMETRY_KEY), { signal })
    if (!response.ok)
      return await readStoredJson(TRAIL_GRAPH_GEOMETRY_KEY, isGraphGeometry, edgeCount)

    const bytes = new Uint8Array(await response.arrayBuffer())
    const expected = await publishedHash(TRAIL_GRAPH_GEOMETRY_KEY, { signal })
    if (expected === null) return null
    if ((await sha256Of(bytes)) !== expected) return null

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes))
    if (!isGraphGeometry(parsed)) return null
    if (parsed.length !== edgeCount) return null

    void keepVerified(TRAIL_GRAPH_GEOMETRY_KEY, bytes, expected, response, signal)
    return parsed
  } catch {
    // A refused origin, a dropped connection, a signal that turned out not to
    // be one. The stored copy answers where there is one - the same fallback
    // the offline branch above takes, arrived at from the other direction.
    return await readStoredJson(TRAIL_GRAPH_GEOMETRY_KEY, isGraphGeometry, edgeCount)
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
  online = true,
): Promise<Array<[number, number] | null> | null> {
  if (!DATA_CONFIGURED) return null

  if (!online) {
    return await readStoredJson(TRAIL_GRAPH_ELEVATION_KEY, isGraphElevation, edgeCount)
  }

  try {
    const response = await fetch(dataUrl(TRAIL_GRAPH_ELEVATION_KEY), { signal })
    if (!response.ok) {
      return await readStoredJson(TRAIL_GRAPH_ELEVATION_KEY, isGraphElevation, edgeCount)
    }

    const bytes = new Uint8Array(await response.arrayBuffer())
    const expected = await publishedHash(TRAIL_GRAPH_ELEVATION_KEY, { signal })
    if (expected === null) return null
    if ((await sha256Of(bytes)) !== expected) return null

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes))
    if (!isGraphElevation(parsed)) return null
    if (parsed.length !== edgeCount) return null

    void keepVerified(TRAIL_GRAPH_ELEVATION_KEY, bytes, expected, response, signal)
    return parsed
  } catch {
    return await readStoredJson(TRAIL_GRAPH_ELEVATION_KEY, isGraphElevation, edgeCount)
  }
}

/**
 * Keep a verified artifact for the next launch, and never let that failing
 * cost the session the bytes it already holds.
 *
 * The manifest version is read from the same snapshot the hash came from where
 * one is available. It is recorded rather than acted on - see
 * lib/trailGraphStore.ts's header for what it is for.
 */
async function keepVerified(
  publishedKey: string,
  bytes: Uint8Array,
  hash: string,
  response: Response,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const snapshot = await publishedSnapshot({ signal })
    await writeStoredGraph(publishedKey, {
      bytes: new Blob([bytes as unknown as BlobPart], {
        type: response.headers.get('content-type') ?? 'application/json',
      }),
      hash,
      version: snapshot.version,
    })
  } catch {
    // Storing is an improvement on the NEXT launch, never a condition of this
    // one. Every way this can fail ends here on purpose.
  }
}

/**
 * A stored artifact, parsed and held to the same shape and edge-count checks a
 * fresh fetch is.
 *
 * The checks are not skipped for stored bytes, and the edge-count one is the
 * reason: a phone can hold a graph from one release and a geometry file from
 * the next, and edge 40 drawn from edge 41's vertices is a route on the wrong
 * trail. That check is what makes a mismatched PAIR degrade to no highlight
 * rather than to a wrong one, and it matters more offline than online, because
 * offline there is no fresh copy coming to correct it.
 */
async function readStoredJson<T>(
  publishedKey: string,
  isShape: (value: unknown) => value is T & { length: number },
  edgeCount: number,
): Promise<T | null> {
  const stored = await readStoredGraph(publishedKey)
  if (stored === null) return null
  try {
    const parsed: unknown = JSON.parse(await stored.bytes.text())
    if (!isShape(parsed)) return null
    if (parsed.length !== edgeCount) return null
    return parsed
  } catch {
    return null
  }
}

/** A stored graph, parsed and shape-checked - {@link readStoredJson} without
 *  an edge count to check against, because this file IS what defines one. */
async function parseStoredGraph(
  stored: StoredGraphArtifact,
): Promise<TrailGraphIndex | null> {
  try {
    const parsed: unknown = JSON.parse(await stored.bytes.text())
    if (!isTrailGraph(parsed)) return null
    return buildGraphIndex(parsed)
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
