// Loading the junction graph (#975, pipeline/build_trail_graph.py) - in 1°
// cells since #1257 stage 3 (pipeline/cut_trail_graph.py).
//
// map/networkTiles.ts draws the network's LINES. This loads their TOPOLOGY
// for lib/trailGraph.ts to route over. Two deliveries of one derivation, and
// the second is useless without the first, which is why they are read the
// same way - by the cell, never the whole - and fail the same way.
//
// WHY CELLS, AND WHAT A CELL IS HERE
//
// The whole graph was promoted at 78,595,556 bytes on 2026-09-07 (nationwide
// USFS trails, #1231), and parsing it on the main thread was "the app is
// hanging on the first page" (#1254). The budget that stopped that fetch left
// the phone with no day hikes at all. So the pipeline cuts the graph into the
// same whole-degree cells the basemap and the network tiles are cut into, and
// this module loads a SHARD per cell: the routing half (`graph`), and lazily
// its three companions (`geometry` when the builder opens, `elevation` with
// it, `profile` when a chart opens). Which cells is lib/useTrailGraph.ts's
// decision - under the hike, at the fix, under a camera past the seam, and
// where the hiker taps.
//
// A SHARD IS A COMPLETE GRAPH THAT REMEMBERS WHERE IT CAME FROM. Its
// `from`/`to` index its own `nodes`, so it routes on its own; its `node_ids`
// and `edge_ids` carry each row's position in the whole graph, so two shards
// merge without matching coordinates on the phone. {@link mergeGraphShard}
// is that merge, and it is APPEND-ONLY: a node or an edge already merged keeps
// its position when a later cell arrives, because a draft under construction
// holds `GraphPoint.edgeIndex` values (lib/dayHikeDraft.ts) and a merge that
// renumbered them would move every tap onto a different trail. An edge that
// rides in two cells (one crossing the seam, or within the cutter's margin of
// it) is merged once.
//
// PARSED, NOT AN OBJECT URL, AND THAT IS THE ONE REAL DIFFERENCE
//
// nearbyTrailData hands MapLibre a Blob of the bytes it hashed, deliberately:
// re-serialising would draw something nobody checked. Nothing draws these
// files. They are read, indexed and searched, so they are parsed here - and
// the hash is still checked against the BYTES first, before anything is
// parsed out of them.
//
// A 404 IS AN ORDINARY ANSWER, AND IT IS NOT THE ONLY ONE (#1049)
//
// A release older than the cut, a bucket a publish has not reached, a
// reviewer pointing the app at a local serve_processed.py, or no signal at
// all. All of them end the same way for the ROUTER - no shard, so no day
// hikes on that ground - and they are emphatically not the same answer for
// the HIKER, which is what this module used to get wrong.
//
// It returned bare `null` for six different situations under a comment saying
// none of them was worth a word, and chrome/PlanKindSheet.tsx then told all
// six "It arrives with the next data sync." Four of the six never resolve by
// waiting: a build with no bucket, a release with no graph in it, a manifest
// that names no hash, and bytes that fail it. #1048 is the fifth - the graph
// published to UA and never promoted - and a hiker was told to wait for a
// sync that was never coming, which is #312's bug one surface over.
//
// So every load here carries the REASON, and the door says the true sentence
// for each (lib/trailNetworkText.ts). What the router does is unchanged: no
// graph is no graph.
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
  trailGraphCellKey,
  type TrailGraphCellHalf,
} from './config'
import { oversized, warnOversized } from './artifactBudget'
import type { CoverageCell } from './coverageCells'
import { publishedSnapshot } from './dataManifest'
import { graphCellStoreKey, readStoredGraph, writeStoredGraph } from './trailGraphStore'
import { sha256Of } from './trailData'
import {
  buildGraphIndex,
  type GraphEdge,
  type TrailGraph,
  type TrailGraphIndex,
} from './trailGraph'

/** One cell's routing half as cut_trail_graph.py writes it: a graph of its
 *  own, plus each node's and edge's position in the whole graph. */
export interface GraphShard extends TrailGraph {
  node_ids: number[]
  edge_ids: number[]
}

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

/** Whether the parsed JSON is a shard: a graph that also says where each of
 *  its rows sits in the whole. The two id lists are held to the lengths of
 *  the lists they describe, because a shard whose ids are off by one merges
 *  every one of its edges onto the wrong node. */
