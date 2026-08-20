import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createExpression, featureFilter } from '@maplibre/maplibre-gl-style-spec'
import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { POI_TYPES } from '../lib/config'
import { hiddenTypesFrom, onlyType, showAllTypes } from '../lib/waypointVisibility'
import {
  buildPoiIcons,
  POI_FALLBACK_COLOR,
  POI_PIN_SIZE,
  poiColor,
  poiIconId,
  siteMemberCombinations,
  UNKNOWN_POI_TYPE,
} from './poiIcons'
import { poiIconImages } from './poiIconImages'
import { SITE_ANCHOR_TYPES, SITE_MEMBERS_PROPERTY, siteMembersKey } from './poiSites'
import {
  attachPoiFilter,
  attachPoiData,
  attachPoiIcons,
  buildPoiDotLayer,
  buildPoiLayer,
  poiFeatureCollection,
  poiFilter,
  POI_DOT_COLOR_EXPRESSION,
  POI_DOT_LAYER_ID,
  POI_DOT_MIN_ZOOM,
  POI_DOT_RADIUS_EXPRESSION,
  POI_STALENESS_LAYER_ID,
  POI_ICON_EXPRESSION,
  POI_ICON_SIZE_EXPRESSION,
  POI_ID_PROPERTY,
  POI_LAYER_ID,
  POI_PIN_MIN_ZOOM,
  POI_SORT_KEY_EXPRESSION,
  POI_SOURCE_ID,
} from './poiLayers'
import { POI_PRIORITY } from './poiPriority'

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

describe('the dot rank', () => {
  it('is a CIRCLE layer, which is the entire mechanism', () => {
    // THE test in this file. MapLibre's collision engine is a property of
    // symbol layers; a circle participates in no placement pass, so every
    // feature renders at every camera. Changed to 'symbol' - which would look
    // like a harmless refactor and would typecheck - this layer starts
    // colliding, waypoints start disappearing again, and the only symptom is
    // that the map is quietly lying once more.
    expect(buildPoiDotLayer().type).toBe('circle')
  })

  it('reaches below the pin seam, because a dot makes no claim a seam protects', () => {
    // #603, reversing what this test used to assert. The seam is about whether
    // a PIN can say what it is without colliding; a dot says only "something is
    // here", so that argument never covered it - and holding both ranks at one
    // seam left the opening corridor view drawing the trail line and nothing
    // else. features/POI_VISIBILITY.md had this open as a question and it is
    // answered yes.
    //
    // The two ranks now stop in different places, deliberately, which is the
    // thing a later reader is most likely to "tidy" back into agreement.
    expect(buildPoiDotLayer().minzoom).toBe(POI_DOT_MIN_ZOOM)
    expect(POI_DOT_MIN_ZOOM).toBeLessThan(POI_PIN_MIN_ZOOM)
    expect(buildPoiLayer().minzoom).toBe(POI_PIN_MIN_ZOOM)
  })

  it('shrinks to a stipple at the corridor view rather than keeping its seam size', () => {
    // What makes the line above honest. At z4 the corridor's waypoints sit
    // within a few hundred pixels of trail line, so a dot sized for the seam
    // would draw a solid bar and claim the trail is one continuous place.
    const ramp = POI_DOT_RADIUS_EXPRESSION
    const atDotFloor = ramp[ramp.indexOf(POI_DOT_MIN_ZOOM) + 1] as number
    const atSeam = ramp[ramp.indexOf(POI_PIN_MIN_ZOOM) + 1] as number

    expect(atDotFloor).toBeLessThan(atSeam)
    expect(atDotFloor).toBeGreaterThan(0)
  })

  it('reads the same source as the pins, which is what makes it site-correct', () => {
    // poiFeatureCollection already emits one feature per SITE, so sharing the
    // source means a privy riding its shelter's pin does not also get a dot
    // 40 m away claiming to be a second place. Nothing else enforces that.
    // `source` off the union, which also holds background layers that have
    // none - narrowed rather than asserted away, so this still fails if either
    // layer ever stops being source-backed.
    const sourceOf = (layer: LayerSpecification): string | undefined =>
      'source' in layer ? layer.source : undefined

    expect(sourceOf(buildPoiDotLayer())).toBe(POI_SOURCE_ID)
    expect(sourceOf(buildPoiDotLayer())).toBe(sourceOf(buildPoiLayer()))
  })

  it('wears its category accent, from the same table the pin uses', () => {
    for (const type of POI_TYPES) {
      expect(evaluate(POI_DOT_COLOR_EXPRESSION, poi(type))).toBe(poiColor(type))
    }
  })

  it('lands an unknown type on the fallback rather than on nothing', () => {
    expect(evaluate(POI_DOT_COLOR_EXPRESSION, poi('yurt'))).toBe(POI_FALLBACK_COLOR)
  })

  it('stays small enough not to compete with a pin', () => {
    const atSeam = evaluate(
      POI_DOT_RADIUS_EXPRESSION,
      poi('water'),
      POI_PIN_MIN_ZOOM,
    ) as number

    // Diameter against the pin's whole 38px. A dot that reads as a small pin
    // is worse than no dot: it claims to say what is there, which is exactly
    // what it cannot do.
    expect(atSeam * 2).toBeLessThan(POI_PIN_SIZE / 2)
  })

  it('grows with the camera, like the pins do', () => {
    const far = evaluate(
      POI_DOT_RADIUS_EXPRESSION,
      poi('water'),
      POI_PIN_MIN_ZOOM,
    ) as number
    const near = evaluate(POI_DOT_RADIUS_EXPRESSION, poi('water'), 16) as number

    expect(far).toBeLessThan(near)
  })
})

