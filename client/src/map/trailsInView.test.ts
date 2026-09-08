import { describe, it, expect, vi } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { attachTrailsInView, badgeFeatures, trailsInView } from './trailsInView'
import {
  BLAZE_DOTTED_LAYER_ID,
  BLAZE_LAYER_ID,
  NEARBY_BLAZE_DOTTED_LAYER_ID,
  NEARBY_BLAZE_LAYER_ID,
  TAPPABLE_BLAZE_LAYER_IDS,
} from './style'
import {
  BADGE_CHIP_PROPERTY,
  BADGE_MARK_PROPERTY,
  TRAIL_BADGE_SOURCE_ID,
  blazeChipImageId,
  trailMarkImageId,
} from './trailBadges'

// Which named trails the map is drawing, and where each through-route's
// badge sits (#1283). Driven through the mock the way drawnPois.test.ts
// drives its counts: the fixtures are what `queryRenderedFeatures` answers,
// and the assertions are what the legend and the badge source are told.

function mapWith(byLayer: Record<string, unknown[]>): MockMap {
  const map = new MockMap({
    style: {
      layers: TAPPABLE_BLAZE_LAYER_IDS.map((id) => ({ id })),
      sources: { [TRAIL_BADGE_SOURCE_ID]: {} },
    },
  })
  map.bounds = { west: -75, south: 41, east: -73, north: 42 }
  for (const [layer, features] of Object.entries(byLayer)) {
    map.renderedFeatures.set(layer, features)
  }
  return map
}

function line(
  name: string | null,
  source: string,
  coordinates: Array<[number, number]>,
  blaze: string | null = 'Blue',
  extra: Record<string, unknown> = {},
) {
  return {
    properties: { name, source, blaze_color: blaze, ...extra },
    geometry: { type: 'LineString', coordinates },
  }
}

/** The A.T. through Harriman, every vertex in view. */
const AT = line(
  'Appalachian National Scenic Trail',
  'centerline',
  [
    [-74.2, 41.2],
    [-74.1, 41.25],
    [-74.0, 41.3],
  ],
  'White',
  { id: 'centerline:chain:0' },
)

describe('trailsInView', () => {
  it('lists every named trail the blaze layers are drawing, once each', () => {
    const map = mapWith({
      [BLAZE_LAYER_ID]: [AT],
      [NEARBY_BLAZE_DOTTED_LAYER_ID]: [
        line('Long Path', 'oprhp_trails', [[-74.05, 41.22]], 'Aqua'),
        // The same trail from a second tile.
        line('Long Path', 'oprhp_trails', [[-74.04, 41.23]], 'Aqua'),
        line('Ramapo-Dunderberg Trail', 'oprhp_trails', [[-74.06, 41.21]], 'Red'),
      ],
    })

    expect(trailsInView(map as unknown as MapLibreMap).map((t) => t.name)).toEqual([
      'Appalachian National Scenic Trail',
      'Long Path',
      'Ramapo-Dunderberg Trail',
    ])
  })

  it('puts through-routes first, then the chosen system, then the rest by name', () => {
    const map = mapWith({
      [BLAZE_LAYER_ID]: [line('Zebra Spur', 'side_trails', [[-74.05, 41.22]]), AT],
      [NEARBY_BLAZE_DOTTED_LAYER_ID]: [
        line('Beech Trail', 'oprhp_trails', [[-74.06, 41.21]]),
        line('Arden-Surebridge Trail', 'oprhp_trails', [[-74.07, 41.21]]),
      ],
    })

    const trails = trailsInView(map as unknown as MapLibreMap)
    expect(trails.map((t) => [t.name, t.throughRoute, t.chosen])).toEqual([
      ['Appalachian National Scenic Trail', true, true],
      ['Zebra Spur', false, true],
      ['Arden-Surebridge Trail', false, false],
      ['Beech Trail', false, false],
    ])
  })

  it('omits an unnamed line rather than listing "Unnamed"', () => {
    const map = mapWith({
      [BLAZE_LAYER_ID]: [
        line(null, 'side_trails', [[-74.05, 41.22]]),
        line('', 'side_trails', [[-74.05, 41.22]]),
      ],
    })
    expect(trailsInView(map as unknown as MapLibreMap)).toEqual([])
  })

  it('anchors a badge on a vertex at the middle of the longest visible run', () => {
    // Three in-view vertices, evenly spaced: the middle one.
    const map = mapWith({ [BLAZE_LAYER_ID]: [AT] })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).toEqual([-74.1, 41.25])
  })

  it('ignores the part of a tile-clipped piece that runs off screen', () => {
    // Four vertices, two outside the viewport to the west: the run that
    // counts is the two inside, and the anchor is one of them.
    const map = mapWith({
      [BLAZE_LAYER_ID]: [
        line(
          'Appalachian National Scenic Trail',
          'centerline',
          [
            [-76.0, 41.2],
            [-75.5, 41.2],
            [-74.1, 41.25],
            [-74.0, 41.3],
          ],
          'White',
        ),
      ],
    })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect([
      [-74.1, 41.25],
      [-74.0, 41.3],
    ]).toContainEqual(at.anchor)
  })

  it('picks the piece that shows the most of the trail when it comes back per tile', () => {
    const map = mapWith({
      [BLAZE_LAYER_ID]: [
        line('Appalachian National Scenic Trail', 'centerline', [[-74.9, 41.9]], 'White'),
        AT,
      ],
    })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).toEqual([-74.1, 41.25])
  })

  it('reports no anchor for a trail whose drawn vertices are all off screen', () => {
    const map = mapWith({
      [BLAZE_LAYER_ID]: [
        line('Appalachian National Scenic Trail', 'centerline', [[-80, 40]], 'White'),
      ],
    })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).toBeNull()
  })

  it('walks every part of a MultiLineString', () => {
    const map = mapWith({
      [NEARBY_BLAZE_DOTTED_LAYER_ID]: [
        {
          properties: { name: 'Long Path', source: 'oprhp_trails', blaze_color: 'Aqua' },
          geometry: {
            type: 'MultiLineString',
            coordinates: [
              [[-80, 40]],
              [
                [-74.1, 41.2],
                [-74.1, 41.3],
              ],
            ],
          },
        },
      ],
    })
    const [longPath] = trailsInView(map as unknown as MapLibreMap)
    expect(longPath.anchor).not.toBeNull()
  })

  it('reads both halves of both splits, and nothing before the style holds them', () => {
    const map = mapWith({
      [BLAZE_DOTTED_LAYER_ID]: [line('Fault Line', 'unheard_of', [[-74.05, 41.22]])],
      [NEARBY_BLAZE_LAYER_ID]: [line('Adopted Trail', 'centerline', [[-74.05, 41.22]])],
    })
    expect(trailsInView(map as unknown as MapLibreMap).map((t) => t.name)).toEqual([
      'Adopted Trail',
      'Fault Line',
    ])

    map.layerIds = []
    expect(trailsInView(map as unknown as MapLibreMap)).toEqual([])
  })
})