export function isGraphShard(value: unknown): value is GraphShard {
  if (!isTrailGraph(value)) return false
  const candidate = value as TrailGraph & { node_ids?: unknown; edge_ids?: unknown }
  if (!Array.isArray(candidate.node_ids) || !Array.isArray(candidate.edge_ids))
    return false
  if (candidate.node_ids.length !== candidate.nodes.length) return false
  if (candidate.edge_ids.length !== candidate.edges.length) return false
  const firstNodeId = candidate.node_ids[0]
  const firstEdgeId = candidate.edge_ids[0]
  if (candidate.node_ids.length > 0 && typeof firstNodeId !== 'number') return false
  if (candidate.edge_ids.length > 0 && typeof firstEdgeId !== 'number') return false
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
   * A shard this phone cannot hold (#1254): the manifest says it decodes to
   * more than lib/artifactBudget.ts allows, so it was not fetched - or, where
   * the manifest named no size, it arrived and was not parsed. Settled the
   * way a 404 is: nothing on this phone changes it, and a smaller publish
   * does. Since the cut, this is one cell rather than the whole: the whole
   * graph of 2026-09-07 was 78,595,556 bytes, and parsing it on the main
   * thread was what "the app is hanging on the first page" was; its densest
   * cell is 12.7 MB.
   */
  | 'too-large'
  /**
   * A real, valid index with no cell for this ground.
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

/** One cell's shard, or why there isn't one. */
export type GraphShardLoad =
  { kind: 'shard'; shard: GraphShard } | { kind: 'absent'; because: TrailNetworkAbsence }

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
 * The manifest's word on one artifact: the hash its bytes must match, and
 * the size they decode to. Null for either where the manifest names none.
 */
async function published(
  key: string,
  signal?: AbortSignal,
): Promise<{ hash: string | null; decodedBytes: number | null }> {
  const snapshot = await publishedSnapshot({ signal })
  return {
    hash: snapshot.hashes[key] ?? null,
    decodedBytes: snapshot.decodedSizes[key] ?? null,
  }
}

/**
 * One cell's routing shard, verified - or the reason there is none.
 *
 * An absence is an ordinary state, not an error to report. What is new (#1049)
 * is that it is a DIFFERENT ordinary state each time, and the caller is told
 * which.
 */
export async function loadGraphShard(
  cell: CoverageCell,
  signal?: AbortSignal,
  online = true,
): Promise<GraphShardLoad> {
  if (!DATA_CONFIGURED) return { kind: 'absent', because: 'unconfigured' }
  const key = trailGraphCellKey(cell.name, 'graph')
  const storeKey = graphCellStoreKey(cell.name, 'graph')

  // STORE FIRST WHEN THERE IS NO CONNECTION (#1050), which is the whole point
  // of the store: a hiker at a trailhead with no signal is the situation this
  // app exists for, and until this branch existed they got the builder's
  // refusal there and a working one at the hostel.
  //
  // The stored bytes are trusted without re-asking the manifest, because a
  // phone offline cannot reach it - and nothing is ever written that did not
  // match the manifest when it was fetched. See lib/trailGraphStore.ts.
  if (!online) {
    const stored = await readStoredGraph(storeKey)
    if (stored === null) return { kind: 'absent', because: 'unreachable' }
    const parsed = await parseStored(stored.bytes, isGraphShard)
    return parsed === null
      ? { kind: 'absent', because: 'not-a-graph' }
      : { kind: 'shard', shard: parsed }
  }

  try {
    // The manifest first, and before the fetch (#1254). Every loader here
    // used to fetch, read the body whole and only then ask the manifest what
    // the bytes should hash to - an order that cost nothing while every
    // artifact fit, and cost a frozen main thread the day one did not,
    // because by the time anything could have weighed the graph it was
    // already in memory. Asking first is what lets a shard the phone cannot
    // hold be declined for the price of a ~KB manifest read, with no bytes
    // moved at all.
    const { hash: expected, decodedBytes } = await published(key, signal)
    if (oversized(decodedBytes)) {
      warnOversized(key, decodedBytes, 'manifest')
      return { kind: 'absent', because: 'too-large' }
    }

    const response = await fetch(dataUrl(key), { signal })
    // Any non-2xx, not only 404. A 403 on a misconfigured bucket and a 500
    // from the edge are both "this bucket is not serving this cell", and
    // neither is cured by waiting for a connection the phone already has.
    if (!response.ok) return { kind: 'absent', because: 'not-in-release' }

    const bytes = new Uint8Array(await response.arrayBuffer())
    // The backstop for a manifest that named no size: the bytes in hand are
    // weighed before anything hashes or parses them.
    if (oversized(bytes.byteLength)) {
      warnOversized(key, bytes.byteLength, 'response')
      return { kind: 'absent', because: 'too-large' }
    }
    // No hash, no routing. There is no lesser use of a graph to fall back to.
    if (expected === null) return { kind: 'absent', because: 'unverifiable' }
    if ((await sha256Of(bytes)) !== expected) {
      return { kind: 'absent', because: 'unverifiable' }
    }

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes))
    // The hash proves the bytes are the published ones. This proves the
    // published ones are a shard - a manifest and an artifact can be right
    // about each other and still be the wrong file.
    if (!isGraphShard(parsed)) return { kind: 'absent', because: 'not-a-graph' }

    // Kept for the next launch, verified. A refusal here costs nothing: the
    // bytes in hand still route this session, exactly as they did before the
    // store existed.
    void keepVerified(storeKey, bytes, expected, response, signal)

    return { kind: 'shard', shard: parsed }
  } catch {
    // Every way a fetch can fail to complete, the abort included. Reported as
    // reachability rather than as a fault, because that is the honest reading
    // of a request that never got an answer - and it is the one absence the
    // shell will try again.
    //
    // BUT THE STORE FIRST, which the whole-graph loader never did: a phone
    // that reports a connection and cannot complete a request - one bar on a
    // ridge, a captive portal, a bucket that stopped answering - used to be
    // told the graph was unreachable while holding it. A cell kept is a cell
    // that routes; "unreachable" is what this says only when the phone holds
    // nothing for it. The companions below take the same fallback.
    //
    // A JSON.parse throw lands here too and is NOT reachability. It is
    // unreachable in practice: the bytes matched a published hash one line
    // above, so a release whose shard does not parse is one whose manifest
    // signed off on it. Rather than a second try/catch for a case nobody can
    // produce, it costs one retry on reconnect and then settles.
    const stored = await readStoredGraph(storeKey)
    const parsed = stored === null ? null : await parseStored(stored.bytes, isGraphShard)
    return parsed === null
      ? { kind: 'absent', because: 'unreachable' }
      : { kind: 'shard', shard: parsed }
  }
}