describe('density', () => {
  it('draws no pins at all above the whole-corridor view', () => {
    // The opening camera frames 2,197 miles. Eight hundred pins on it is a
    // texture, not information, and letting the collision engine thin them
    // would answer "which of these matters" by geometry.
    //
    // The seam is MEASURED - pipeline/spike_poi_seam.py - so this asserts the
    // floor exists rather than restating the figure, which would be one number
    // in two places.
    //
    // `>= 9` rather than `> 9`: the seam is now 9, the same number as the
    // original hard floor but reached from the opposite direction - that floor
    // drew nothing below itself, this one hands over to the corridor view. 9
    // is the bound either way, because below it the corridor is a texture
    // (POI_MIN_ZOOM's own argument, which was right about that).
    expect(buildPoiLayer().minzoom).toBe(POI_PIN_MIN_ZOOM)
    expect(POI_PIN_MIN_ZOOM).toBeGreaterThanOrEqual(9)
  })

  it('leaves the collision engine switched on, which is the whole density story', () => {
    const layout = buildPoiLayer().layout as Record<string, unknown>

    expect(layout['icon-allow-overlap']).toBe(false)
  })

  it('grows the pins as the hiker zooms in', () => {
    const far = evaluate(
      POI_ICON_SIZE_EXPRESSION,
      poi('water'),
      POI_PIN_MIN_ZOOM,
    ) as number
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

  it('places a vista behind every other category, however many of them there are', () => {
    // The densest layer ATC publishes: 1,223 vistas against 2,532 POIs of
    // every other kind put together. Ranked anywhere but last, the pins that
    // survive a crowded ridge are decided by how many of them there are
    // rather than by what a hiker needs - and losing a spring to an overlook
    // is exactly the trade this ordering exists to refuse.
    const viewpoint = evaluate(POI_SORT_KEY_EXPRESSION, poi('viewpoint')) as number

    for (const type of POI_TYPES) {
      if (type !== 'viewpoint') {
        expect(evaluate(POI_SORT_KEY_EXPRESSION, poi(type))).toBeLessThan(viewpoint)
      }
    }
  })
})

describe('the pin layer', () => {
  it('asks for no text, because there is no font to render it with offline', () => {
    // The OFFLINE style declares no `glyphs` URL - it cannot, there is no
    // network on a mountain. MapLibre draws icons happily without one and
    // cannot draw a single character of a label. A `text-field` added here
    // would fail at the top of a hill and nowhere else.
    //
    // The live sheet does declare one, for its own OSM labels, and that is
    // exactly why the pin layer must not lean on it: pins are drawn on both
    // backgrounds, and a label that renders in town and vanishes on the ridge
    // is worse than one that was never there.
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

  it('carries the attributes the style matches on, and the id to look up by', () => {
    const [, shelter] = poiFeatureCollection(pois).features

    expect(shelter.id).toBe('s1')
    expect(shelter.properties).toEqual({
      poi_type: 'shelter',
      confidence: 'low',
      [POI_ID_PROPERTY]: 's1',
      // Always present, empty where the pin carries nothing (#524). Asserted
      // exactly rather than loosely, which is why this test had to change when
      // the property arrived - a `toMatchObject` here would have let a fourth
      // property appear unnoticed.
      [SITE_MEMBERS_PROPERTY]: '',
      // The day-one defaults with no note roll-up supplied: no ring, no fade
      // (#256's maintainer decision, lib/stalenessDisplay.ts).
      staleness_ring: 'none',
      staleness_faded: false,
    })
  })

  it('carries the ring and fade the staleness lookup answers, per waypoint', () => {
    const collection = poiFeatureCollection(pois, {}, (poiId) =>
      poiId === 'w1'
        ? { ring: 'faint-invite', faded: false }
        : { ring: 'grey-dotted', faded: true },
    )
    const [water, shelter] = collection.features

    expect(water.properties.staleness_ring).toBe('faint-invite')
    expect(water.properties.staleness_faded).toBe(false)
    expect(shelter.properties.staleness_ring).toBe('grey-dotted')
    expect(shelter.properties.staleness_faded).toBe(true)
  })

  // One pin per site (#524). The mechanism lives in map/poiSites.ts and is
  // tested there; what only this file can catch is the source failing to apply
  // it, which would leave every member competing for a box exactly as before.
  it('resolves every site pin to an image that was actually registered', () => {
    // THE FAILURE THIS CATCHES, and the reason it EVALUATES the expression
    // rather than reading it: MapLibre draws a missing image as NOTHING, logging
    // once per tile. A site pin asking for an id nobody built is a shelter that
    // vanishes from the map entirely - strictly worse than the privy problem
    // #524 is fixing.
    for (const type of SITE_ANCHOR_TYPES) {
      for (const members of siteMemberCombinations()) {
        for (const confidence of ['high', 'low'] as const) {
          const resolved = evaluate(POI_ICON_EXPRESSION, {
            ...poi(type, confidence),
            [SITE_MEMBERS_PROPERTY]: siteMembersKey(members),
          })

          const label = `${type}/${confidence}/${members.join('+')}`
          expect(REGISTERED_ICON_IDS, label).toContain(resolved)
          // And it must be the SITE image, not merely A registered one. Asserting
          // only "registered" passed while the expression resolved every site pin
          // to the PLAIN icon - a shelter carrying a privy drawing a bare shelter
          // pin and saying nothing, which is the failure this whole change exists
          // to prevent. Caught by mutating the arm, not by reading it.
          expect(resolved, label).toBe(poiIconId(type, confidence, members))
          expect(resolved, label).not.toBe(poiIconId(type, confidence))
        }
      }
    }
  })

  it('still resolves a pin carrying nothing to the plain image', () => {
    const resolved = evaluate(POI_ICON_EXPRESSION, {
      ...poi('shelter', 'high'),
      [SITE_MEMBERS_PROPERTY]: '',
    })

    expect(resolved).toBe(poiIconId('shelter', 'high'))
  })

  it('drops a site member from the source rather than letting it lose a collision', () => {
    const collection = poiFeatureCollection([
      {
        id: 'shelter',
        type: 'shelter',
        lat: 39,
        lon: -77,
        confidence: 'high',
        siteId: 'site_1',
        siteRole: 'anchor',
      },
      {
        id: 'privy',
        type: 'privy',
        lat: 39.0004,
        lon: -77,
        confidence: 'high',
        siteId: 'site_1',
        siteRole: 'member',
      },
    ])

    expect(collection.features.map((f) => f.id)).toEqual(['shelter'])
  })

  it('tells the style what the surviving pin is carrying', () => {
    const collection = poiFeatureCollection([
      {
        id: 'shelter',
        type: 'shelter',
        lat: 39,
        lon: -77,
        confidence: 'high',
        siteId: 'site_1',
        siteRole: 'anchor',
      },
      {
        id: 'privy',
        type: 'privy',
        lat: 39.0004,
        lon: -77,
        confidence: 'high',
        siteId: 'site_1',
        siteRole: 'member',
      },
      {
        id: 'water',
        type: 'water',
        lat: 39.0005,
        lon: -77,
        confidence: 'low',
        siteId: 'site_1',
        siteRole: 'member',
      },
    ])

    expect(collection.features[0].properties[SITE_MEMBERS_PROPERTY]).toBe('privy+water')
  })

  it('puts the POI id somewhere a tap can still read it', () => {
    // The gotcha, and the reason the id is duplicated into the properties at
    // all: MapLibre runs a string feature id through parseInt (FeatureWrapper,
    // maplibre-gl 6), so every id the pipeline publishes reaches a rendered
    // feature as NaN. A pin whose id only lived in the GeoJSON `id` field
    // could be drawn perfectly and never be identified again.
    const published = [
      { id: 'atc_shelters:0f8a-4c11', type: 'shelter', lat: 44, lon: -70 },
    ].map((poi) => ({ ...poi, confidence: 'high' as const }))

    const [feature] = poiFeatureCollection(published).features

    expect(Number.parseInt(feature.id, 10)).toBeNaN()
    expect(feature.properties[POI_ID_PROPERTY]).toBe('atc_shelters:0f8a-4c11')
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
      poiFilter(new Set(hidden)) as never,
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
    expect(poiFilter(new Set(['water', 'campsite']))).toEqual(
      poiFilter(new Set(['campsite', 'water'])),
    )
  })
})

// The source and the filter TOGETHER, which is the only place this bug is
// visible (#607). Neither half can catch it alone: the composition can be right
// about which POI carries the pin while the filter takes that pin off the map,
// and the filter can be right about which types survive while the source never
// offered the privy in the first place. What is asserted here is what reaches
// the hiker's screen.
describe('filtering the legend down to one category', () => {
  const SITE = [
    {
      id: 'shelter',
      type: 'shelter',
      lat: 39,
      lon: -77,
      confidence: 'high' as const,
      siteId: 'site_1',
      siteRole: 'anchor',
    },
    {
      id: 'privy',
      // 42 m from its shelter, which is the median in features/POI_SITES.md and
      // the reason it cannot be drawn below z16 while it competes for a box.
      type: 'privy',
      lat: 39.0004,
      lon: -77,
      confidence: 'high' as const,
      siteId: 'site_1',
      siteRole: 'member',
    },
  ]

  function drawnPins(shown: string[]): string[] {
    const hiddenTypes = hiddenTypesFrom(shown)
    const { filter } = featureFilter(poiFilter(hiddenTypes) as never, 'layers[0].filter')

    return poiFeatureCollection(SITE, { hiddenTypes })
      .features.filter((feature) =>
        filter(
          { zoom: 14 } as never,
          { properties: feature.properties, type: 1 } as never,
          null as never,
        ),
      )
      .map((feature) => feature.id)
  }

  it('draws the privy once its shelter has been filtered out', () => {
    // THE REGRESSION. Before this, both halves fired at once and the map drew
    // NOTHING: the privy was removed from the source as riding a shelter pin,
    // and the shelter pin was removed by the filter. Over the real corridor that
    // is 284 of 316 privies gone from the one control built to find them.
    expect(drawnPins(onlyType('privy'))).toEqual(['privy'])
  })

  it('still draws the shelter, and only the shelter, when nothing is hidden', () => {
    expect(drawnPins(showAllTypes())).toEqual(['shelter'])
  })

  it('draws the shelter and not the privy when only shelters are asked for', () => {
    // The other direction, and it must still fold: the privy is not promoted
    // just because a filter is in force, only because the pin it rides has gone.
    expect(drawnPins(onlyType('shelter'))).toEqual(['shelter'])
  })

  it('resolves the promoted pin to an image that was actually registered', () => {
    // A promoted member is asked for by an expression built for anchors. A privy
    // is not a SITE_ANCHOR_TYPE, so it has no member variants - and an id nobody
    // built draws as nothing at all, which would turn this fix into the same
    // blank map by another route.
    const hiddenTypes = hiddenTypesFrom(onlyType('privy'))
    const [promoted] = poiFeatureCollection(SITE, { hiddenTypes }).features

    const resolved = evaluate(POI_ICON_EXPRESSION, promoted.properties)

    expect(REGISTERED_ICON_IDS).toContain(resolved)
    expect(resolved).toBe(poiIconId('privy', 'high'))
  })
})

describe('the "Verified?" filter', () => {
  function passes(
    confidence: 'high' | 'low',
    verifiedOnly: boolean,
    hidden: string[] = [],
  ): boolean {
    const { filter } = featureFilter(
      poiFilter(new Set(hidden), verifiedOnly) as never,
      'layers[0].filter',
    )
    return filter(
      { zoom: 14 } as never,
      { properties: poi('water', confidence), type: 1 } as never,
      null as never,
    )
  }

  it('draws both confidences while it is off', () => {
    // Off is the default, and deliberately: an unconfirmed spring is still the
    // best information anyone has about that spring.
    expect(passes('high', false)).toBe(true)
    expect(passes('low', false)).toBe(true)
  })

  it('drops exactly the unverified pins while it is on', () => {
    expect(passes('high', true)).toBe(true)
    expect(passes('low', true)).toBe(false)
  })

  it('composes with the hidden categories rather than replacing them', () => {
    // Two controls, one filter. A verified spring in a hidden category stays
    // hidden - if these were two filters the second write would win and the
    // legend's category toggles would silently stop working.
    expect(passes('high', true, ['water'])).toBe(false)
    expect(passes('high', false, ['water'])).toBe(false)
  })

  it('keeps one expression shape whether it is on or off', () => {
    // Same reasoning as the empty hidden set above: "showing everything" must
    // not be a second code path that can drift from the one doing the work.
    const off = poiFilter(new Set(), false) as unknown[]
    const on = poiFilter(new Set(), true) as unknown[]

    expect(off[0]).toBe('all')
    expect(on[0]).toBe('all')
    expect(off).toHaveLength(on.length)
  })
})

describe('pushing all of it onto a live map', () => {
  let map: MockMap

  beforeEach(() => {
    resetMapLibreMock()
    map = new MockMap({})
    // All three ranks, because the real style carries all three (#597, and
    // the staleness rings with #759) and attachPoiFilter waits for every one
    // before writing. A stub holding only the pin layer would make every
    // filter test here pass by never running.
    map.layerIds = [POI_LAYER_ID, POI_DOT_LAYER_ID, POI_STALENESS_LAYER_ID]
    map.sourceIds = [POI_SOURCE_ID]
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  /**
   * The images, once they have been built.
   *
   * Every assertion about a registered pin has to go through this since #857,
   * because the rasterising moved off the main thread (map/poiIconImages.ts)
   * and `attachPoiIcons` now returns before a single image exists. Awaiting
   * the module's own promise is enough to order this after the registration:
   * `attachPoiIcons` put its continuation on that promise before the test put
   * this one, and a promise runs its continuations in the order they were
   * added.
   *
   * jsdom has no Worker, so what is being awaited here is a synchronous build
   * behind a resolved promise - which is the fallback path the app also takes
   * where a worker cannot be constructed.
   */
  const iconsBuilt = () => poiIconImages()

  it('registers every pin image once the style is up', async () => {
    attachPoiIcons(map as never)
    map.emit('load')
    await iconsBuilt()

    for (const { id } of buildPoiIcons()) expect(map.images.has(id)).toBe(true)
  })

  it('registers them at 2x, so a 60px badge is not drawn 60px wide', async () => {
    attachPoiIcons(map as never)
    map.emit('load')
    await iconsBuilt()

    expect(map.imageOptions.get(poiIconId('water', 'high'))).toEqual({ pixelRatio: 2 })
  })

  it('registers without a further style event when the style has already loaded', async () => {
    // A style that finished before this ran will never fire `load` again.
    // Waiting on the event alone leaves the map permanently pinless on
    // exactly the fast path.
    map.styleLoaded = true

    attachPoiIcons(map as never)
    await iconsBuilt()

    expect(map.images.size).toBeGreaterThan(0)
  })

  it('does nothing after detaching, even if the images are still being built', async () => {
    // The window this opens (#857): a detach can now land while the rasteriser
    // is still running, which is before there is any style listener to remove.
    // Nothing is registered on a map the shell has already let go of.
    const detach = attachPoiIcons(map as never)

    detach()
    await iconsBuilt()

    expect(map.images.size).toBe(0)
  })

  it('does nothing after detaching, even if the layer arrives late', async () => {
    map.layerIds = []
    const detach = attachPoiIcons(map as never)
    await iconsBuilt()

    detach()
    map.layerIds = [POI_LAYER_ID]
    map.emit('styledata')

    expect(map.images.size).toBe(0)
    expect(map.listenerCount('styledata')).toBe(0)
  })

  it('honours a detach that lands part-way through the style event itself', async () => {
    // Not hypothetical: MapLibre dispatches to a snapshot of its listeners, so
    // an earlier handler unmounting the map screen removes this one from the
    // map and cannot remove it from the snapshot. Without the detached check,
    // that writes images onto a map React has already torn down.
    map.layerIds = []
    let detach = () => {}
    map.on('styledata', () => detach())
    detach = attachPoiIcons(map as never)
    await iconsBuilt()

    map.layerIds = [POI_LAYER_ID]
    map.emit('styledata')

    expect(map.images.size).toBe(0)
  })

  it('still lands the POIs when the style is busy at the moment they arrive', () => {
    // The bug (#129). The gate asked whether the WHOLE style was loaded and
    // waited on `load` when it was not - but `load` fires exactly once, while
    // isStyleLoaded() goes false again on every tile fetch, every setData and
    // every source reload. POIs arrive from IndexedDB once. One landing in
    // such a window registered a listener for an event that had already
    // happened, and the pins never appeared at all, for the life of the map,
    // while the legend went on listing what was missing.
    map.sourceIds = []
    map.emit('load')
    map.styleLoaded = false

    const pois = [
      { id: 'w1', type: 'water', lat: 39.3, lon: -77.1, confidence: 'high' as const },
    ]
    attachPoiData(map as never, pois)
    expect(map.sourceData.get(POI_SOURCE_ID)).toBeUndefined()

    map.sourceIds = [POI_SOURCE_ID]
    map.emit('styledata')

    expect(map.sourceData.get(POI_SOURCE_ID)).toEqual(poiFeatureCollection(pois))
  })

  it('does not re-register images a previous map screen already added', async () => {
    // Images outlive a style reload and MapLibre throws on a duplicate id.
    // Every trip through the More tab builds a new map, so this is the
    // ordinary path, not an edge case.
    map.styleLoaded = true
    attachPoiIcons(map as never)
    await iconsBuilt()
    const addImage = vi.spyOn(map, 'addImage')

    attachPoiIcons(map as never)
    await iconsBuilt()

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

    attachPoiFilter(map as never, new Set(['water']))

    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiFilter(new Set(['water'])))
  })

  it('carries the "Verified?" toggle onto the same layer filter', () => {
    map.styleLoaded = true

    attachPoiFilter(map as never, new Set(['water']), true)

    expect(map.filters.get(POI_LAYER_ID)).toEqual(poiFilter(new Set(['water']), true))
  })

  it('hides a type on ALL ranks, so no dot or ring outlives the pin it belonged to', () => {
    // The failure this exists for is silent: hide privies, the pins go, and a
    // stipple of privy dots stays behind saying the legend is lying. Nothing
    // throws, nothing logs, and the only symptom is on a screen.
    map.styleLoaded = true

    attachPoiFilter(map as never, new Set(['privy']), true)

    const expected = poiFilter(new Set(['privy']), true)
    expect(map.filters.get(POI_LAYER_ID)).toEqual(expected)
    expect(map.filters.get(POI_DOT_LAYER_ID)).toEqual(expected)
    // The ring rank takes the same legend filter AND keeps its own
    // membership clause - a hidden category's rings go with its pins, and a
    // shown one still only rings what has a ring to wear.
    expect(map.filters.get(POI_STALENESS_LAYER_ID)).toEqual([
      'all',
      expected,
      ['!=', ['get', 'staleness_ring'], 'none'],
    ])
  })

  it('waits for both ranks rather than filtering whichever arrived first', () => {
    // A style mid-reload can hold one layer and not the other. Writing to the
    // one that exists would leave the two ranks showing different categories
    // until something else happened to trigger a re-filter.
    map.styleLoaded = true
    map.layerIds = [POI_LAYER_ID]

    attachPoiFilter(map as never, new Set(['privy']))

    expect(map.filters.has(POI_LAYER_ID)).toBe(false)
  })

  it('keeps the map alive when a write fails, and says so', () => {
    // These run inside React effects on the map screen. An exception here
    // would take the whole map down over a pin, which is the one outcome
    // worse than a missing pin.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    // A layer that IS there and still refuses the write - a style swapped out
    // from under the call. A layer that is merely absent is a different state
    // now: it means "not yet", and waiting is the right answer to it.
    vi.spyOn(map, 'setFilter').mockImplementation(() => {
      throw new Error('style replaced mid-write')
    })

    expect(() => attachPoiFilter(map as never, new Set(['water']))).not.toThrow()
    expect(warn).toHaveBeenCalled()
  })

  it('leaves no style listener behind when detached before the style loads', () => {
    // The seeded layerIds from beforeEach would let every attach succeed
    // immediately, registering nothing - which is how this test spent weeks
    // unable to fail (#175). An empty style is what "before the style
    // loads" actually means, and is what forces the styledata wait this
    // detach test exists to clean up after.
    map.layerIds = []
    const detachers = [
      attachPoiIcons(map as never),
      attachPoiData(map as never, []),
      attachPoiFilter(map as never, new Set()),
    ]

    // Guards the guard: if nothing registered, the assertion below passes
    // on a detach that does nothing.
    expect(map.listenerCount('styledata')).toBeGreaterThan(0)

    for (const detach of detachers) detach()

    expect(map.listenerCount('styledata')).toBe(0)
    expect(map.listenerCount('load')).toBe(0)
  })
})
