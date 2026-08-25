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
// The same call lib/nearbyTrailData.ts makes and for a stronger reason. There,
// an unverifiable line is drawn as context. Here there is no lesser use to
// fall back to - a graph is either trusted for routing or it is not loaded.

import { DATA_CONFIGURED, dataUrl, TRAIL_GRAPH_KEY } from './config'
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
