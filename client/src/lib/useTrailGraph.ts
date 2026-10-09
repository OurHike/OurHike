// The junction graph a phone holds, cell by cell (#1257 stage 3).
//
// WHAT THIS DECIDES, AND WHAT IT LEAVES TO THE SHELL
//
// The shell knows WHERE a day hike could be wanted - the hike lib/plannedHike.ts
// stores, the fix, the camera once it is past the seam, and every tap in the
// builder - and hands the cells under those in as `wanted`. This hook turns
// that into a graph: it loads each wanted cell's routing shard once
// (lib/trailGraphData.ts), merges shards append-only so a draft's edge indices
// survive a cell landing mid-build, and rebuilds the index each time the
// merged graph grows. A cell wanted while a phone has no signal is read from
// the store, which is what makes a hike planned at home route at the
// trailhead.
//
// THE DOOR ANSWERS FROM THE INDEX, NOT FROM A LOAD. `trailNetwork` - what
// chrome/PlanKindSheet.tsx says - is decided by whether this release publishes
// a cell index at all and whether it has any cells, which is the question "can
// a day hike be built" actually is now that no single file holds the network.
// The whole graph used to answer it by arriving: 78,595,556 bytes on
// 2026-09-07, parsed on the main thread, and the door opened when the parse
// finished. The index is 166,721 bytes on the same data.
//
// WHAT A CELL THAT WILL NOT LOAD LOOKS LIKE. The door is already open; a tap
// in that cell is refused with lib/dayHikeDraft.ts's "hasn't got this area's
// trail lines yet", and the cell is asked again on the next reconnection or
// retry. That sentence collapses "still arriving" with "never coming" for one
// cell, exactly as dayHikeDraft.ts records it already does for the geometry
// half, and the console says which - a per-cell reason on the door is a
// change to what a screen SAYS, which wants its own before-and-after.
//
// ONE RELEASE PER SESSION'S GRAPH (#1828 - a phone merges trail-graph cells
// from two releases by node number, and a new release renumbers them). The
// first cell to merge decides
// which release this session's graph is - the manifest's with signal, the
// newest this phone stored without (lib/trailGraphData.ts's header has the
// rule and the maintainer's choice behind it) - and every later cell is asked
// for that release. A cell this phone holds only from another release is
// treated as not held, and the console says so once. A cell that arrives
// from another release - signal came back, and the manifest's release is not
// the one the graph was built from - is left out until the app restarts,
// because a live draft holds positions in this graph and a graph rebuilt
// from the other release would move every one of them. Both look, to a
// hiker, like any cell that has not arrived: the same "hasn't got this
// area's trail lines yet".

import { useEffect, useMemo, useRef, useState } from 'react'
import { DATA_CONFIGURED } from './config'
import type { CellIndex, CoverageCell } from './coverageCells'
import { buildGraphIndex, type TrailGraphIndex } from './trailGraph'
import {
  emptyMergedGraph,
  isSettledAbsence,
  loadGraphShard,
  mergeGraphShard,
  sameRelease,
  type GraphRelease,
  type MergedGraph,
  type TrailNetworkAbsence,
  type TrailNetworkState,
} from './trailGraphData'
import { forgetWholeGraph, newestStoredGraphVersion } from './trailGraphStore'

export interface TrailGraphInputs {
  online: boolean
  /** #1117's gate: with signal, nothing here is fetched until the trail line's
   *  own launch fetch has settled. Offline the store read competes with
   *  nothing and is never gated. */
  gate: boolean
  /** The graph's cell index (lib/coverageCells.ts's GRAPH_CELLS), and whether
   *  it has answered - `useCellIndexState`'s three facts. */
  cellIndex: CellIndex | null
  cellIndexSettled: boolean
  cellIndexUnreachable: boolean
  /** The cells the shell wants routable, from the index above. Order is
   *  immaterial; the set is what is compared. */
  wanted: readonly CoverageCell[]
  /** The door's "Try again" count, owned by the shell because the index
   *  hook re-asks on it too: each bump forgives every cell the bucket
   *  refused, so the next run asks for them again. */
  attempt: number
}

export interface TrailGraphHook {
  /** The merged, indexed graph of every cell loaded so far, or null before
   *  the first lands. Consumers that route read this. */
  graphIndex: TrailGraphIndex | null
  /** The same graph with the bookkeeping the companions align by. */
  graphMerged: MergedGraph | null
  /** What to SAY about the graph, as against whether there is one. */
  trailNetwork: TrailNetworkState
}

/** The identity of a set of cells, for the effect that loads them. */
function namesKey(cells: readonly CoverageCell[]): string {
  return [...new Set(cells.map((cell) => cell.name))].sort().join(' ')
}

/** A release as the console names it. */
function releaseName(release: GraphRelease): string {
  return release.version ?? 'a release that named no version'
}

