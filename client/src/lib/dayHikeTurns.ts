// The turns along a day hike, and every other trail at each junction it
// passes (#1041, frames `D9` and `D10`).
//
// THE NAMING QUESTION THIS ANSWERS, WHICH #934 LEFT OPEN
//
// features/HIKE_PLANNING.md records the turn list as blocked, and names the
// blocker precisely: frame `1l`'s vocabulary is junction-relative throughout -
// "mi 2.1 Right onto Seven Hills (blue) at the Pine Meadow junction" - and a
// leg that starts mid-segment has no such phrase available for its first
// line, because #934's answer splits the segment rather than snapping to a
// junction.
//
// Frame `D10` answers it by not naming the junction at all. It names the ARMS:
//
//   Turn left · Seven Hills Trail, blue blazes
//   Straight on is Pine Meadow Tr, red - not your route
//   Back right is Reeves Meadow, white - the way you came
//
// Every one of those is an edge attribute the published graph already
// carries, and the mid-segment first leg stops being a problem because THE
// START OF A WALK IS NOT A TURN - it never appears in this list. What a hiker
// checks against the blaze in front of them is the trail's own name and
// colour, not a junction's name, which is the thing they cannot see from
// where they are standing.
//
// A TURN IS EXACTLY A LEG BOUNDARY, and that is by construction rather than
// by coincidence: the test below is `sameTrail`, the same predicate
// lib/trailGraph.ts's leg grouping uses. So a hike with three legs in a
// segment has two turns in it, and the header's "leg 2 of 3" and this list
// cannot disagree about where Pine Meadow becomes Seven Hills.
//
// WHAT IS NOT HERE, AND WHY
//
// Frame `D10` also writes "The next blaze is about 80 ft along, on the left."
// Nothing in this repository knows where a blaze is painted - not the graph,
// not the pipeline, not any source - so that sentence is dropped rather than
// approximated. chrome/TurnCard.tsx prints the advice the app CAN stand
// behind ("if you don't see blue within a few minutes, you took the wrong
// one"), which is a rule of thumb rather than a measurement and reads as one.

import { dayHikeWalk } from './dayHikeWalk'
import type { ResolvedDayHike } from './dayHikeCard'
import {
  bearingDegrees,
  metresToMiles,
  sameTrail,
  type LonLat,
  type TrailGraphIndex,
} from './trailGraph'

/**
 * How far along an arm the bearing is read, in metres.
 *
 * @unvalidated Picked. The two vertices either side of a junction can be a
 * metre apart in the published geometry, where the bearing between them is
 * digitising noise rather than the direction a trail leaves in; 20 m is far
 * enough for a direction to exist and near enough to still be the junction a
 * hiker is standing at. What would settle it: reading the side this module
 * computes against the side a person standing at a sample of real Harriman
 * junctions reports, and finding the smallest distance at which the two stop
 * disagreeing.
 */
const ARM_SAMPLE_M = 20

/**
 * The cone either side of straight ahead that is called "straight on", and
 * the cone behind that is called "back".
 *
 * @unvalidated Both picked. They divide a circle into four readings and
 * nobody has checked them against what a hiker would say standing at a real
 * fork - a 35 degrees bend reads as "bear left" to most people and as
 * "straight on" here. What would settle it is the same instrument as
 * ARM_SAMPLE_M above. Erring wide on "straight" is the deliberate direction:
 * "turn left" at a junction that is really a gentle bend sends somebody
 * looking for a fork that is not there.
 */
const STRAIGHT_MAX_DEG = 30
const BACK_MIN_DEG = 150

/** Which way an arm leaves a junction, read from where the hiker is facing. */
export type TurnSide = 'left' | 'right' | 'straight' | 'back'

/** One trail leaving a junction - what the card names and what a hiker
 *  compares against the blaze in front of them. */
