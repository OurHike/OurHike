import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createExpression, latest } from '@maplibre/maplibre-gl-style-spec'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { POI_ICON_SIZE_EXPRESSION, POI_PIN_MIN_ZOOM } from './poiLayers'
import { POI_PIN_INK_SIZE, POI_PIN_PIXEL_RATIO } from './poiIcons'
import { buildMapStyle } from './style'
import { WORKDAY_LAYER_ID } from './workdayLayers'
import { POSITION_ACCURACY_LAYER_ID } from './positionLayers'
import { CHALLENGE_ICON_ID, CHALLENGE_TAGGED_ICON_ID } from './challengePin'
import {
  attachChallengeData,
  attachChallengeIcons,
  buildChallengeLayer,
  buildChallengeSource,
  CHALLENGE_LAYER_ID,
  CHALLENGE_PIN_OFFSET,
  CHALLENGE_SOURCE_ID,
  CHALLENGE_TAGGED_PROPERTY,
  NO_CHALLENGE_PINS,
  setChallengeVisible,
  type ChallengePinFeatureCollection,
} from './challengeLayers'

// The challenge layer (#1780, features/CHALLENGES.md frame #1). The two
// rules the design makes of it - off by default, and the waypoints' seam -
// plus the ones this layer adds for itself: it claims no space, so turning
// it on cannot move anything else on the map, and it sits on its place's own
// waypoint pin.

const STYLE_OPTIONS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
  background: 'usgs_topo_offline' as const,
}

function layout(): Record<string, unknown> {
  return buildChallengeLayer().layout as Record<string, unknown>
}

const PINS: ChallengePinFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [-80.03, 37.39] },
      properties: {
        poi: 'atc_viewpoints:mcafee',
        name: 'McAfee Knob Summit',
        poi_type: 'viewpoint',
        tagged: true,
        challengeId: 'bucket',
        itemId: 'mcafee-knob',
      },
    },
  ],
}

describe('the layer', () => {
  it('starts at the waypoints’ seam, like every other pin (#1292)', () => {
    expect(buildChallengeLayer().minzoom).toBe(POI_PIN_MIN_ZOOM)
  })

  it('is hidden in the style it is built into - off until the hiker asks (principle 2)', () => {
    const built = buildMapStyle(STYLE_OPTIONS).layers.find(
      (l) => l.id === CHALLENGE_LAYER_ID,
    )

    expect(built).toBeDefined()
    expect((built!.layout as Record<string, unknown>).visibility).toBe('none')
  })

  it('asks for the tagged image on a tagged place and the hollow one otherwise', () => {
    // Evaluated through MapLibre's own engine rather than read back off the
    // array, so the answer is the image the renderer would ask for.
    const compiled = createExpression(
      layout()['icon-image'] as never,
      latest.layout_symbol['icon-image'] as never,
    )
    if (compiled.result !== 'success') throw new Error('icon-image does not compile')
    const imageFor = (tagged: boolean) =>
      compiled.value.evaluate({ zoom: 12 }, {
        type: 'Point',
        properties: { [CHALLENGE_TAGGED_PROPERTY]: tagged },
      } as never)

    expect(imageFor(true)).toBe(CHALLENGE_TAGGED_ICON_ID)
    expect(imageFor(false)).toBe(CHALLENGE_ICON_ID)
  })

  it('always draws and claims no space, so switching it on moves nothing else', () => {
    // A diamond that took part in placement would push a neighbour's pin
    // down to its dot, or a trail name off the map, because a hiker joined
    // a challenge - the walking view changing, which principle 2 forbids.
    expect(layout()['icon-allow-overlap']).toBe(true)
    expect(layout()['icon-ignore-placement']).toBe(true)
  })

  it('centres each diamond on its place’s own waypoint pin, which stands on the point', () => {
    // map/poiLayers.ts bottom-anchors a waypoint so its drawn edge touches
    // the coordinate; its centre is half the drawn pin above it. MapLibre
    // scales `icon-offset` by `icon-size`, and the two layers share one, so
    // this icon-size-1 figure holds at every size.
    expect(CHALLENGE_PIN_OFFSET).toEqual([0, -POI_PIN_INK_SIZE / 2])
    expect(layout()['icon-offset']).toEqual(CHALLENGE_PIN_OFFSET)
    expect(layout()['icon-anchor'] ?? 'center').toBe('center')
  })

  it('takes the waypoint pin’s own size at every zoom, read against the place’s type', () => {
    // The maintainer's pick of 2026-09-30 (option B, "sized to the pin"): a
    // diamond drawn at icon-size 1 was 36.8 px at z7, where the pins round it
    // are 15-21 px. The same expression, and the same `poi_type` key it
    // reads, is what keeps the apothem equal to the covered pin's radius.
    expect(layout()['icon-size']).toBe(POI_ICON_SIZE_EXPRESSION)
    const size = createExpression(
      POI_ICON_SIZE_EXPRESSION,
      latest.layout_symbol['icon-size'] as never,
    )
    if (size.result !== 'success') throw new Error('icon-size did not compile')
    const at = (zoom: number, poiType: string) =>
      size.value.evaluate({ zoom }, {
        type: 'Point',
        properties: { poi_type: poiType },
      } as never) as number
    expect(at(POI_PIN_MIN_ZOOM, 'viewpoint')).toBeLessThan(at(13, 'viewpoint'))
    expect(at(13, 'viewpoint')).toBeLessThan(at(13, 'shelter'))
    expect(at(13, 'shelter')).toBe(1)
  })

  it('prints nothing beside the pin - no name, no count', () => {
    expect(layout()).not.toHaveProperty('text-field')
  })

  it('sits directly over the workdays and under the hiker and every safety mark', () => {
    const ids = buildMapStyle(STYLE_OPTIONS).layers.map((l) => l.id)
    const at = ids.indexOf(CHALLENGE_LAYER_ID)

    expect(ids[at - 1]).toBe(WORKDAY_LAYER_ID)
    // The first thing over it is the hiker's accuracy ring; style.test.ts
    // holds that everything above THAT is a safety mark, the hiker's own
    // mark, or the ATC's.
    expect(ids[at + 1]).toBe(POSITION_ACCURACY_LAYER_ID)
  })
})