/** One cell as merged: its name, and its shard's edges in the shard's own
 *  order as whole-graph ids - what aligns a companion fetched for that cell
 *  with the merged edges it describes. */
export interface LoadedGraphCell {
  name: string
  edgeIds: readonly number[]
}

/**
 * The cells a phone has merged into one graph, and the bookkeeping that keeps
 * every later merge append-only (see the header).
 */
export interface MergedGraph {
  graph: TrailGraph
  /** Merged edge position -> whole-graph edge id. */
  edgeIds: readonly number[]
  /** Whole-graph node id -> merged position. */
  nodePositions: ReadonlyMap<number, number>
  /** Whole-graph edge id -> merged position. */
  edgePositions: ReadonlyMap<number, number>
  cells: readonly LoadedGraphCell[]
}

export function emptyMergedGraph(): MergedGraph {
  return {
    graph: { nodes: [], edges: [] },
    edgeIds: [],
    nodePositions: new Map(),
    edgePositions: new Map(),
    cells: [],
  }
}

/**
 * `merged` with one more cell's shard in it - a NEW value, the input untouched.
 *
 * APPEND-ONLY, which is the property everything routing on the result depends
 * on: every node and edge already merged keeps its position, unseen ones go on
 * the end, and an edge two cells both carry is merged once, from whichever
 * arrived first. A cell merged twice is a no-op.
 */
export function mergeGraphShard(
  merged: MergedGraph,
  name: string,
  shard: GraphShard,
): MergedGraph {
  if (merged.cells.some((cell) => cell.name === name)) return merged

  const nodes = [...merged.graph.nodes]
  const edges: GraphEdge[] = [...merged.graph.edges]
  const edgeIds = [...merged.edgeIds]
  const nodePositions = new Map(merged.nodePositions)
  const edgePositions = new Map(merged.edgePositions)

  // The shard's local node index -> the merged position, resolved through the
  // whole graph's id so two cells' copies of one junction are one node.
  const local = shard.node_ids.map((nodeId, position) => {
    const known = nodePositions.get(nodeId)
    if (known !== undefined) return known
    const at = nodes.length
    nodes.push(shard.nodes[position])
    nodePositions.set(nodeId, at)
    return at
  })

  shard.edges.forEach((edge, position) => {
    const edgeId = shard.edge_ids[position]
    if (edgePositions.has(edgeId)) return
    edgePositions.set(edgeId, edges.length)
    edgeIds.push(edgeId)
    edges.push({ ...edge, from: local[edge.from], to: local[edge.to] })
  })

  return {
    graph: { nodes, edges },
    edgeIds,
    nodePositions,
    edgePositions,
    cells: [...merged.cells, { name, edgeIds: shard.edge_ids }],
  }
}