export interface TurnArm {
  name: string | null
  blaze_color: string | null
  source: string | null
  /**
   * Which way it goes, or null when this phone's graph cannot say.
   *
   * Null happens for a real reason and is not a degraded number to fill in: an
   * edge published before `trail_graph_geometry.json` existed carries no
   * vertices, and the chord between its two junctions can point the opposite
   * way to the trail across a switchback. "Turn right" for a left-hand fork is
   * the confidently-wrong answer CLAUDE.md's four-ways section rules out, so
   * the side is withheld and the card names the trail without it.
   */
  side: TurnSide | null
  /** Degrees clockwise from north, or null on the same terms as `side`.
   *  Carried so chrome/JunctionDiagram.tsx can draw the arms at the angles
   *  they really leave at rather than at four cardinal stubs. */
  bearingDeg: number | null
}

export interface DayHikeTurn {
  /** Walked-trail miles from the hike's first step to this junction - the
   *  distance a hiker has actually covered when they arrive, which is what
   *  pair-wise accumulation gets right (lib/dayHikeWalk.ts). */
  miles: number
  /** The arm the route takes. */
  onto: TurnArm
  /** The arm the hiker arrives on - the way they came. */
  from: TurnArm
  /**
   * Every other trail at this junction, in no promised order.
   *
   * NOT collapsed by trail identity, unlike the finished card's ways-off rows.
   * A trail CROSSING a junction contributes an arm on each side, and to
   * somebody standing there those are two different directions with the same
   * name on both - which is exactly the confusion this card exists to settle.
   * The card says what each one is and that it is not the route.
   */
  others: TurnArm[]
}

/** The junction's own coordinate, so a caller can frame it. */
export interface DayHikeTurnPlace {
  turn: DayHikeTurn
  at: LonLat
}

/**
 * Every place along the walk where the route leaves one trail for another, in
 * walking order.
 *
 * Empty for a walk that never changes trail, which is a real answer rather
 * than a missing one - plenty of Harriman loops are a single blazed circuit -
 * and chrome/NextTurnCard.tsx says so instead of leaving the slot blank.
 */
export function dayHikeTurns(
  index: TrailGraphIndex,
  resolved: ResolvedDayHike,
): DayHikeTurn[] {
  return dayHikeTurnPlaces(index, resolved).map((place) => place.turn)
}

/** The turns, each with the junction's coordinate. */
export function dayHikeTurnPlaces(
  index: TrailGraphIndex,
  resolved: ResolvedDayHike,
): DayHikeTurnPlace[] {
  const graph = index.graph
  const steps = dayHikeWalk(index, resolved)
  const out: DayHikeTurnPlace[] = []

  for (let i = 0; i + 1 < steps.length; i += 1) {
    const step = steps[i]
    const next = steps[i + 1]
    const junction = step.junctionNode
    // No junction means the traversal ended at a tap, and a tap is not a
    // place with a choice at it. A segment boundary is not a turn either -
    // #935's deliberate gap is ground this app has no route across, so
    // "turn left" over it would be an instruction to walk somewhere nobody
    // mapped.
    if (junction === null || next.segment !== step.segment) continue

    const arriving = graph.edges[step.edgeIndex]
    const taking = graph.edges[next.edgeIndex]
    if (sameTrail(arriving, taking)) continue

    // Where the hiker is FACING as they arrive: the reverse of the bearing
    // the arm they came in on leaves this junction by.
    const backwards = armBearing(index, step.edgeIndex, junction)
    const facing = backwards === null ? null : (backwards + 180) % 360
    const armOf = (edgeIndex: number): TurnArm => {
      const bearing = armBearing(index, edgeIndex, junction)
      const edge = graph.edges[edgeIndex]
      return {
        name: edge.name,
        blaze_color: edge.blaze_color,
        source: edge.source,
        bearingDeg: bearing,
        side: facing === null || bearing === null ? null : sideOf(facing, bearing),
      }
    }

    const others: TurnArm[] = []
    for (const neighbour of index.adjacency[junction] ?? []) {
      if (neighbour.edgeIndex === step.edgeIndex) continue
      if (neighbour.edgeIndex === next.edgeIndex) continue
      others.push(armOf(neighbour.edgeIndex))
    }

    const node = graph.nodes[junction]
    out.push({
      turn: {
        miles: metresToMiles(step.beforeMetres + step.metres),
        onto: armOf(next.edgeIndex),
        from: armOf(step.edgeIndex),
        others,
      },
      at: { lon: node[0], lat: node[1] },
    })
  }

  return out
}

