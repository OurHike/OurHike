import { describe, expect, it } from 'vitest'
import { createExpression } from '@maplibre/maplibre-gl-style-spec'
import type { MapPoint } from '../lib/legendContents'
import {
  BASE_PADDING_PX,
  CROWDED_NEIGHBOURS,
  CROWDED_PADDING_PX,
  CROWDING_PROPERTY,
  CROWDING_RADIUS_M,
  POI_ICON_PADDING_EXPRESSION,
  QUIET_NEIGHBOURS,
  crowdingByPoi,
} from './poiCrowding'

/** The padding MapLibre would actually compute, rather than the shape of the
 *  array we handed it - the same evaluation poiLayers.test.ts uses. */
function paddingFor(properties: Record<string, unknown>, zoom = 12): number {
  const compiled = createExpression(
    POI_ICON_PADDING_EXPRESSION,
    'layers[0].layout.icon-padding',
  )
  if (compiled.result === 'error') {
    throw new Error(compiled.value.map((e) => e.message).join('; '))
  }
  return compiled.value.evaluate({ zoom }, { properties, type: 'Point' } as never)
}

/** A waypoint `metresNorth` up from a fixed point in Brooklyn. */
function at(
  metresEast: number,
  metresNorth: number,
  id = `${metresEast},${metresNorth}`,
) {
  const lat = 40.6932 + metresNorth / 111_320
  const lon = -73.9715 + metresEast / (111_320 * Math.cos((40.6932 * Math.PI) / 180))
  return { id, type: 'water', lat, lon, confidence: 'high' } as MapPoint
}

describe('the padding ramp', () => {
  it('pads a waypoint on the emptiest possible ground exactly as the map does today', () => {
    expect(paddingFor({ [CROWDING_PROPERTY]: 0 })).toBe(BASE_PADDING_PX)
  })

  it('still pads at the base at the anchor itself, which is where the A.T. sits', () => {
    // THE SAFETY ASSERTION OF THIS WHOLE FEATURE. Every one of the 563
    // waypoints ATC publishes on the Appalachian Trail measures 5 neighbours
    // or fewer, so all of them land under QUIET_NEIGHBOURS and are padded
    // exactly as they are today. Asserted AT the anchor rather than at 5,
    // because the anchor is the edge that has to hold.
    expect(paddingFor({ [CROWDING_PROPERTY]: QUIET_NEIGHBOURS })).toBe(BASE_PADDING_PX)
  })

  it('leaves room above the busiest ground ATC publishes, so the trail is not on the edge of the ramp', () => {
    // Measured 2026-09-17: the A.T.'s own maximum is 5. If somebody lowers
    // QUIET_NEIGHBOURS to 4 the trail starts paying for a city's problem, and
    // every other test here would still pass.
    expect(QUIET_NEIGHBOURS).toBeGreaterThan(5)
    expect(paddingFor({ [CROWDING_PROPERTY]: 5 })).toBe(BASE_PADDING_PX)
  })

  it('gives the full allowance at twice the busiest place on the A.T., and no more above it', () => {
    expect(paddingFor({ [CROWDING_PROPERTY]: CROWDED_NEIGHBOURS })).toBe(
      CROWDED_PADDING_PX,
    )
    expect(paddingFor({ [CROWDING_PROPERTY]: CROWDED_NEIGHBOURS * 10 })).toBe(
      CROWDED_PADDING_PX,
    )
  })

  it('ramps rather than steps, so ground that is only somewhat crowded gets only some air', () => {
    const midpoint = (QUIET_NEIGHBOURS + CROWDED_NEIGHBOURS) / 2
    const padding = paddingFor({ [CROWDING_PROPERTY]: midpoint })
    expect(padding).toBeGreaterThan(BASE_PADDING_PX)
    expect(padding).toBeLessThan(CROWDED_PADDING_PX)
    expect(padding).toBeCloseTo((BASE_PADDING_PX + CROWDED_PADDING_PX) / 2, 5)
  })

  it('pads a feature with no crowding property as though it were quiet, not as though it were empty', () => {
    // Both happen to be BASE_PADDING_PX today, so this asserts the coalesce
    // TARGET rather than the number: a ramp whose low end later moved would
    // otherwise silently change what an older feature gets.
    expect(paddingFor({})).toBe(paddingFor({ [CROWDING_PROPERTY]: QUIET_NEIGHBOURS }))
  })

  it('does not vary with zoom, because crowding is a fact about the ground', () => {
    const properties = { [CROWDING_PROPERTY]: CROWDED_NEIGHBOURS }
    expect(paddingFor(properties, 9)).toBe(paddingFor(properties, 16))
  })
})