/** The graph, or why there isn't one - the cells asked for, loaded and
 *  merged in one call. What lib/useTrailGraph.ts does incrementally, for a
 *  caller that only wants the answer. */
export type TrailGraphLoad =
  | { kind: 'graph'; index: TrailGraphIndex; merged: MergedGraph }
  | { kind: 'absent'; because: TrailNetworkAbsence }

export async function loadTrailGraphCells(
  cells: readonly CoverageCell[],
  signal?: AbortSignal,
  online = true,
): Promise<TrailGraphLoad> {
  if (!DATA_CONFIGURED) return { kind: 'absent', because: 'unconfigured' }
  if (cells.length === 0) return { kind: 'absent', because: 'empty' }
  let merged = emptyMergedGraph()
  for (const cell of cells) {
    const load = await loadGraphShard(cell, signal, online)
    if (load.kind === 'absent') return load
    merged = mergeGraphShard(merged, cell.name, load.shard)
  }
  return { kind: 'graph', index: buildGraphIndex(merged.graph), merged }
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

/** Whether the parsed JSON is one `[gain, loss]` pair (or null) per edge. */
function isGraphElevation(value: unknown): value is Array<[number, number] | null> {
  if (!Array.isArray(value)) return false
  // Spot-check the first ENTRY THAT IS NOT NULL, not simply the first entry:
  // a cell whose leading edges sit in a DEM gap is a real artifact, and
  // reading its leading null as "wrong shape" would throw the whole file away
  // over the one case it is designed to express.
  const first = value.find((entry) => entry !== null)
  if (first === undefined) return true
  if (!Array.isArray(first) || first.length !== 2) return false
  return typeof first[0] === 'number' && typeof first[1] === 'number'
}

/**
 * Whether the parsed JSON is one array of samples (or null) per edge.
 *
 * Spot-checked on the first entry that is not null, for the reason
 * {@link isGraphElevation} states. The first SAMPLE may legitimately be null
 * too - a hole in the DEM with its place on the axis kept - so the check
 * accepts either.
 */
function isGraphProfile(value: unknown): value is Array<Array<number | null> | null> {
  if (!Array.isArray(value)) return false
  const first = value.find((entry) => entry !== null)
  if (first === undefined) return true
  if (!Array.isArray(first)) return false
  if (first.length === 0) return true
  return typeof first[0] === 'number' || first[0] === null
}

/**
 * One cell's companion half, held to its published hash and to ITS CELL'S
 * edge count - null on every way of not having one.
 *
 * The count check against the cell's shard is the point: the halves are
 * index-aligned per cell, and edge 40 drawn from edge 41's vertices is a route
 * on the wrong trail. A mismatch means the pair on this phone came from two
 * different publishes, and null - no highlight, chords refused - beats drawing
 * the wrong one.
 */
async function fetchCompanionCell<E>(
  cell: LoadedGraphCell,
  half: Exclude<TrailGraphCellHalf, 'graph'>,
  isShape: (value: unknown) => value is E[],
  signal?: AbortSignal,
  online = true,
): Promise<E[] | null> {
  if (!DATA_CONFIGURED) return null
  const key = trailGraphCellKey(cell.name, half)
  const storeKey = graphCellStoreKey(cell.name, half)
  const stored = () => readStoredCompanion(storeKey, isShape, cell.edgeIds.length)

  if (!online) return await stored()

  try {
    // Weighed at the manifest before the fetch and at the response after it,
    // exactly as the shard is (#1254); null is what this half already means
    // by "not on this phone".
    const { hash: expected, decodedBytes } = await published(key, signal)
    if (oversized(decodedBytes)) {
      warnOversized(key, decodedBytes, 'manifest')
      return null
    }

    const response = await fetch(dataUrl(key), { signal })
    if (!response.ok) return await stored()

    const bytes = new Uint8Array(await response.arrayBuffer())
    if (oversized(bytes.byteLength)) {
      warnOversized(key, bytes.byteLength, 'response')
      return null
    }
    if (expected === null) return null
    if ((await sha256Of(bytes)) !== expected) return null

    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes))
    if (!isShape(parsed)) return null
    if (parsed.length !== cell.edgeIds.length) return null

    void keepVerified(storeKey, bytes, expected, response, signal)
    return parsed
  } catch {
    // A refused origin, a dropped connection, a signal that turned out not to
    // be one. The stored copy answers where there is one - the same fallback
    // the offline branch above takes, arrived at from the other direction.
    return await stored()
  }
}