export function useTrailGraph({
  online,
  gate,
  cellIndex,
  cellIndexSettled,
  cellIndexUnreachable,
  wanted,
  attempt,
}: TrailGraphInputs): TrailGraphHook {
  const [merged, setMerged] = useState<MergedGraph | null>(null)
  /** Cells whose shard is merged, or is on its way. */
  const asked = useRef(new Set<string>())
  /** Cells whose shard has merged - what a cancelled run may not un-ask. */
  const landed = useRef(new Set<string>())
  /** Cells whose shard the bucket answered about, and the answer was settled:
   *  not asked again until a retry, which is the rule isSettledAbsence
   *  carries for the whole graph. */
  const settled = useRef(new Map<string, TrailNetworkAbsence>())
  /** The release this session's graph is built from, once a cell has merged
   *  (#1828). Never changes after that - see the header. */
  const building = useRef<GraphRelease | null>(null)
  /** Cells that arrived from another release than `building`, by the release
   *  they came from. Not asked again this session, retry included: asking
   *  cannot change which release the graph is. */
  const otherRelease = useRef(new Map<string, GraphRelease>())
  /** Cells the console has already been told this phone holds from another
   *  release - said once, not on every re-ask. */
  const heldElsewhereSaid = useRef(new Set<string>())

  // The whole-file copies earlier releases stored, deleted once per launch -
  // lib/trailGraphStore.ts says what they cost.
  useEffect(() => {
    void forgetWholeGraph()
  }, [])

  // A retry forgives every settled refusal: the bucket may have been
  // republished, and the door's control promises a fresh ask.
  useEffect(() => {
    settled.current.clear()
  }, [attempt])

  const wantedKey = namesKey(wanted)
  useEffect(() => {
    if (!DATA_CONFIGURED || cellIndex === null) return
    if (online && !gate) return
    const missing = wanted.filter(
      (cell, position, all) =>
        !asked.current.has(cell.name) &&
        !settled.current.has(cell.name) &&
        !otherRelease.current.has(cell.name) &&
        all.findIndex((other) => other.name === cell.name) === position,
    )
    if (missing.length === 0) return

    const controller = new AbortController()
    let live = true
    const askedCells = asked.current
    const landedCells = landed.current
    for (const cell of missing) askedCells.add(cell.name)

    void (async () => {
      // NEWEST WINS, until something has merged (#1828). Of the cells this
      // run asks for, the release this phone stored one from most recently
      // is the one a stored copy must be from; once a cell has merged, its
      // release is. Read across these cells and not the whole store -
      // lib/trailGraphStore.ts's newestStoredGraphVersion says why.
      const newest =
        building.current === null
          ? await newestStoredGraphVersion(missing.map((cell) => cell.name))
          : null
      if (!live) return
      // One at a time rather than all at once: the densest cell is 12.7 MB of
      // JSON, and a phone parsing four of those together is the frozen page
      // this whole cut exists to prevent, one artifact further down.
      for (const cell of missing) {
        const load = await loadGraphShard(
          cell,
          controller.signal,
          online,
          building.current ?? newest ?? undefined,
        )
        if (!live) return
        if (load.kind === 'shard') {
          const graphRelease = building.current
          if (graphRelease !== null && !sameRelease(graphRelease, load.release)) {
            // Signal came back, and the manifest's release is not the one
            // this session's graph was built from. Joining would invent
            // junctions (#1828); swapping the graph would move a live
            // draft's taps. Left out until the app restarts.
            askedCells.delete(cell.name)
            otherRelease.current.set(cell.name, load.release)
            console.warn(
              `Junction graph cell ${cell.name} arrived from release ${releaseName(load.release)}, and this session's graph is ${releaseName(graphRelease)}: left out until the app restarts (lib/useTrailGraph.ts)`,
            )
            continue
          }
          building.current = load.release
          landedCells.add(cell.name)
          setMerged((current) =>
            mergeGraphShard(
              current ?? emptyMergedGraph(),
              cell.name,
              load.shard,
              load.release,
            ),
          )
          continue
        }
        askedCells.delete(cell.name)
        if (load.heldRelease !== undefined && !heldElsewhereSaid.current.has(cell.name)) {
          heldElsewhereSaid.current.add(cell.name)
          console.warn(
            `Junction graph cell ${cell.name} is held from release ${releaseName(load.heldRelease)}, not the one this graph is built from: not used, and fetched again with signal (lib/useTrailGraph.ts)`,
          )
        }
        if (isSettledAbsence(load.because)) {
          settled.current.set(cell.name, load.because)
          console.warn(
            `Junction graph cell ${cell.name} is not being used: ${load.because} (lib/useTrailGraph.ts)`,
          )
        }
      }
    })()

    return () => {
      live = false
      controller.abort()
      // What did not land is asked for again by the next run of this effect.
      for (const cell of missing) {
        if (!landedCells.has(cell.name)) askedCells.delete(cell.name)
      }
    }
    // `wanted` is read through `wantedKey`, which is its identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online, gate, cellIndex, wantedKey, attempt])

  const graphIndex = useMemo(
    () =>
      merged === null || merged.graph.edges.length === 0
        ? null
        : buildGraphIndex(merged.graph),
    [merged],
  )

  /**
   * What to SAY about the graph, from the index alone (see the header).
   *
   * Memoised on the facts it is built from rather than rebuilt per render: it
   * is a prop, and a fresh object every render is a re-render for whatever
   * holds it.
   */
  const trailNetwork = useMemo<TrailNetworkState>(() => {
    if (!DATA_CONFIGURED) return { kind: 'absent', because: 'unconfigured' }
    if (!cellIndexSettled) return { kind: 'looking' }
    if (cellIndex === null) {
      return {
        kind: 'absent',
        because: cellIndexUnreachable ? 'unreachable' : 'not-in-release',
      }
    }
    // A VALID INDEX IS NOT THE SAME AS A ROUTABLE ONE (#1044 review): an
    // index with no cells is a real published state - a ring with no
    // maintained trail in it - and treating it as "ready" would open the
    // door onto a builder that could answer no tap.
    if (cellIndex.cells.length === 0) return { kind: 'absent', because: 'empty' }
    return { kind: 'ready' }
  }, [cellIndex, cellIndexSettled, cellIndexUnreachable])

  return { graphIndex, graphMerged: merged, trailNetwork }
}
