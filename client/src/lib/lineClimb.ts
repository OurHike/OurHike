// How much a tapped trail climbs, out of the graph cells already on this
// phone (#1476).
//
// The figure exists and has had exactly one reader. pipeline/
// export_network_elevation.py measures `[gain_ft, loss_ft]` along every edge
// of the junction graph, cut_trail_graph.py files it into the same 1° cells
// as the routing shard, and lib/dayHikeCard.ts sums it - for a RESOLVED day
// hike. A hiker who never opens the builder has never seen it, on any trail,
// the A.T. included. "19.1 mi" is the number that decides nothing on its own;
// whether those miles are flat or over five Harriman knobs is the whole of
// whether somebody beats the dark.
//
// This is that sum for a LINE rather than a route, and it lives in its own
// module rather than in lineDetail.ts because it is arithmetic over the graph
// and lineDetail.ts is a string-builder that has never imported one.
//
// ======================================================================
// SUMMED WITHIN EDGES, NEVER ACROSS A NODE JOIN
// ======================================================================
//
// Not a rule this module remembers to follow - the only thing the artifact
// can express. Each entry is measured along one edge's own vertices, and the
// sum here is over edges, in feet. #559 measured what summing across a break
// in the ground costs: ~36,800 ft of climbing nobody did entered the
// published A.T. total, the largest a single +2,588 ft "step" across 25 m.
// build_trail_graph.py's ENDPOINT_SNAP_M is 8.0, so two edges meeting at one
// node can be metres apart on the ground and some unmeasured distance apart
// vertically. There is no concatenated profile here for that to hide in.
//
// ======================================================================
// THREE ABSENCES, AND CONFUSING ANY TWO OF THEM IS THE FAILURE
// ======================================================================
//
// A hiker reading "no climb figure" needs to know which kind, because two of
// them are things they can act on and one is not:
//
//   unmeasured   an edge the DEM never covered. `null` in the artifact, and
//                never 0 - absent means unknown (FEATURES.md). Summing the
//                edges that ARE measured would print a total that reads as
//                the whole trail's and is silently low, which is the
//                confidently-wrong answer on the band a hiker uses to judge
//                daylight.
//   partial      the line runs past the cells this phone holds. Not a gap in
//                anybody's data - a gap in the download, and the one a hiker
//                can fix.
//   none         this phone has no climb figures at all: a release published
//                without them (the elevation leg is opt-in), or a graph cell
//                that carries no elevation half.
//
// HOW `partial` IS DETECTED WITHOUT A NEW ARTIFACT. The tapped feature
// carries the published line's own length (`lengthMiles`, written by
// export_nearby_trails.records_to_geojson), and every matched edge carries
// `length_m`. If the edges this phone holds are materially shorter than the
// line that was published, the phone is holding part of the line. The two
// numbers reach the phone down different paths - the line through
// export_nearby_trails.py, the edges through build_trail_graph.py, each with
// its own simplification - so it needs a tolerance; see COVERAGE_TOLERANCE.
//
// THE FIELD IS NOT ALWAYS THERE, AND `unverified` IS WHAT THAT COSTS. This
// paragraph used to assert that export_nearby_trails.py wrote `length_miles`
// when no exporter did (#1516): the guard below could never fire, so a phone
// holding one cell of a long trail summed that cell's edges and printed the
// total as `measured` - silently low, on the band a hiker uses to judge
// daylight. #1516 added the field and added `unverified` for when it is
// missing anyway, which is the case that outlives the fix: a phone reads
// whatever release it downloaded, so a build running against data published
// before that exporter change sees no length on any line.

import type { GraphEdge, TrailGraph } from './trailGraph'

/** Metres to miles, at the one ratio this codebase uses (trailGraph.ts's
 *  `metresToMiles`, restated rather than imported to keep this module free of
 *  the routing index it has no other reason to pull in). */
const METRES_PER_MILE = 1609.344

