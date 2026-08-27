// Tests for lib/dayHikeTurns.ts - the junctions along a followed day hike
// (#1041, frames `D9` and `D10`).
//
// THE ASYMMETRY THIS SUITE PINS. A turn withheld costs a hiker a glance at
// the blazes they should be reading anyway. A turn INVENTED - a side guessed
// from a chord, a junction reported where the trail simply continues - sends
// somebody down the wrong arm of a fork at the one moment they are trusting
// the screen instead of the tree. So several tests below assert that a side
// comes back NULL or that a junction produces NO turn, and a change that
// makes them pass by returning something is not an improvement.

import { describe, expect, it } from 'vitest'

import { resolveDayHike } from './dayHikeCard'
import { AT_JUNCTION_MILES, atJunction, dayHikeTurns, nextTurn } from './dayHikeTurns'
import {
  EAST_END,
  NETWORK,
  NETWORK_WITHOUT_GEOMETRY,
  NORTH_END,
  WEST_END,
  hikeThrough,
} from './dayHikeWalk.fixtures'
import { buildGraphIndex, metresToMiles, type TrailGraph } from './trailGraph'

function turnsFor(graph: TrailGraph, hike = hikeThrough([WEST_END, NORTH_END])) {
  const index = buildGraphIndex(graph)
  const resolved = resolveDayHike(index, hike)
  expect(resolved).not.toBeNull()
  return dayHikeTurns(index, resolved!)
}

describe('dayHikeTurns', () => {
  it('names the arm taken, the arm arrived on, and every other arm', () => {
    const turns = turnsFor(NETWORK)

    expect(turns).toHaveLength(1)
    expect(turns[0].onto.name).toBe('Seven Hills Trail')
    expect(turns[0].from.name).toBe('Pine Meadow Trail')
    // Both remaining arms, uncollapsed: Pine Meadow carrying straight on and
    // Reeves Meadow leaving south. A hiker standing here can see three trails
    // that are not theirs and the card has to account for all of them.
    expect(turns[0].others.map((arm) => arm.name).sort()).toEqual([
      'Pine Meadow Trail',
      'Reeves Meadow Trail',
    ])
  })

  it('reads each side from the direction the hiker is walking', () => {
    const turns = turnsFor(NETWORK)
    const arms = Object.fromEntries(turns[0].others.map((arm) => [arm.name, arm.side]))

    // Walking east, Seven Hills leaves north: a left turn. The rest follow
    // from the same facing, which is what makes them checkable by hand.
    expect(turns[0].onto.side).toBe('left')
    expect(arms['Pine Meadow Trail']).toBe('straight')
    expect(arms['Reeves Meadow Trail']).toBe('right')
    expect(turns[0].from.side).toBe('back')
  })

  it('prices the junction at the miles actually walked to reach it', () => {
    const turns = turnsFor(NETWORK)
    // The whole of e0 and nothing else: the tap is at its far end, so this
    // is a distance a reader can check against the fixture's own length_m.
    expect(turns[0].miles).toBeCloseTo(metresToMiles(836), 6)
  })

  it('withholds the side rather than reading it off a chord', () => {
    // Resolved against the network that HAS vertices and then asked of the
    // one that has not (#1093). The two steps have to be separated now:
    // since a tap will not snap to a geometry-less edge at all, resolving
    // the saved ends against the bare graph refuses one layer earlier and
    // this module's own withholding would never be reached to be tested.
    const resolved = resolveDayHike(
      buildGraphIndex(NETWORK),
      hikeThrough([WEST_END, NORTH_END]),
    )
    expect(resolved).not.toBeNull()
    const turns = dayHikeTurns(buildGraphIndex(NETWORK_WITHOUT_GEOMETRY), resolved!)

    // The turn is still there - which trail to take is known without any
    // vertices - and every direction is absent. Across a switchback the
    // chord between two junctions can point the opposite way to the trail,
    // and "turn right" for a left-hand fork is worse than no instruction.
    expect(turns).toHaveLength(1)
    expect(turns[0].onto.name).toBe('Seven Hills Trail')
    expect(turns[0].onto.side).toBeNull()
    expect(turns[0].onto.bearingDeg).toBeNull()
    expect(turns[0].others.every((arm) => arm.side === null)).toBe(true)
  })

  it('reports no turn where the route carries straight on down one trail', () => {
    // West end to east end: the same blazed trail through the junction, so a
    // hiker has nothing to do there. A junction is not a turn.
    expect(turnsFor(NETWORK, hikeThrough([WEST_END, EAST_END]))).toEqual([])
  })

  it('finds one turn per leg boundary, which is what the header counts', () => {
    const index = buildGraphIndex(NETWORK)
    const resolved = resolveDayHike(index, hikeThrough([WEST_END, NORTH_END]))
    expect(resolved).not.toBeNull()

    // The invariant lib/trailGraph.ts's shared `sameTrail` buys: a segment
    // with N legs has N-1 turns in it. Two lists derived two ways that
    // disagreed would put "leg 2 of 3" over a card naming the wrong trail.
    expect(dayHikeTurns(index, resolved!)).toHaveLength(resolved!.legs.length - 1)
  })
})