describe('the source', () => {
  it('starts empty, because the pins are the hiker’s and arrive after the map', () => {
    expect(buildChallengeSource()).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  })

  it('is in the built style, with no attribution of its own', () => {
    // Every point is a published POI's coordinate, already credited through
    // the POI source.
    const sources = buildMapStyle(STYLE_OPTIONS).sources as Record<
      string,
      Record<string, unknown>
    >
    expect(sources[CHALLENGE_SOURCE_ID]).toBeDefined()
    expect(sources[CHALLENGE_SOURCE_ID].attribution).toBeUndefined()
  })
})

describe('on a live map', () => {
  let map: MockMap

  beforeEach(() => {
    resetMapLibreMock()
    map = new MockMap({})
    map.layerIds = [CHALLENGE_LAYER_ID]
    map.sourceIds = [CHALLENGE_SOURCE_ID]
    map.styleLoaded = true
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('registers both images at the ratio they were drawn at', () => {
    attachChallengeIcons(map as never)

    for (const id of [CHALLENGE_ICON_ID, CHALLENGE_TAGGED_ICON_ID]) {
      expect(map.images.has(id)).toBe(true)
      expect(map.imageOptions.get(id)).toEqual({ pixelRatio: POI_PIN_PIXEL_RATIO })
    }
  })

  it('does not re-add an image that survived a style reload', () => {
    attachChallengeIcons(map as never)
    const addImage = vi.spyOn(map, 'addImage')

    attachChallengeIcons(map as never)

    expect(addImage).not.toHaveBeenCalled()
  })

  it('pushes the pins, and clears them when the shell passes none', () => {
    attachChallengeData(map as never, PINS)
    expect(map.sourceData.get(CHALLENGE_SOURCE_ID)).toEqual(PINS)

    // Leaving the last challenge: the pins go at once.
    attachChallengeData(map as never, NO_CHALLENGE_PINS)
    expect(map.sourceData.get(CHALLENGE_SOURCE_ID)).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })

  it('shows and hides the layer in place, without touching its data', () => {
    attachChallengeData(map as never, PINS)

    setChallengeVisible(map as never, true)
    expect(map.layoutProperties.get(`${CHALLENGE_LAYER_ID}/visibility`)).toBe('visible')

    setChallengeVisible(map as never, false)
    expect(map.layoutProperties.get(`${CHALLENGE_LAYER_ID}/visibility`)).toBe('none')
    expect(map.sourceData.get(CHALLENGE_SOURCE_ID)).toEqual(PINS)
  })
})