/**
 * How far short of the steward's published length the edges on this phone may
 * fall before the answer is `partial` rather than a total.
 *
 * @unvalidated 8% is picked, not found. It has to absorb two disagreements
 * that are both real and neither measured here: the graph's `length_m` is
 * EPSG:5070 projected metres over vertices rounded to six decimals, while
 * `lengthMiles` is whatever the publishing organization measured and however
 * they measured it; and an edge is filed whole into every cell its bounding
 * box touches, so a held cell can carry slightly MORE of a line than the
 * square it names.
 *
 * WHICH WAY IT ROUNDS, AND WHY THAT IS THE SAFE ONE. Too tight and a hiker
 * holding the whole line is told to download something they already have -
 * annoying, and they can check. Too loose and a partial total prints as a
 * whole one, which is the silently-low figure this module exists to refuse.
 * So it is deliberately not generous: 8% of a 19-mile trail is a mile and a
 * half, and a phone missing more of a line than that is missing a cell.
 *
 * What would settle it: the distribution of (summed edge length / published
 * length) over every line in one published graph, which is a query over two
 * artifacts the pipeline already writes and nobody has run.
 */
export const COVERAGE_TOLERANCE = 0.08

/** What this phone can honestly say about a line's climb. */
export type LineClimb =
  /** Every edge of the line is here and measured. Feet, as published. */
  | { kind: 'measured'; gainFt: number; lossFt: number; miles: number }
  /**
   * Some edge of the line is on this phone with no climb measured against it
   * - a hole in the DEM. `measuredMiles` is how much of the line DOES have a
   * figure, so a sheet can say which part is unknown rather than only that
   * something is.
   */
  | { kind: 'unmeasured'; measuredMiles: number; unmeasuredMiles: number }
  /** The line runs past the cells this phone holds. */
  | { kind: 'partial'; heldMiles: number; publishedMiles: number }
  /**
   * Every edge this phone holds is measured, and there is no way to check
   * whether they are all of the line: the tapped feature carries no
   * `lengthMiles` to compare against (#1516).
   *
   * The gain and loss are real for `miles` of trail. What nobody can say is
   * whether `miles` is the whole trail, so the figure is reported against the
   * extent it was summed over rather than presented as the line's total.
   */
  | { kind: 'unverified'; gainFt: number; lossFt: number; miles: number }
  /** No climb figures on this phone for this line at all. */
  | { kind: 'none' }

/**
 * Everything this module needs about the tapped line, which is two facts.
 *
 * `ClimbedLine` rather than `TappedLine`, which is map/lineTaps.ts's name for
 * the whole set of facts a tap reports: a module importing both would
 * otherwise have two different types with one name, and this is the narrow
 * one - `TappedLine` satisfies it structurally, which is how the panel passes
 * one straight in.
 */
export interface ClimbedLine {
  /** The feature id, as map/lineTaps.ts reports it - the same string
   *  build_trail_graph.py copies onto every edge as `trail_id`. */
  id: string | null
  /** The steward's own published length, where they gave one. */
  lengthMiles?: number | null
}

/**
 * The edges of one line, in the merged graph's own order.
 *
 * By `trail_id` rather than by name: build_trail_graph.py copies the parent
 * line's id onto every edge for exactly this kind of question, and two
 * different trails can share a name ("Blue Trail" is not one trail).
 */
export function edgesOfLine(graph: TrailGraph, id: string): GraphEdge[] {
  return graph.edges.filter((edge) => edge.trail_id === id)
}

/**
 * What to say about a tapped line's climb.
 *
 * ORDER MATTERS AND IS THE DESIGN. `none` first, because a phone with no
 * elevation at all must not be told to download a cell it already has.
 * `unmeasured` before `partial`, because a DEM hole is a fact about the
 * world that downloading more cells cannot fix, and offering the download
 * would be the wrong instruction. `partial` last, so it is only ever reached
 * when every edge this phone holds does have a figure.
 */
