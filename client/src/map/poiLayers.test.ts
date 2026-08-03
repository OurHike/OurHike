import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createExpression, featureFilter } from '@maplibre/maplibre-gl-style-spec'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { POI_TYPES } from '../lib/config'
import { buildPoiIcons, poiIconId, UNKNOWN_POI_TYPE } from './poiIcons'
import {
  attachHiddenPoiTypes,
  attachPoiData,
  attachPoiIcons,
  buildPoiLayer,
  poiFeatureCollection,
  poiTypeFilter,
  POI_ICON_EXPRESSION,
  POI_ICON_SIZE_EXPRESSION,
  POI_LAYER_ID,
  POI_MIN_ZOOM,
  POI_PRIORITY,
  POI_SORT_KEY_EXPRESSION,
  POI_SOURCE_ID,
} from './poiLayers'

// These are EVALUATED rather than shape-asserted wherever MapLibre gives us
// the means to. An expression can have exactly the right array structure and
// still resolve to the wrong image, and a `match` with a missing arm produces
// no error at all - just a pin that never appears.

function evaluate(expression: unknown[], properties: Record<string, unknown>, zoom = 14) {
  // The rootKey is only used to place errors in a style document; any stable
  // string does.
  const compiled = createExpression(expression, 'layers[0].layout.icon-image')
  if (compiled.result === 'error') {
    throw new Error(compiled.value.map((e) => e.message).join('; '))
  }
  return compiled.value.evaluate({ zoom }, { properties, type: 'Point' } as never)
}

function poi(type: string, confidence: 'high' | 'low' = 'high') {
  return { poi_type: type, confidence }
}

const REGISTERED_ICON_IDS = new Set(buildPoiIcons().map((icon) => icon.id))

describe('the icon expression', () => {
  it.each(POI_TYPES)('resolves %s to an image that was actually registered', (type) => {
    // The failure this catches is silent: a `match` arm naming an image nobody
    // registered draws nothing, logs once per tile, and looks exactly like
    // "there are no POIs here".
    for (const confidence of ['high', 'low'] as const) {
      const resolved = evaluate(POI_ICON_EXPRESSION, poi(type, confidence))

      expect(resolved).toBe(poiIconId(type, confidence))
      expect(REGISTERED_ICON_IDS.has(resolved as string)).toBe(true)
    }
  })

  it('falls through to the neutral pin for a type this build has never seen', () => {
    // A category added upstream reaches the map as a neutral pin rather than
    // as nothing, so new data does not wait on a client release to be visible.
    const resolved = evaluate(POI_ICON_EXPRESSION, poi('yurt'))

    expect(resolved).toBe(poiIconId(UNKNOWN_POI_TYPE, 'high'))
    expect(REGISTERED_ICON_IDS.has(resolved as string)).toBe(true)
  })

  it('treats anything that is not an explicit "high" as unverified', () => {
    // Matching lib/trailData.ts, which only counts an explicit 'high' as
    // verified. Guessing the other way would vouch for a water source nobody
    // has checked.
    for (const confidence of ['low', '', 'unknown']) {
      expect(evaluate(POI_ICON_EXPRESSION, poi('water', confidence as 'low'))).toBe(
        poiIconId('water', 'low'),
      )
    }
  })
})