describe('nextTurn', () => {
  it('is the first turn still ahead, with the distance to it', () => {
    const turns = turnsFor(NETWORK)
    const next = nextTurn(turns, 0.1)

    expect(next?.turn).toBe(turns[0])
    expect(next?.milesAway).toBeCloseTo(turns[0].miles - 0.1, 6)
  })

  it('is null once every turn is behind the hiker', () => {
    const turns = turnsFor(NETWORK)
    expect(nextTurn(turns, turns[0].miles + AT_JUNCTION_MILES + 0.01)).toBeNull()
  })

  it('holds the turn while the hiker is standing in it', () => {
    // The junction must not be a boundary the state can oscillate across.
    // walkedMi is re-projected from a raw fix every second and canopy moves
    // that fix by about the 90 ft this module's sibling calls "off the
    // tread", so a hiker STANDING at the fork would otherwise watch the
    // header alternate between "at a junction" and the next leg's name, with
    // the junction card swapping to a diagram of somewhere a mile away.
    const turns = turnsFor(NETWORK)
    const past = nextTurn(turns, turns[0].miles + AT_JUNCTION_MILES / 2)

    expect(past?.turn).toBe(turns[0])
    // And it never reports a NEGATIVE distance to a junction behind you.
    expect(past?.milesAway).toBe(0)
  })

  it('is null for a walk that never changes trail', () => {
    expect(nextTurn([], 0)).toBeNull()
  })
})

describe('atJunction', () => {
  it('is true only once the hiker has arrived', () => {
    const turns = turnsFor(NETWORK)
    expect(atJunction(nextTurn(turns, turns[0].miles - 0.01))).toBe(true)
    expect(atJunction(nextTurn(turns, turns[0].miles - 0.5))).toBe(false)
    expect(atJunction(null)).toBe(false)
  })
})

describe('the bearing an arm leaves on', () => {
  it('is read at the sample distance, not at whatever vertex comes after it', () => {
    // A straight run with nothing to digitise: the first vertex past the
    // junction is most of an edge away. Returning the bearing to THAT vertex
    // makes ARM_SAMPLE_M decorative and the reading a chord across the whole
    // edge - the approximation TurnArm.side's own docstring says is withheld
    // rather than guessed.
    //
    // Seven Hills is bent here: due north for ~110 m, then hard east for the
    // rest. Sampled at 20 m the arm leaves NORTH (a left turn from an
    // eastbound hiker); read to the far vertex it would average out east,
    // which is "straight on" - the wrong instruction at a real fork.
    const bent = {
      nodes: NETWORK.nodes,
      edges: NETWORK.edges.map((edge, at) =>
        at === 2
          ? {
              ...edge,
              geometry: [
                [-74.09, 41.25],
                [-74.09, 41.251],
                [-74.06, 41.251],
                [-74.09, 41.26],
              ] as Array<[number, number]>,
            }
          : edge,
      ),
    }

    const turns = turnsFor(bent)
    expect(turns[0].onto.side).toBe('left')
    expect(turns[0].onto.bearingDeg).toBeCloseTo(0, 1)
  })
})
