import { describe, it, expect, vi } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import {
  attachTrailsInView,
  badgeFeatures,
  badgePlateWidth,
  trailsInView,
} from './trailsInView'
import {
  BLAZE_DOTTED_LAYER_ID,
  BLAZE_LAYER_ID,
  NEARBY_BLAZE_DOTTED_LAYER_ID,
  NEARBY_BLAZE_LAYER_ID,
  NETWORK_OVERVIEW_DOTTED_LAYER_ID,
  TAPPABLE_BLAZE_LAYER_IDS,
} from './style'
import {
  BADGE_ANCHOR_PROPERTY,
  TRAIL_BADGE_ANCHORS,
  BADGE_CHIP_PROPERTY,
  BADGE_MARK_PROPERTY,
  TRAIL_BADGE_SOURCE_ID,
  blazeChipImageId,
  trailMarkImageId,
} from './trailBadges'
import { POI_LAYER_ID } from './poiLayers'
import { WARNING_LAYER_ID } from './warningLayers'

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

  it('reads a named through-route off the overview sketch below the seam (#1307)', () => {
    // No blaze layers rendering at all - the corridor camera, below the pin
    // seam, where only the two network-overview layers draw. The Long
    // Path's own qualifying feature carries `name` and `through_route`
    // (export_nearby_trails.py's write_overview); the generic haze it was
    // merged with before #1307 carries neither and stays out of the list,
    // the same `if (name === null) continue` that already kept every
    // unnamed nearby line out above the seam.
    const map = mapWith({
      [NETWORK_OVERVIEW_DOTTED_LAYER_ID]: [
        line(
          'Long Path',
          'nynjtc_long_path',
          [
            [-74.2, 41.2],
            [-74.0, 41.3],
          ],
          'Aqua',
          { through_route: true },
        ),
        line(null, 'oprhp_trails', [[-74.06, 41.21]], 'Red'),
      ],
    })

    const trails = trailsInView(map as unknown as MapLibreMap)
    expect(trails.map((t) => t.name)).toEqual(['Long Path'])
    expect(trails[0].throughRoute).toBe(true)
    expect(trails[0].chosen).toBe(false)
    expect(trails[0].anchor).not.toBeNull()
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

  it('anchors a badge on the in-view vertex nearest the frame’s centre (the review of #1374)', () => {
    // Pixel space (the mock projects identically, and reports a 390x844
    // canvas): a line across the screen at y = 400, a vertex every 19 px.
    // The frame's centre is (195, 422); the nearest vertex is at 190.
    const map = mapWith({
      [BLAZE_LAYER_ID]: [
        line(
          'Appalachian National Scenic Trail',
          'centerline',
          Array.from({ length: 21 }, (_, i) => [i * 19, 400] as [number, number]),
          'White',
        ),
      ],
    })
    map.bounds = { west: 0, south: 0, east: 390, north: 844 }
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).toEqual([190, 400])
    expect(at.badgeFit).toBe('full')
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

  it('reads every piece of a trail that comes back per tile, nearest the centre first', () => {
    // The old rule kept the longest piece and threw the rest away, so a
    // trail whose long piece ran along the top of the frame was badged up
    // there while a short piece of it sat by the centre. Pixel space: a
    // long piece along y = 100 and a two-vertex piece by the centre.
    const map = mapWith({
      [BLAZE_LAYER_ID]: [
        line(
          'Appalachian National Scenic Trail',
          'centerline',
          Array.from({ length: 21 }, (_, i) => [i * 19, 100] as [number, number]),
          'White',
        ),
        line(
          'Appalachian National Scenic Trail',
          'centerline',
          [
            [176, 440],
            [214, 440],
          ],
          'White',
        ),
      ],
    })
    map.bounds = { west: 0, south: 0, east: 390, north: 844 }
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor?.[1]).toBe(440)
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
      [BLAZE_LAYER_ID]: [
        {
          properties: { name: 'Long Path', source: 'centerline', blaze_color: 'Aqua' },
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
    // The vertex nearest the frame's centre, which in this degree-space
    // fixture (the mock projects degrees straight to px) is the eastmost.
    expect(features[0].geometry).toEqual({ type: 'Point', coordinates: [-74, 41.3] })
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
          takeable: true,
          chosen: true,
          anchor: null,
          badgeFit: 'full',
          badgeAnchor: 'left',
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

describe('the chrome over the canvas (#1283, the second preview frame)', () => {
  // The mock unprojects identically - x IS the longitude, y IS the latitude -
  // and reports a 390x844 container, so a viewport of [0..390] x [0..844] in
  // "degrees" is the canvas in pixels, and an inset is an inset.
  function screenMap(byLayer: Record<string, unknown[]>): MockMap {
    const map = mapWith(byLayer)
    map.bounds = { west: 0, south: 0, east: 390, north: 844 }
    return map
  }
  const PLATE = { top: 110, right: 0, bottom: 62, left: 0 }

  it('anchors the badge in the clear when the vertex nearest the centre runs under the plate', () => {
    // Two vertices: one under the identity plate at y = 100, 322 px from
    // the frame's centre, and one in the clear at y = 760, 338 px from it.
    const map = screenMap({
      [BLAZE_LAYER_ID]: [
        line(
          'Appalachian National Scenic Trail',
          'centerline',
          [
            [195, 100],
            [195, 760],
          ],
          'White',
        ),
      ],
    })
    const [withoutInsets] = trailsInView(map as unknown as MapLibreMap)
    const [withInsets] = trailsInView(map as unknown as MapLibreMap, PLATE)

    // Free of insets the nearer vertex wins, under the plate.
    expect(withoutInsets.anchor).toEqual([195, 100])
    expect(withoutInsets.anchor?.[1]).toBeLessThan(PLATE.top)
    // With them the clear runs come first, and the plate hangs above the
    // vertex - the one anchor that keeps it inside the frame's foot.
    expect(withInsets.anchor).toEqual([195, 760])
    expect(withInsets.badgeFit).toBe('full')
  })

  it('falls back to the whole canvas for a trail with no vertex in the clear', () => {
    const map = screenMap({
      [BLAZE_LAYER_ID]: [
        line(
          'Appalachian National Scenic Trail',
          'centerline',
          [
            [100, 30],
            [200, 40],
            [300, 20],
          ],
          'White',
        ),
      ],
    })
    const [at] = trailsInView(map as unknown as MapLibreMap, PLATE)
    expect(at.anchor).toEqual([200, 40])
  })

  it('still lists a trail that is only under the plate: it is on the map', () => {
    const map = screenMap({
      [NEARBY_BLAZE_DOTTED_LAYER_ID]: [
        line('Long Path', 'oprhp_trails', [[100, 30]], 'Aqua'),
      ],
    })
    expect(trailsInView(map as unknown as MapLibreMap, PLATE).map((t) => t.name)).toEqual(
      ['Long Path'],
    )
  })

  it('reads the insets it was attached with', () => {
    const map = screenMap({
      [BLAZE_LAYER_ID]: [
        line(
          'Appalachian National Scenic Trail',
          'centerline',
          [
            [0, 300],
            [100, 200],
            [150, 60],
            [250, 40],
            [390, 50],
          ],
          'White',
        ),
      ],
    })
    const onChange = vi.fn()
    attachTrailsInView(map as unknown as MapLibreMap, onChange, PLATE)
    expect(onChange.mock.calls[0][0][0].anchor).toEqual([100, 200])
  })
})

describe('the pins in view (#1283, the third preview frame)', () => {
  // Identity projection again: a vertex at [x, y] projects to pixel (x, y),
  // and a pin at [x, y] is a 44 px box round pixel (x, y).
  function screenMap(byLayer: Record<string, unknown[]>): MockMap {
    const map = mapWith(byLayer)
    map.layerIds = [...map.layerIds, POI_LAYER_ID]
    map.bounds = { west: 0, south: 0, east: 390, north: 844 }
    return map
  }
  /** The A.T. straight across the 390 px screen at y = 400, a vertex every
   *  19 px from 0 to 380 - twenty-one of them, so the middle is one vertex,
   *  at 190, and not a tie between two. */
  const ACROSS = line(
    'Appalachian National Scenic Trail',
    'centerline',
    Array.from({ length: 21 }, (_, i) => [i * 19, 400] as [number, number]),
    'White',
  )
  const pin = (x: number, y: number) => ({
    properties: { poi_type: 'shelter' },
    geometry: { type: 'Point', coordinates: [x, y] },
  })

  it('anchors at the middle of the run when nothing is in the way', () => {
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS] })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).toEqual([190, 400])
  })

  it('marks no row chosen when nothing is taken, and the A.T. chosen when it is (#1306)', () => {
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS] })
    const [untaken] = trailsInView(map as unknown as MapLibreMap, undefined, [])
    const [taken] = trailsInView(map as unknown as MapLibreMap)
    expect(untaken.chosen).toBe(false)
    expect(untaken.throughRoute).toBe(true)
    expect(taken.chosen).toBe(true)
  })

  it('fans out from the centre to the first vertex with room, and takes the mark where the full plate has none', () => {
    // A shelter on the trail just short of the middle, its box reaching
    // from x = 161 to 209. The full plate is some 240 px wide on a 390 px
    // frame, so no position anywhere keeps it both inside the frame and
    // clear of that box - hung to either side it runs off an edge, centred
    // above or below it still spans the pin's column - and the search
    // falls to the mark. The mark's 36 px box, hung off the right of the
    // vertex at 228 (33 px from the centre, one vertex nearer than 152 on
    // the other side), starts at 223.6, clear of the pin by 14 px; at 209
    // and 171 every position of it touches the box. The margins are the
    // geometry the placer tests, to the decimal (the fifth preview frame,
    // 2026-09-08).
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS], [POI_LAYER_ID]: [pin(185, 400)] })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).toEqual([228, 400])
    expect(at.badgeFit).toBe('mark')
  })

  it('reads every pin layer placed before the badge, not the waypoints alone', () => {
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS] })
    map.layerIds = [...map.layerIds, WARNING_LAYER_ID]
    map.renderedFeatures.set(WARNING_LAYER_ID, [pin(185, 400)])
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).not.toEqual([190, 400])
    expect(map.featureQueries.some((q) => q.layers.includes(WARNING_LAYER_ID))).toBe(true)
  })

  it('reads the chrome’s bands as the frame too, and lands in the same place', () => {
    // The plate and the tab bar take the top and the foot; the line at
    // y = 400 is between them, so the answer is the one above.
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS], [POI_LAYER_ID]: [pin(185, 400)] })
    const [at] = trailsInView(map as unknown as MapLibreMap, {
      top: 110,
      right: 0,
      bottom: 62,
      left: 0,
    })
    expect(at.badgeFit).toBe('mark')
    expect(at.anchor).toEqual([228, 400])
  })

  it('hands over the mark on the nearest vertex where not even the mark has room', () => {
    // Pins every nineteen pixels along the whole line: nothing fits
    // anywhere, so the mark goes on the vertex nearest the centre and the
    // layer, allowed to overlap (map/trailBadges.ts), draws it there -
    // never nothing.
    const map = screenMap({
      [BLAZE_LAYER_ID]: [ACROSS],
      [POI_LAYER_ID]: Array.from({ length: 21 }, (_, i) => pin(i * 19, 400)),
    })
    const [at] = trailsInView(map as unknown as MapLibreMap, {
      top: 110,
      right: 0,
      bottom: 62,
      left: 0,
    })
    expect(at.badgeFit).toBe('mark')
    expect(at.anchor).toEqual([190, 400])
  })

  it('takes the full form wherever it fits, and says so on the feature', () => {
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS] })
    const trails = trailsInView(map as unknown as MapLibreMap)
    expect(trails[0].badgeFit).toBe('full')
    const { features } = badgeFeatures(trails)
    expect(features[0].properties).toMatchObject({ fit: 'full' })
    // Mid-screen the plate fits only above or below the vertex - a 390 px
    // screen is narrower than the vertex plus a plate on either side - and
    // whichever side it is, the feature says so.
    expect(TRAIL_BADGE_ANCHORS).toContain(features[0].properties?.[BADGE_ANCHOR_PROPERTY])
  })

  it('hands the layer the side it chose, so a plate at the right edge is drawn leftward', () => {
    // One vertex twenty px from the right edge. The plate to the right of
    // it ('left', the first anchor) would run off the screen; to the left
    // of it ('right') it fits whole. The engine, allowed to overlap, would
    // draw the first anchor on its list regardless (the phone frame at
    // 05e9506a), so the choice rides the feature and the layer reads it.
    const map = screenMap({
      [BLAZE_LAYER_ID]: [
        line('Appalachian National Scenic Trail', 'centerline', [[370, 400]], 'White'),
      ],
    })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.badgeFit).toBe('full')
    expect(at.badgeAnchor).toBe('right')
    const { features } = badgeFeatures([at])
    expect(features[0].properties).toMatchObject({ [BADGE_ANCHOR_PROPERTY]: 'right' })

    // And the mirror: at the left edge the first anchor fits, and is kept.
    const mirror = screenMap({
      [BLAZE_LAYER_ID]: [
        line('Appalachian National Scenic Trail', 'centerline', [[20, 400]], 'White'),
      ],
    })
    expect(trailsInView(mirror as unknown as MapLibreMap)[0].badgeAnchor).toBe('left')
  })

  it('searches only for a through-route, which is the only line that gets a badge', () => {
    const map = screenMap({
      [NEARBY_BLAZE_DOTTED_LAYER_ID]: [
        line('Long Path', 'oprhp_trails', [[100, 400]], 'Aqua'),
      ],
    })
    const [longPath] = trailsInView(map as unknown as MapLibreMap)
    expect(longPath.anchor).toBeNull()
  })

  it('estimates the plate wide enough for the name it will carry', () => {
    // Measured on the stand-alone render: 33 characters set 185 px of text;
    // the estimate must not come out narrower than what will be drawn.
    expect(badgePlateWidth('Appalachian National Scenic Trail')).toBeGreaterThan(185 + 42)
    expect(badgePlateWidth('A.T.')).toBeLessThan(badgePlateWidth('Long Path'))
    // The mark alone: the mark and its paper, whatever the name.
    expect(badgePlateWidth('Appalachian National Scenic Trail', 'mark')).toBe(32)
  })
})