/**
 * One companion for the whole merged graph: every merged cell's half, placed
 * at the merged edge positions - or null when any cell's is missing, on the
 * all-or-nothing rule the whole artifact already followed (a walk crossing an
 * edge nobody measured has no total at all rather than a total missing one
 * edge; a highlight missing one edge's vertices is a chord across a
 * switchback).
 */
async function fetchCompanionCells<E>(
  merged: MergedGraph,
  half: Exclude<TrailGraphCellHalf, 'graph'>,
  isShape: (value: unknown) => value is E[],
  signal?: AbortSignal,
  online = true,
): Promise<E[] | null> {
  const halves: E[][] = []
  for (const cell of merged.cells) {
    const data = await fetchCompanionCell(cell, half, isShape, signal, online)
    if (data === null) return null
    halves.push(data)
  }
  const aligned: Array<E | undefined> = new Array<E | undefined>(
    merged.edgeIds.length,
  ).fill(undefined)
  merged.cells.forEach((cell, cellIndex) => {
    const data = halves[cellIndex]
    cell.edgeIds.forEach((edgeId, position) => {
      const at = merged.edgePositions.get(edgeId)
      if (at !== undefined) aligned[at] = data[position]
    })
  })
  // Every merged edge came from some merged cell, whose half covered it.
  return aligned as E[]
}

/**
 * The merged graph's edge vertices, cell by cell, fetched lazily when the
 * day-hike builder opens. Null - no geometry on this phone for some cell - is
 * ordinary: the builder refuses taps until it lands (lib/dayHikeDraft.ts).
 */
export async function fetchTrailGraphGeometryCells(
  merged: MergedGraph,
  signal?: AbortSignal,
  online = true,
): Promise<Array<Array<[number, number]>> | null> {
  return fetchCompanionCells(merged, 'geometry', isGraphGeometry, signal, online)
}

/**
 * The climb along each merged edge, cell by cell - fetched lazily when the
 * builder opens. Null - no elevation on this phone - is ordinary. The
 * builder still routes and the card still prints miles; only the climb and
 * the ≈time go unsaid, which is what they did before this artifact existed.
 */
export async function fetchTrailGraphElevationCells(
  merged: MergedGraph,
  signal?: AbortSignal,
  online = true,
): Promise<Array<[number, number] | null> | null> {
  return fetchCompanionCells(merged, 'elevation', isGraphElevation, signal, online)
}

/**
 * The SHAPE of the ground along each merged edge, cell by cell - fetched when
 * a chart opens, and never with the builder (#1045). A different artifact from
 * the elevation one, and not a replacement for it: that file is the sanctioned
 * TOTAL a card prices from; this is what a ribbon draws. `lib/config.ts`
 * carries why they must not be swapped and `lib/walkProfile.ts` carries the
 * rules for reading this one. Null is ordinary and its consequence is exactly
 * #1041's: no ribbon on a followed walk.
 */
export async function fetchTrailGraphProfileCells(
  merged: MergedGraph,
  signal?: AbortSignal,
  online = true,
): Promise<Array<Array<number | null> | null> | null> {
  return fetchCompanionCells(merged, 'profile', isGraphProfile, signal, online)
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
  storeKey: string,
  bytes: Uint8Array,
  hash: string,
  response: Response,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const snapshot = await publishedSnapshot({ signal })
    await writeStoredGraph(storeKey, {
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

/** A stored companion, parsed and held to the same shape and edge-count
 *  checks a fresh fetch is - not skipped for stored bytes, because a phone
 *  can hold a shard from one release and a companion from the next. */
async function readStoredCompanion<T extends { length: number }>(
  storeKey: string,
  isShape: (value: unknown) => value is T,
  edgeCount: number,
): Promise<T | null> {
  const stored = await readStoredGraph(storeKey)
  if (stored === null) return null
  const parsed = await parseStored(stored.bytes, isShape)
  if (parsed === null || parsed.length !== edgeCount) return null
  return parsed
}

/** Stored bytes, parsed and shape-checked - null on anything else. */
async function parseStored<T>(
  bytes: Blob,
  isShape: (value: unknown) => value is T,
): Promise<T | null> {
  try {
    const parsed: unknown = JSON.parse(await bytes.text())
    return isShape(parsed) ? parsed : null
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
