import { describe, it, expect, vi } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import {
  attachTrailsInView,
  badgeFeatures,
  badgePlateWidth,
  badgeTextSize,
  indexObstacles,
  trailsInView,
} from './trailsInView'
import {
  BLAZE_UNTAKEN_LAYER_ID,
  BLAZE_LAYER_ID,
  NEARBY_BLAZE_UNTAKEN_LAYER_ID,
  NEARBY_BLAZE_LAYER_ID,
  NETWORK_OVERVIEW_UNTAKEN_LAYER_ID,
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
      [NEARBY_BLAZE_UNTAKEN_LAYER_ID]: [
        line('Long Path', 'oprhp_trails', [[-74.05, 41.22]], 'Aqua'),
        // The same trail from a second tile.
        line('Long Path', 'oprhp_trails', [[-74.04, 41.23]], 'Aqua'),
        line('Ramapo-Dunderberg Trail', 'oprhp_trails', [[-74.06, 41.21]], 'Red'),
      ],
    })

    expect(trailsInView(map as unknown as MapLibreMap).map((t) => t.name)).toEqual([
      'Appalachian Trail',
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
      [NETWORK_OVERVIEW_UNTAKEN_LAYER_ID]: [
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

  it('names a marked trail off the registry when the sketch carries no name (2026-09-11)', () => {
    // THE BUCKET'S OWN SHAPE, not a hypothetical: the published
    // network_overview.geojson carries `source`, `blaze_color` and
    // `trail_status` and nothing else - 38 features, none named, read live
    // 2026-09-11 - because the publish that would refresh it is held back
    // with the network file it sketches. The maintainer's frame of that day
    // is the A.T. wearing its pill over the Hudson and the Long Path in aqua
    // beside it wearing nothing. The registry knows the name and the mark;
    // map/trailBadges.ts's registryNameForSource is why taking the name from
    // there says nothing the mark did not.
    const map = mapWith({
      [NETWORK_OVERVIEW_UNTAKEN_LAYER_ID]: [
        line(
          null,
          'nynjtc_long_path',
          [
            [-74.2, 41.2],
            [-74.0, 41.3],
          ],
          'Aqua',
        ),
      ],
    })

    const trails = trailsInView(map as unknown as MapLibreMap)
    expect(trails.map((t) => t.name)).toEqual(['Long Path'])
    expect(trails[0].throughRoute).toBe(true)
    expect(trails[0].anchor).not.toBeNull()
  })

  it('leaves the unnamed haze unnamed - only a marked source gets the fallback', () => {
    // The forty fine lines of a state park are one folded feature per
    // (source, blaze, status) with no name, and they must stay off the list:
    // the fallback fires for the two sources BADGE_MARK_BY_SOURCE declares,
    // and a park's feed is not one of them. This is the half of the change
    // that keeps "Trails in view" a list of trails rather than of sources.
    const map = mapWith({
      [NETWORK_OVERVIEW_UNTAKEN_LAYER_ID]: [
        line(null, 'oprhp_trails', [[-74.06, 41.21]], 'Red'),
        line(null, 'dec_hiking_trails', [[-74.05, 41.22]], 'Blue'),
      ],
    })

    expect(trailsInView(map as unknown as MapLibreMap)).toEqual([])
  })

  it('shows ATC’s centerline as "Appalachian Trail", not its federal designation', () => {
    // ATC publishes "Appalachian National Scenic Trail" on all 3,025
    // centerline segments (the count is in map/trailLabels.test.ts). Nobody
    // says that on a sheet headed "Appalachian Trail", so the badge and the
    // legend row - both measured off this one pass - read the registry's
    // name instead (lib/trails.ts's PUBLISHED_ALIASES, the maintainer's ask
    // of 2026-09-16). The fixture stays as ATC spells it: the point of the
    // test is that the rename happens here rather than in the data.
    const map = mapWith({ [BLAZE_LAYER_ID]: [AT] })

    expect(trailsInView(map as unknown as MapLibreMap).map((t) => t.name)).toEqual([
      'Appalachian Trail',
    ])
  })

  it('leaves a steward’s own name exactly as published, however formal it looks', () => {
    // The other half of the rename and the one worth guarding: only a
    // spelling the registry already knows is swapped. A name this app does
    // not recognise is somebody else's data, and renaming it would be a
    // claim about that data nobody here can stand behind - the same refusal
    // `trailForName` makes about substrings, where "Long Path Link Trail" is
    // a different trail from the Long Path and must not wear its mark.
    const map = mapWith({
      [NEARBY_BLAZE_UNTAKEN_LAYER_ID]: [
        line('Ramapo-Dunderberg Trail', 'oprhp_trails', [[-74.06, 41.21]], 'Red'),
        line('Long Path Link Trail', 'oprhp_trails', [[-74.05, 41.22]], 'Aqua'),
      ],
    })

    expect(trailsInView(map as unknown as MapLibreMap).map((t) => t.name)).toEqual([
      'Long Path Link Trail',
      'Ramapo-Dunderberg Trail',
    ])
  })

  it('puts through-routes first, then the chosen system, then the rest by name', () => {
    const map = mapWith({
      [BLAZE_LAYER_ID]: [line('Zebra Spur', 'side_trails', [[-74.05, 41.22]]), AT],
      [NEARBY_BLAZE_UNTAKEN_LAYER_ID]: [
        line('Beech Trail', 'oprhp_trails', [[-74.06, 41.21]]),
        line('Arden-Surebridge Trail', 'oprhp_trails', [[-74.07, 41.21]]),
      ],
    })

    const trails = trailsInView(map as unknown as MapLibreMap)
    expect(trails.map((t) => [t.name, t.throughRoute, t.chosen])).toEqual([
      ['Appalachian Trail', true, true],
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
      [BLAZE_UNTAKEN_LAYER_ID]: [line('Fault Line', 'unheard_of', [[-74.05, 41.22]])],
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
      // What the plate prints, so the registry's name rather than ATC's -
      // and note it beats the feed's `name` the spread carries in, which is
      // the one property of the line's own facts the badge overrides.
      name: 'Appalachian Trail',
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
          name: 'Appalachian Trail',
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
      'Appalachian Trail',
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
      [NEARBY_BLAZE_UNTAKEN_LAYER_ID]: [
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

  /** Five shelters along the trail from x = 38 to x = 230, each a 48 px box,
   *  the boxes touching: together they cover x = 14 to 254 and leave 136 px
   *  of clear frame east of them. Measured 2026-09-16 with the plate
   *  geometry this file also pins below: the full plate's box is 148 px
   *  wide (130 px of text, 3 left, 9 right, 3 of border and symbol padding
   *  each side), so it fits in neither the 136 px gap nor anywhere behind
   *  the row, and the mark's 36 px box fits the gap with room to spare.
   *  That is the two-rung search this block exists to drive. */
  const CROWDED = [38, 86, 134, 182, 230].map((x) => pin(x, 400))

  it('fans out from the centre to the first vertex with room, and takes the mark where the full plate has none', () => {
    // The mark goes on 266 - the eighth candidate out from the frame's
    // centre (195, 422), and the first whose box clears the pins: hung off
    // the right of that vertex it spans 263.6 to 299.6, clear of the last
    // pin box by 9.6 px, where at 247 it would start at 244.6 and still be
    // inside it. The margins are the geometry the placer tests, to the
    // decimal (the fifth preview frame, 2026-09-08).
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS], [POI_LAYER_ID]: CROWDED })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).toEqual([266, 400])
    expect(at.badgeFit).toBe('mark')
  })

  it('keeps the name beside a single shelter, which the longer one lost it to', () => {
    // A row is what it now takes, and this is the pin that used to be
    // enough on its own: one shelter just short of the middle, box from
    // x = 161 to 209. ATC's "Appalachian National Scenic Trail" needed a
    // 240 px plate and had nowhere on a 390 px frame to hang it clear of
    // that box, so the badge fell to the bare mark and the trail went
    // unnamed on screen. "Appalachian Trail" needs 144 px (both measured
    // 2026-09-16, and badgePlateWidth is asserted on below), which fits
    // beside the pin at the vertex at 228 - so the rename buys back the
    // name on exactly the screen #1283's third preview frame was about.
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS], [POI_LAYER_ID]: [pin(185, 400)] })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).toEqual([228, 400])
    expect(at.badgeFit).toBe('full')
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
    const map = screenMap({ [BLAZE_LAYER_ID]: [ACROSS], [POI_LAYER_ID]: CROWDED })
    const [at] = trailsInView(map as unknown as MapLibreMap, {
      top: 110,
      right: 0,
      bottom: 62,
      left: 0,
    })
    expect(at.badgeFit).toBe('mark')
    expect(at.anchor).toEqual([266, 400])
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

  it('reads the whole line at a coarser pitch when it is longer than the cap, rather than only its densest mile', () => {
    // The z9 frame of the review of #1374, in screen space: two thousand
    // vertices a tenth of a px apart under a pin every nineteen px (the
    // seam's tile geometry through Harriman, pins on every stretch of it),
    // and eighty sparse vertices in the clear beyond them. The six hundred
    // nearest the centre all lie under the pins, so a search cut at the
    // centre finds nothing and drops the mark on the nearest vertex - under
    // a pin. Sampled along the line, the clear stretch is reached.
    const dense = Array.from(
      { length: 2001 },
      (_, i) => [100 + i / 10, 400] as [number, number],
    )
    const clear = Array.from({ length: 80 }, (_, i) => [301 + i, 400] as [number, number])
    const map = screenMap({
      [BLAZE_LAYER_ID]: [
        line(
          'Appalachian National Scenic Trail',
          'centerline',
          [...dense, ...clear],
          'White',
        ),
      ],
      [POI_LAYER_ID]: Array.from({ length: 11 }, (_, i) => pin(100 + i * 20, 400)),
    })
    const [at] = trailsInView(map as unknown as MapLibreMap)
    expect(at.anchor).not.toBeNull()
    // Past the last pin at x = 300: on the clear stretch, where the mark's
    // box clears the pin's (the placer's own test, plateBox against the
    // obstacle), rather than on the vertex nearest the centre under a pin.
    expect((at.anchor as [number, number])[0]).toBeGreaterThan(300)
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
      [NEARBY_BLAZE_UNTAKEN_LAYER_ID]: [
        line('Long Path', 'oprhp_trails', [[100, 400]], 'Aqua'),
      ],
    })
    const [longPath] = trailsInView(map as unknown as MapLibreMap)
    expect(longPath.anchor).toBeNull()
  })

  it('estimates the plate wide enough for the name it will carry', () => {
    // Measured on the stand-alone render: 33 characters set 185 px of text;
    // the estimate must not come out narrower than what will be drawn.
    //
    // "Appalachian National Scenic Trail" is the CALIBRATION here, not a
    // name this badge still prints - since 2026-09-16 the A.T.'s plate reads
    // "Appalachian Trail" (lib/trails.ts). The measured pair is kept because
    // it is the only chars-to-px datum anybody produced, and the estimator
    // has to hold for whatever name a steward publishes next, not just for
    // the four the registry knows.
    expect(badgePlateWidth('Appalachian National Scenic Trail')).toBeGreaterThan(185 + 42)
    expect(badgePlateWidth('A.T.')).toBeLessThan(badgePlateWidth('Long Path'))
    // The mark alone: the mark and its paper, whatever the name.
    expect(badgePlateWidth('Appalachian National Scenic Trail', 'mark')).toBe(32)

    // The two figures the badge-fit tests above reason with, measured
    // 2026-09-16: the rename took the A.T.'s plate from 240 px to 144 px on
    // a 390 px frame, which is why one shelter no longer costs the trail its
    // name and it takes a row of five.
    expect(badgePlateWidth('Appalachian National Scenic Trail')).toBe(240)
    expect(badgePlateWidth('Appalachian Trail')).toBe(144)
  })
})