describe('density', () => {
  it('draws no pins at all above the whole-corridor view', () => {
    // The opening camera frames 2,197 miles. Eight hundred pins on it is a
    // texture, not information, and letting the collision engine thin them
    // would answer "which of these matters" by geometry.
    expect(buildPoiLayer().minzoom).toBe(POI_MIN_ZOOM)
    expect(POI_MIN_ZOOM).toBeGreaterThan(8)
  })

  it('leaves the collision engine switched on, which is the whole density story', () => {
    const layout = buildPoiLayer().layout as Record<string, unknown>

    expect(layout['icon-allow-overlap']).toBe(false)
  })

  it('grows the pins as the hiker zooms in', () => {
    const far = evaluate(POI_ICON_SIZE_EXPRESSION, poi('water'), POI_MIN_ZOOM) as number
    const near = evaluate(POI_ICON_SIZE_EXPRESSION, poi('water'), 14) as number

    expect(far).toBeLessThan(near)
    expect(near).toBe(1)
  })

  it('gives water the best sort key, so it is the pin that survives a collision', () => {
    // Not a visual preference. When two pins cannot both be placed, the one
    // that stays should be the one a hiker most needs to know about, and
    // MapLibre places lower sort keys first.
    const keys = [...POI_TYPES, 'yurt'].map(
      (type) => [type, evaluate(POI_SORT_KEY_EXPRESSION, poi(type)) as number] as const,
    )
    const water = keys.find(([type]) => type === 'water')?.[1]

    expect(water).toBe(0)
    for (const [type, key] of keys) {
      if (type !== 'water') expect(key).toBeGreaterThan(water as number)
    }
  })

  it('ranks an unknown type below every known one', () => {
    expect(evaluate(POI_SORT_KEY_EXPRESSION, poi('yurt'))).toBeGreaterThan(
      Math.max(
        ...POI_TYPES.map((t) => evaluate(POI_SORT_KEY_EXPRESSION, poi(t)) as number),
      ),
    )
  })

  it('covers every published POI type in the priority order', () => {
    // A type missing here would silently take the fallback rank, which for a
    // future water-adjacent category is the wrong answer by default.
    for (const type of POI_TYPES) expect(POI_PRIORITY).toContain(type)
  })
})

describe('the pin layer', () => {
  it('asks for no text, because there is no font to render it with offline', () => {
    // The style declares no `glyphs` URL - it cannot, there is no network on a
    // mountain. MapLibre draws icons happily without one and cannot draw a
    // single character of a label. A `text-field` added here would fail at the
    // top of a hill and nowhere else.
    const layout = buildPoiLayer().layout as Record<string, unknown>

    expect(layout['text-field']).toBeUndefined()
  })

  it('reads its pins from the POI source', () => {
    const layer = buildPoiLayer()

    expect(layer.type).toBe('symbol')
    expect('source' in layer && layer.source).toBe(POI_SOURCE_ID)
  })
})

describe('poiFeatureCollection', () => {
  const pois = [
    { id: 'w1', type: 'water', lat: 39.3, lon: -77.1, confidence: 'high' as const },
    { id: 's1', type: 'shelter', lat: 40.1, lon: -76.4, confidence: 'low' as const },
  ]

  it('writes coordinates as [lon, lat], which is the order GeoJSON means', () => {
    // Reversed, every pin in the Appalachians lands in the Indian Ocean, and
    // nothing in the type system objects - both are numbers.
    const [first] = poiFeatureCollection(pois).features

    expect(first.geometry.coordinates).toEqual([-77.1, 39.3])
  })

  it('carries the two attributes the style matches on, and the id to look up by', () => {
    const [, shelter] = poiFeatureCollection(pois).features

    expect(shelter.id).toBe('s1')
    expect(shelter.properties).toEqual({ poi_type: 'shelter', confidence: 'low' })
  })

  it('produces a collection every feature of which the icon expression can resolve', () => {
    for (const feature of poiFeatureCollection(pois).features) {
      expect(
        REGISTERED_ICON_IDS.has(
          evaluate(POI_ICON_EXPRESSION, feature.properties) as string,
        ),
      ).toBe(true)
    }
  })

  it('is empty for no POIs rather than undefined', () => {
    expect(poiFeatureCollection([])).toEqual({ type: 'FeatureCollection', features: [] })
  })
})

describe('hiding a category', () => {
  function passes(hidden: string[], type: string): boolean {
    const { filter } = featureFilter(
      poiTypeFilter(new Set(hidden)) as never,
      'layers[0].filter',
    )
    return filter(
      { zoom: 14 } as never,
      { properties: poi(type), type: 1 } as never,
      null as never,
    )
  }

  it('shows everything when nothing is hidden', () => {
    for (const type of POI_TYPES) expect(passes([], type)).toBe(true)
  })

  it('drops exactly the hidden category and nothing else', () => {
    expect(passes(['water'], 'water')).toBe(false)
    expect(passes(['water'], 'shelter')).toBe(true)
  })

  it('hides several categories at once', () => {
    expect(passes(['water', 'campsite'], 'water')).toBe(false)
    expect(passes(['water', 'campsite'], 'campsite')).toBe(false)
    expect(passes(['water', 'campsite'], 'resupply')).toBe(true)
  })

  it('is stable regardless of the order the hiker tapped the rows in', () => {
    // The filter is handed to MapLibre on every toggle; two orderings of the
    // same set producing two different filters would re-evaluate every feature
    // for no reason.
    expect(poiTypeFilter(new Set(['water', 'campsite']))).toEqual(
      poiTypeFilter(new Set(['campsite', 'water'])),
    )
  })
})