export function lineClimb(
  graph: TrailGraph | null,
  line: ClimbedLine,
  /**
   * Per-edge `[gain_ft, loss_ft]`, index-aligned with `graph.edges`, for a
   * caller holding the companion BESIDE the graph rather than attached to it.
   *
   * WHY BOTH SHAPES. lib/trailGraphData.ts's `attachTrailGraphElevation`
   * builds a whole new index, which is right for the builder - it holds the
   * result across a session of routing. A tap is not that: it wants one
   * line's figure and is gone, and rebuilding an index of every merged edge
   * to read a handful would be work proportional to the wrong thing. So the
   * array may be passed straight in.
   *
   * A LENGTH THAT DISAGREES IS REFUSED, not trimmed - the same rule
   * lib/trailGraphData.ts keeps for every companion, and for its reason:
   * edge 40 priced from edge 41's climb is a plausible number against the
   * wrong trail, which is worse than no number.
   */
  elevation?: ReadonlyArray<[number, number] | null> | null,
): LineClimb {
  if (graph === null || line.id === null) return { kind: 'none' }
  const aligned =
    elevation !== undefined &&
    elevation !== null &&
    elevation.length === graph.edges.length
      ? elevation
      : null

  const edges: Array<{ edge: GraphEdge; climb: [number, number] | null | undefined }> = []
  graph.edges.forEach((edge, index) => {
    if (edge.trail_id !== line.id) return
    edges.push({ edge, climb: aligned === null ? edge.climb : aligned[index] })
  })
  if (edges.length === 0) return { kind: 'none' }

  // `undefined` is "this phone never fetched the elevation artifact" and
  // `null` is "the artifact has this edge and nobody measured it". Different
  // facts; the first is about the download and the second about the ground,
  // so they are counted apart rather than both read as a gap.
  if (edges.every(({ climb }) => climb === undefined)) return { kind: 'none' }

  let gainFt = 0
  let lossFt = 0
  let measuredMetres = 0
  let unmeasuredMetres = 0
  for (const { edge, climb } of edges) {
    if (climb === undefined || climb === null) {
      unmeasuredMetres += edge.length_m
      continue
    }
    gainFt += climb[0]
    lossFt += climb[1]
    measuredMetres += edge.length_m
  }

  if (unmeasuredMetres > 0) {
    return {
      kind: 'unmeasured',
      measuredMiles: measuredMetres / METRES_PER_MILE,
      unmeasuredMiles: unmeasuredMetres / METRES_PER_MILE,
    }
  }

  const heldMiles = measuredMetres / METRES_PER_MILE
  const published = line.lengthMiles

  // Nothing to compare against, so this phone cannot tell a whole trail from
  // part of one. It reports what it summed and over how far, rather than
  // calling it the line's total (#1516).
  //
  // This is not a dead branch waiting for old data: the field arrives with a
  // publish, and a phone reads whatever release it downloaded. A build that
  // ships before the exporter's next production run sees no `length_miles` on
  // any line, and a source that publishes none would land here permanently.
  if (typeof published !== 'number' || !Number.isFinite(published) || published <= 0) {
    return {
      kind: 'unverified',
      gainFt: Math.round(gainFt),
      lossFt: Math.round(lossFt),
      miles: heldMiles,
    }
  }

  if (heldMiles < published * (1 - COVERAGE_TOLERANCE)) {
    return { kind: 'partial', heldMiles, publishedMiles: published }
  }

  // Rounded here rather than at the sheet, and to whole feet, because whole
  // feet is the precision the artifact carries: export_network_elevation.py
  // publishes `round(gain)`, so a decimal anywhere downstream would be
  // invented.
  return {
    kind: 'measured',
    gainFt: Math.round(gainFt),
    lossFt: Math.round(lossFt),
    miles: heldMiles,
  }
}