// THE OBSTACLE GRID (#1415)
//
// `anchorWithRoom` is `fits x candidates x anchors x obstacles`. It returns
// on the first position that fits, so the ordinary frame is cheap - but the
// case it cannot return early from is the one the "always finds a place"
// fallback exists for: when NOTHING fits, every candidate is tried at every
// anchor in both fits, and each of those must look at every obstacle to
// conclude there is no room.
//
// These tests hold the index to its contract (a superset, never a subset)
// and then COUNT the work it removes over the issue's own numbers. The count
// is not a frame time and is not offered as one - nobody has profiled this
// on a phone and #1415's `@unvalidated` note stands. It is the arithmetic
// that decides how much there is to profile.
describe('indexObstacles', () => {
  const box = (x: number, y: number, width = 48, height = 48) => ({
    x1: x,
    y1: y,
    x2: x + width,
    y2: y + height,
  })

  const overlaps = (a: ReturnType<typeof box>, b: ReturnType<typeof box>) =>
    a.x1 <= b.x2 && a.x2 >= b.x1 && a.y1 <= b.y2 && a.y2 >= b.y1

  /** A pin every 40 px over a 390x844 phone screen - 200 of them, the order
   *  #1415 describes as "a few hundred on a shelter-and-spring-lined
   *  screen". */
  function pinnedScreen() {
    const pins = []
    for (let x = 0; x < 390; x += 40) {
      for (let y = 0; y < 844; y += 40) pins.push(box(x - 24, y - 24))
    }
    return pins
  }

  it('never loses an overlap - the property the whole thing rests on', () => {
    const pins = pinnedScreen()
    const index = indexObstacles(pins)

    // Every query the sweep below makes, checked against the honest answer.
    let checked = 0
    for (let x = -60; x < 450; x += 7) {
      for (let y = -60; y < 900; y += 11) {
        const query = box(x, y, 225, 32)
        const truth = pins.some((pin) => overlaps(query, pin))
        const viaIndex = index.near(query).some((pin) => overlaps(query, pin))
        expect(viaIndex).toBe(truth)
        checked += 1
      }
    }
    expect(checked).toBeGreaterThan(5000)
  })

  it('holds the superset direction for a box projected far off screen', () => {
    // Coordinates outside the grid's addressable range clamp into the edge
    // bucket rather than wrapping, so a pin MapLibre projected a long way
    // off screen is still found rather than silently skipped.
    const far = box(9_000_000, 9_000_000)
    const index = indexObstacles([far])

    expect(index.near(box(9_000_000, 9_000_000, 10, 10)).length).toBeGreaterThan(0)
  })

  it('is empty rather than undefined where nothing was indexed', () => {
    const index = indexObstacles([])

    expect(index.size).toBe(0)
    expect(index.near(box(10, 10))).toEqual([])
  })

  // THE COUNT. CANDIDATE_LIMIT is 600 and TRAIL_BADGE_ANCHORS has 8 entries,
  // in two fits - 9,600 positions per named trail on the frame where nothing
  // fits. Half of that (one fit) is swept below, twice, at two pin densities,
  // because the saving is a ratio between the plate's footprint and the pin
  // spacing rather than a constant.
  function examinations(spacingPx: number) {
    const pins = []
    for (let x = 0; x < 390; x += spacingPx) {
      for (let y = 0; y < 844; y += spacingPx) pins.push(box(x - 24, y - 24))
    }
    const index = indexObstacles(pins)
    const plate = badgeTextSize('Appalachian National Scenic Trail', 'full')

    let examined = 0
    let positions = 0
    for (let candidate = 0; candidate < 600; candidate += 1) {
      const at = { x: (candidate * 13) % 390, y: (candidate * 29) % 844 }
      for (let anchor = 0; anchor < 8; anchor += 1) {
        examined += index.near(box(at.x, at.y, plate.width, plate.height)).length
        positions += 1
      }
    }
    return { pins: pins.length, positions, before: positions * pins.length, examined }
  }

  it('cuts what a nothing-fits frame examines, most where the pins are thinnest', () => {
    // A pin every 40 px is denser than the 64 px bucket, so each plate's
    // buckets hold two or three and the saving is at its smallest.
    const dense = examinations(40)
    expect(dense.positions).toBe(4800)
    expect(dense.pins).toBe(220)
    expect(dense.before).toBe(1_056_000)
    // MEASURED 2026-09-15: 1,056,000 -> 147,360, a factor of 7.2.
    // Stated as a factor rather than an order: #1415 guessed the saving was
    // the whole product, and it is not - the plate's own footprint is a real
    // floor and the grid cannot go under it.
    expect(dense.examined).toBeLessThan(dense.before / 5)

    // A pin every 80 px - still "a few hundred" by #1415's description, and
    // the shape of an ordinary shelter-and-spring screen rather than a wall.
    const ordinary = examinations(80)
    expect(ordinary.pins).toBe(55)
    // MEASURED the same day: 264,000 -> 33,504, a factor of 7.9.
    expect(ordinary.examined).toBeLessThan(ordinary.before / 6)

    // The ratio improves as the field thins, which is the property worth
    // pinning: the grid's cost tracks what the plate actually covers, where
    // the scan's tracked how many pins were on the screen at all.
    expect(ordinary.examined / ordinary.before).toBeLessThan(
      dense.examined / dense.before,
    )
  })

  it('leaves the floor where it belongs - what the plate itself covers', () => {
    // Not zero, and it should not be. A 225 px name lies across four 64 px
    // buckets and a pin box reaches 48 px, so the pins in those buckets are
    // genuinely candidates for overlapping it. The index removes the pins
    // elsewhere on the screen, which is all it claims to do.
    const { examined, positions } = examinations(40)

    expect(examined).toBeGreaterThan(positions)
  })
})
