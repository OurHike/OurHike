// Places waypoints into the map screen's three lanes and collapses the ones
// that would overlap (WIREFRAMES.md §1.4).
//
// The clustering threshold is in PERCENT of the visible window, not miles,
// because the problem it solves is a rendering one: at a 10-mile window four
// springs a tenth of a mile apart are legible, and at a 100-mile window the
// same four are a single illegible smear. What matters is how far apart they
// land on screen, which is exactly what a percentage measures.

export interface Waypoint {
  id: string
  type: string
  mile: number
}

export interface LaneDefinition {
  id: 'water' | 'sleep' | 'else'
  label: string
}

export const LANES: LaneDefinition[] = [
  { id: 'water', label: 'WATER' },
  { id: 'sleep', label: 'SLEEP' },
  { id: 'else', label: 'ELSE' },
]

export type LaneId = LaneDefinition['id']

/** Roughly one pin width - closer than this and the glyphs overlap. */
export const COLLAPSE_THRESHOLD_PCT = 1.5

const SLEEP_TYPES = new Set(['shelter', 'campsite'])

export function laneFor(type: string): LaneId {
  if (type === 'water') return 'water'
  if (SLEEP_TYPES.has(type)) return 'sleep'
  // Anything unrecognised lands in ELSE rather than vanishing. A type
  // introduced by a later import should still be visible on the ribbon, even
  // before it has a lane of its own.
  return 'else'
}

export interface WaypointCluster {
  positionPct: number
  count: number
  members: Waypoint[]
  /** The type of the first member - what the pill's glyph shows. */
  type: string
}

export interface MileWindow {
  startMile: number
  endMile: number
}

export type LaneClusters = Record<LaneId, WaypointCluster[]>

function clusterOne(members: Waypoint[], positions: number[]): WaypointCluster {
  return {
    // A pill sits at the midpoint of what it swallowed, so it stays visually
    // anchored to the group rather than to whichever member happened to be
    // first.
    positionPct: (positions[0] + positions[positions.length - 1]) / 2,
    count: members.length,
    members,
    type: members[0].type,
  }
}

export function clusterWaypoints(
  waypoints: Waypoint[],
  { startMile, endMile }: MileWindow,
): LaneClusters {
  const span = endMile - startMile
  const lanes: LaneClusters = { water: [], sleep: [], else: [] }

  for (const lane of LANES) {
    const inLane = waypoints
      .filter((w) => laneFor(w.type) === lane.id)
      .filter((w) => w.mile >= startMile && w.mile <= endMile)
      .sort((a, b) => a.mile - b.mile)

    let members: Waypoint[] = []
    let positions: number[] = []

    for (const waypoint of inLane) {
      const positionPct = span === 0 ? 0 : ((waypoint.mile - startMile) / span) * 100

      // Compare against the cluster's last member, not its first, so a long
      // chain of individually-close points collapses as one run.
      const isNear =
        positions.length > 0 &&
        positionPct - positions[positions.length - 1] <= COLLAPSE_THRESHOLD_PCT

      if (!isNear && members.length > 0) {
        lanes[lane.id].push(clusterOne(members, positions))
        members = []
        positions = []
      }

      members.push(waypoint)
      positions.push(positionPct)
    }

    if (members.length > 0) lanes[lane.id].push(clusterOne(members, positions))
  }

  return lanes
}