/** The turn a hiker is walking toward, and how far off it is. */
export interface NextTurn {
  turn: DayHikeTurn
  milesAway: number
}

/**
 * The first turn still ahead of a hiker, or null once they are past the last
 * one.
 *
 * Null is the state of most of a loop's final leg and the card prints it
 * rather than hiding: "no more turns" is a thing worth knowing on a trail
 * with a junction every 1.2 miles (NEARBY_TRAILS.md, measured by #771).
 */
export function nextTurn(
  turns: readonly DayHikeTurn[],
  walkedMi: number,
): NextTurn | null {
  for (const turn of turns) {
    if (turn.miles > walkedMi) return { turn, milesAway: turn.miles - walkedMi }
  }
  return null
}

/**
 * How close a hiker has to be for the screen to say they are AT the junction
 * rather than walking toward it.
 *
 * @unvalidated Picked. ~264 ft, which is roughly where a fork stops being
 * something ahead and starts being something you are standing in - but that
 * is a guess about eyesight and tree cover, not a measurement, and it is
 * also within the GPS error this whole surface lives inside. What would
 * settle it: the distance at which a hiker at a sample of real Harriman
 * junctions says they can see the fork.
 */
export const AT_JUNCTION_MILES = 0.05

/** Whether the hiker has arrived at the next turn, for the header's own
 *  reading of the mode ("day hike · at a junction"). */
export function atJunction(next: NextTurn | null): boolean {
  return next !== null && next.milesAway <= AT_JUNCTION_MILES
}

/**
 * The bearing a trail leaves a junction on, or null when this phone's graph
 * cannot say (see {@link TurnArm.side}).
 *
 * Read over the first {@link ARM_SAMPLE_M} metres of the edge's OWN vertices
 * rather than between the first two of them, because those two can be a metre
 * apart and the angle between them is then a picture of the digitiser's hand.
 */
function armBearing(
  index: TrailGraphIndex,
  edgeIndex: number,
  node: number,
): number | null {
  const edge = index.graph.edges[edgeIndex]
  if (edge === undefined) return null
  if (edge.geometry === undefined || edge.geometry.length < 2) return null
  // A self-loop leaves the same node twice and there is no "the" direction it
  // goes in; withheld rather than guessed at.
  if (edge.from === edge.to) return null
  if (node !== edge.from && node !== edge.to) return null

  const vertices = node === edge.from ? edge.geometry : [...edge.geometry].reverse()
  const start: LonLat = { lon: vertices[0][0], lat: vertices[0][1] }
  let walked = 0
  let previous = start
  for (let step = 1; step < vertices.length; step += 1) {
    const here: LonLat = { lon: vertices[step][0], lat: vertices[step][1] }
    walked += metresBetween(previous, here)
    previous = here
    if (walked >= ARM_SAMPLE_M) return bearingDegrees(start, here)
  }
  // Shorter than the sample distance - a real thing in a graph where a
  // junction can be a few metres from the next. The whole edge is then the
  // best evidence there is, which is more than the first two vertices were.
  return walked === 0 ? null : bearingDegrees(start, previous)
}

/** Which reading an arm's bearing gets, from a hiker facing `facing`. */
function sideOf(facing: number, arm: number): TurnSide {
  // Into (-180, 180]: negative is anticlockwise, which on a compass is left.
  const delta = (((arm - facing + 540) % 360) - 180) as number
  const size = Math.abs(delta)
  if (size <= STRAIGHT_MAX_DEG) return 'straight'
  if (size >= BACK_MIN_DEG) return 'back'
  return delta > 0 ? 'right' : 'left'
}

const EARTH_RADIUS_M = 6_378_137

/** Equirectangular metres between two points, for ARM_SAMPLE_M's tally only.
 *  Same projection lib/trailGraph.ts measures with, over the same tens of
 *  metres, for the reason its own note gives. */
function metresBetween(from: LonLat, to: LonLat): number {
  const meanLatitude = ((from.lat + to.lat) / 2) * (Math.PI / 180)
  const x =
    (to.lon - from.lon) * (Math.PI / 180) * EARTH_RADIUS_M * Math.cos(meanLatitude)
  const y = (to.lat - from.lat) * (Math.PI / 180) * EARTH_RADIUS_M
  return Math.hypot(x, y)
}