describe('counting the neighbours', () => {
  it('does not count a waypoint as its own neighbour', () => {
    expect(crowdingByPoi([at(0, 0, 'alone')]).get('alone')).toBe(0)
  })

  it('counts a waypoint just inside the radius and not one just outside', () => {
    const inside = crowdingByPoi([at(0, 0, 'centre'), at(0, CROWDING_RADIUS_M - 10)])
    expect(inside.get('centre')).toBe(1)

    const outside = crowdingByPoi([at(0, 0, 'centre'), at(0, CROWDING_RADIUS_M + 10)])
    expect(outside.get('centre')).toBe(0)
  })

  it('finds a neighbour that sits in the next bucket along', () => {
    // The bug a bucketed count is born with. Cells are the radius wide, so two
    // marks 100 m apart can still land either side of a cell boundary - and a
    // pass that only read its own cell would report both as alone. Walked
    // across a whole cell in 50 m steps so the pair straddles a boundary
    // wherever the grid's origin happens to fall.
    for (let offset = 0; offset < CROWDING_RADIUS_M; offset += 50) {
      const counts = crowdingByPoi([at(offset, 0, 'a'), at(offset + 100, 0, 'b')])
      expect(counts.get('a'), `at ${offset} m east`).toBe(1)
      expect(counts.get('b'), `at ${offset} m east`).toBe(1)
    }
  })

  it('finds a neighbour diagonally across a bucket corner', () => {
    // The nine-cell read has to include the four diagonals, not just the four
    // sides: two marks 400 m apart on both axes are 566 m apart, inside the
    // radius, and can sit in cells that touch only at a corner.
    for (let offset = 0; offset < CROWDING_RADIUS_M; offset += 50) {
      const counts = crowdingByPoi([
        at(offset, offset, 'a'),
        at(offset + 400, offset + 400, 'b'),
      ])
      expect(counts.get('a'), `at ${offset} m`).toBe(1)
    }
  })

  it('reports New York City as crowded and the same number of waypoints strung out along a trail as quiet', () => {
    // The two shapes this has to tell apart, in miniature. Twelve fountains
    // around one park all see each other; twelve shelters a mile apart, which
    // is tighter than the A.T. actually is, see nobody.
    const park = Array.from({ length: 12 }, (_, i) =>
      at((i % 4) * 150, Math.floor(i / 4) * 150, `park-${i}`),
    )
    const trail = Array.from({ length: 12 }, (_, i) => at(0, i * 1609, `trail-${i}`))

    const parkCounts = crowdingByPoi(park)
    expect(Math.max(...parkCounts.values())).toBeGreaterThanOrEqual(
      CROWDED_NEIGHBOURS / 2,
    )

    const trailCounts = crowdingByPoi(trail)
    expect(Math.max(...trailCounts.values())).toBeLessThanOrEqual(QUIET_NEIGHBOURS)
  })

  it('answers for every waypoint it was given, so the layer never reads a missing count', () => {
    const points = [at(0, 0, 'a'), at(500, 0, 'b'), at(90_000, 0, 'far')]
    const counts = crowdingByPoi(points)
    expect([...counts.keys()].sort()).toEqual(['a', 'b', 'far'])
    expect(counts.get('far')).toBe(0)
  })

  it('counts the same either side of the corridor, where a degree of longitude is 18% narrower', () => {
    // Cells are sized by the latitude degree on both axes, which makes them
    // too WIDE in longitude rather than too narrow - too wide costs a few
    // distance checks, too narrow misses a neighbour. Georgia and Maine are
    // the two ends that would disagree if the sizing went the other way.
    const pairAt = (lat: number) => [
      { id: 'a', type: 'water', lat, lon: -80, confidence: 'high' } as MapPoint,
      {
        id: 'b',
        type: 'water',
        lat,
        lon: -80 + 700 / (111_320 * Math.cos((lat * Math.PI) / 180)),
        confidence: 'high',
      } as MapPoint,
    ]
    expect(crowdingByPoi(pairAt(34.6)).get('a')).toBe(1)
    expect(crowdingByPoi(pairAt(45.9)).get('a')).toBe(1)
  })
})

describe('the cost of counting', () => {
  it('stays fast at the scale of the whole published map, so a legend tap does not stall', () => {
    // poiFeatureCollection rebuilds on every legend tap and every hourly
    // conditions refresh, and this pass now rides that rebuild. The published
    // map is about 8,400 default-visible marks; an all-pairs version of this
    // would be 70 million distance checks and would be felt on a phone.
    //
    // Measured against the real artifact (release 2026-09-16-4, 8,379 marks):
    // 18 ms best of five in this environment. The bound here is an order of
    // magnitude above that, because a CI runner under load is not a
    // benchmark - what it is really asserting is that the bucketing is still
    // there, which a quadratic rewrite would blow past by a factor of 50.
    const marks: MapPoint[] = []
    // Half strung out along a line, half packed into city-scale clusters, so
    // a change that is fast only on sparse data does not pass.
    for (let i = 0; i < 4200; i += 1) marks.push(at(0, i * 500, `line-${i}`))
    for (let cluster = 0; cluster < 42; cluster += 1) {
      for (let i = 0; i < 100; i += 1) {
        marks.push(
          at(
            cluster * 3000 + (i % 10) * 70,
            Math.floor(i / 10) * 70,
            `city-${cluster}-${i}`,
          ),
        )
      }
    }

    const started = performance.now()
    const counts = crowdingByPoi(marks)
    const elapsed = performance.now() - started

    expect(counts.size).toBe(marks.length)
    expect(elapsed).toBeLessThan(2000)
  })
})