describe('pushing all of it onto a live map', () => {
  let map: MockMap

  beforeEach(() => {
    resetMapLibreMock()
    map = new MockMap({})
    map.layerIds = [POI_LAYER_ID]
    map.sourceIds = [POI_SOURCE_ID]
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('registers every pin image once the style is up', () => {
    attachPoiIcons(map as never)
    map.emit('load')

    for (const { id } of buildPoiIcons()) expect(map.images.has(id)).toBe(true)
  })

  it('registers them at 2x, so a 60px badge is not drawn 60px wide', () => {
    attachPoiIcons(map as never)
    map.emit('load')

    expect(map.imageOptions.get(poiIconId('water', 'high'))).toEqual({ pixelRatio: 2 })
  })

  it('registers immediately when the style has already loaded', () => {
    // A style that finished before this ran will never fire `load` again.
    // Waiting on the event alone leaves the map permanently pinless on
    // exactly the fast path.
    map.styleLoaded = true

    attachPoiIcons(map as never)

    expect(map.images.size).toBeGreaterThan(0)
  })

  it('does nothing after detaching, even if load arrives late', () => {
    const detach = attachPoiIcons(map as never)

    detach()
    map.emit('load')

    expect(map.images.size).toBe(0)
    expect(map.listenerCount('load')).toBe(0)
  })

  it('honours a detach that lands part-way through the load event itself', () => {
    // Not hypothetical: MapLibre dispatches `load` to a snapshot of its
    // listeners, so an earlier handler unmounting the map screen removes this
    // one from the map and cannot remove it from the snapshot. Without the
    // detached check, that writes images onto a map React has already torn
    // down.
    let detach = () => {}
    map.on('load', () => detach())
    detach = attachPoiIcons(map as never)

    map.emit('load')

    expect(map.images.size).toBe(0)
  })

  it('does not re-register images a previous map screen already added', () => {
    // Images outlive a style reload and MapLibre throws on a duplicate id.
    // Every trip through the Downloads tab builds a new map, so this is the
    // ordinary path, not an edge case.
    map.styleLoaded = true
    attachPoiIcons(map as never)
    const addImage = vi.spyOn(map, 'addImage')

    attachPoiIcons(map as never)

    expect(addImage).not.toHaveBeenCalled()
    expect(map.images.size).toBe(buildPoiIcons().length)
  })

  it('pushes the POIs into the source as GeoJSON', () => {
    map.styleLoaded = true

    attachPoiData(map as never, [
      { id: 'w1', type: 'water', lat: 39.3, lon: -77.1, confidence: 'high' },
    ])

    expect(map.sourceData.get(POI_SOURCE_ID)).toEqual(
      poiFeatureCollection([
        { id: 'w1', type: 'water', lat: 39.3, lon: -77.1, confidence: 'high' },
      ]),
    )
  })

  it('applies the hidden set as a filter on the pin layer', () => {
    map.styleLoaded = true

    attachHiddenPoiTypes(map as never, new Set(['water']))

    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiTypeFilter(new Set(['water'])))
  })

  it('keeps the map alive when a write fails, and says so', () => {
    // These run inside React effects on the map screen. An exception here
    // would take the whole map down over a pin, which is the one outcome
    // worse than a missing pin.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    map.styleLoaded = true
    map.layerIds = []

    expect(() => attachHiddenPoiTypes(map as never, new Set(['water']))).not.toThrow()
    expect(warn).toHaveBeenCalled()
  })

  it('leaves no load listener behind when detached before the style loads', () => {
    for (const detach of [
      attachPoiIcons(map as never),
      attachPoiData(map as never, []),
      attachHiddenPoiTypes(map as never, new Set()),
    ]) {
      detach()
    }

    expect(map.listenerCount('load')).toBe(0)
  })
})