describe('badgeFeatures', () => {
  it('makes one point per through-route with somewhere to sit, carrying the line’s own facts', () => {
    const map = mapWith({
      [BLAZE_LAYER_ID]: [AT, line('Zebra Spur', 'side_trails', [[-74.05, 41.22]])],
    })
    const { features } = badgeFeatures(trailsInView(map as unknown as MapLibreMap))

    expect(features).toHaveLength(1)
    expect(features[0].geometry).toEqual({ type: 'Point', coordinates: [-74.1, 41.25] })
    expect(features[0].properties).toMatchObject({
      id: 'centerline:chain:0',
      name: 'Appalachian National Scenic Trail',
      source: 'centerline',
      blaze_color: 'White',
      [BADGE_MARK_PROPERTY]: trailMarkImageId('centerline'),
      [BADGE_CHIP_PROPERTY]: blazeChipImageId('White'),
    })
  })

  it('draws no badge for a through-route with no vertex on screen', () => {
    expect(
      badgeFeatures([
        {
          name: 'Appalachian National Scenic Trail',
          source: 'centerline',
          blazeColor: 'White',
          throughRoute: true,
          chosen: true,
          anchor: null,
          properties: {},
        },
      ]).features,
    ).toEqual([])
  })
})

describe('attachTrailsInView', () => {
  it('fills the badge source and reports the list, once up front and again as the camera settles', () => {
    const map = mapWith({ [BLAZE_LAYER_ID]: [AT] })
    const onChange = vi.fn()

    attachTrailsInView(map as unknown as MapLibreMap, onChange)

    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange.mock.calls[0][0].map((t: { name: string }) => t.name)).toEqual([
      'Appalachian National Scenic Trail',
    ])
    const pushed = map.sourceData.get(TRAIL_BADGE_SOURCE_ID) as { features: unknown[] }
    expect(pushed.features).toHaveLength(1)

    // The camera moves and the A.T. leaves the screen.
    map.renderedFeatures.set(BLAZE_LAYER_ID, [])
    map.emit('moveend')
    expect(onChange).toHaveBeenCalledTimes(2)
    expect(onChange.mock.calls[1][0]).toEqual([])
    expect(
      (map.sourceData.get(TRAIL_BADGE_SOURCE_ID) as { features: unknown[] }).features,
    ).toEqual([])
  })

  it('writes only on change, so its own setData cannot chase itself through idle', () => {
    const map = mapWith({ [BLAZE_LAYER_ID]: [AT] })
    const onChange = vi.fn()

    attachTrailsInView(map as unknown as MapLibreMap, onChange)
    map.emit('idle')
    map.emit('idle')
    map.emit('moveend')

    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('waits for the source, and detaches its listeners', () => {
    const map = new MockMap({})
    const onChange = vi.fn()
    const detach = attachTrailsInView(map as unknown as MapLibreMap, onChange)
    expect(onChange).not.toHaveBeenCalled()

    map.layerIds = [...TAPPABLE_BLAZE_LAYER_IDS]
    map.sourceIds = [TRAIL_BADGE_SOURCE_ID]
    map.emit('styledata')
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(map.listenerCount('idle')).toBe(1)

    detach()
    expect(map.listenerCount('idle')).toBe(0)
    expect(map.listenerCount('moveend')).toBe(0)
  })
})
