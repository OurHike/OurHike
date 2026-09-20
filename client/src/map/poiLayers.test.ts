import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  createExpression,
  featureFilter,
  validateStyleMin,
} from '@maplibre/maplibre-gl-style-spec'
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
  BASE_PADDING_PX,
  CROWDED_NEIGHBOURS,
  CROWDING_PROPERTY,
  POI_ICON_PADDING_EXPRESSION,
  QUIET_NEIGHBOURS,
} from './poiCrowding'
import {
  attachPoiFilter,
  attachPoiData,
  attachPoiIcons,
  buildPoiDotLayer,
  buildPoiLayer,
  buildPoiStalenessLayer,
  NO_RING,
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
  POI_NAME_PROPERTY,
  POI_LAYER_ID,
  POI_PIN_MIN_ZOOM,
  POI_SORT_KEY_EXPRESSION,
  POI_SOURCE_ID,
  SECONDARY_POI_SCALE,
  buildPoiSource,
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

/** `source` off the union, which also holds background layers that have none. */
function sourceOfLayer(layer: LayerSpecification): string | undefined {
  return 'source' in layer ? layer.source : undefined
}

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

  it('reaches every zoom, so no waypoint is ever undrawn (#1585)', () => {
    // THE THIRD TURN OF THIS TEST, and the history is the point of pinning it:
    // both ranks at the seam (pre-#603) left the opening view empty; the dot
    // rank at z0 (#603) put a stipple on it; #1135 floored both at the seam
    // again, because #1097's network waypoints were being stippled onto trails
    // the view refused to draw. #1585 reverses that once more, on the
    // maintainer's rule that the map may never hide a waypoint from a hiker -
    // and #1135's objection is answered rather than overruled, because #1135
    // itself put every organization's trails on this camera.
    //
    // FOURTH TURN, 2026-09-20: back to the seam, on the maintainer's own
    // reading of the carry frames - "We can keep a seam, and make it at zoom
    // 7. Yes the POI's can be hidden above there." So the two ranks share one
    // floor and the corridor view carries no waypoint mark of any kind.
    //
    // ONE CONSTANT, NOT TWO THAT AGREE. A second number here that happened to
    // equal the pins' is how a band of ground with dots and no pins - or the
    // reverse - gets built by accident.
    expect(buildPoiDotLayer().minzoom).toBe(POI_DOT_MIN_ZOOM)
    expect(POI_DOT_MIN_ZOOM).toBe(POI_PIN_MIN_ZOOM)
    expect(buildPoiLayer().minzoom).toBe(POI_PIN_MIN_ZOOM)
  })

  it('opens its radius ramp at the seam, with no stop below it to be degenerate', () => {
    // The 1.2 px corridor stop went with the band it sized (2026-09-20). This
    // is not housekeeping: MapLibre requires an `interpolate`'s stops to
    // ASCEND STRICTLY, so once both floors converged on the seam, a ramp that
    // still opened at POI_DOT_MIN_ZOOM would have had two stops at one zoom
    // and the engine would have refused the whole style.
    const ramp = POI_DOT_RADIUS_EXPRESSION
    const stops: number[] = []
    for (let i = 3; i < ramp.length; i += 2) stops.push(ramp[i] as number)

    expect(stops[0]).toBe(POI_PIN_MIN_ZOOM)
    for (let i = 1; i < stops.length; i += 1) {
      expect(stops[i]).toBeGreaterThan(stops[i - 1])
    }
    // And it grows with the zoom, which is the ramp's only other job.
    expect(ramp[ramp.length - 1] as number).toBeGreaterThan(ramp[4] as number)
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
  // THE RULE THIS BLOCK EXISTS FOR, in the maintainer's words on 2026-09-18:
  // "Don't auto hide the POIs ever. It's a safety thing, hikers need to know
  // that info."
  //
  // The first build of #1585 broke it. Reaching for a way to put a resupply
  // carry's shelters and water on a hundred-mile screen, it gated the map by
  // TYPE below the seam - three categories drawn, six not - so a hiker at z8
  // saw no campsite, no privy, no parking and no crossing, and nothing on the
  // screen said they were there. A hiker cannot ask about a mark that is not
  // drawn. That is the failure mode CLAUDE.md's "four ways this app can hurt
  // somebody" is written against, and none of it looked wrong from the outside.
  //
  // So: the seam decides WHERE waypoints start and never WHICH. These tests are
  // the difference between those two sentences, held where a future change has
  // to walk past them.
  describe('the layers MapLibre actually gets', () => {
    it('is a style MapLibre’s own validator accepts, pins included', () => {
      // THE CHECK THAT DID NOT EXIST, and #1585 is why it does now. The only
      // spec validation in this suite was map/liveTopo.test.ts's, over the
      // BACKGROUND style - so the waypoint layers, which carry every
      // hand-written expression in this file, were read by nothing that reads
      // them the way MapLibre will.
      //
      // It matters most for `icon-size`. It became data-driven on #1585 (a pin
      // is drawn at its category's size), and a zoom `interpolate` may carry a
      // data expression in each OUTPUT but never in its input. Getting that
      // backwards type-checks, passes every other test in this file, and
      // renders no pins at all.
      const style = {
        version: 8 as const,
        sources: { [POI_SOURCE_ID]: buildPoiSource() },
        layers: [buildPoiDotLayer(), buildPoiStalenessLayer(), buildPoiLayer()],
      }

      expect(validateStyleMin(style as never)).toEqual([])
    })

    it('sizes a full-size category above the tail at every stop of the ramp', () => {
      // The tiers, read through the expression rather than off the constants,
      // so a stop that lost its `match` fails here rather than looking right.
      for (const zoom of [POI_PIN_MIN_ZOOM, 9, 11, 13, 16, 22]) {
        const water = evaluate(POI_ICON_SIZE_EXPRESSION, poi('water'), zoom) as number
        const vista = evaluate(POI_ICON_SIZE_EXPRESSION, poi('viewpoint'), zoom) as number

        expect(water).toBeGreaterThan(vista)
        expect(vista / water).toBeCloseTo(SECONDARY_POI_SCALE, 5)
        // And the tail is still a pin somebody can see, not a way of hiding it:
        // poiIcons.test.ts holds a 7 px floor on a glyph, and the glyph is
        // about 47% of the pin.
        expect(vista * POI_PIN_SIZE * 0.46).toBeGreaterThan(7)
      }
    })
  })

  describe('the map never hides a category of its own accord (#1585)', () => {
    function drawnAt(zoom: number, type: string, hidden: string[] = []): boolean {
      const { filter } = featureFilter(
        poiFilter(new Set(hidden)) as never,
        'layers[0].filter',
      )
      return filter(
        { zoom } as never,
        { properties: poi(type), type: 1 } as never,
        null as never,
      )
    }

    // EVERY zoom a waypoint can be drawn at, and the ones BELOW the seam are
    // the point of the list: down there the dot rank is the only thing saying
    // a place is there at all, and it is exactly where the first build of
    // #1585 hid six categories. A gate that bit in one band only is how that
    // shipped - it looked right at every zoom anybody happened to check.
    const EVERY_ZOOM = [
      0,
      4.9, // the opening camera, the whole corridor
      6,
      7,
      POI_PIN_MIN_ZOOM,
      8,
      9,
      10,
      12,
      14,
      16,
      18,
      22,
    ]

    it('draws every published category at every zoom, including below the seam', () => {
      for (const zoom of EVERY_ZOOM) {
        for (const type of POI_TYPES) {
          expect({ zoom, type, drawn: drawnAt(zoom, type) }).toEqual({
            zoom,
            type,
            drawn: true,
          })
        }
      }
    })

    it('carries no zoom term at all, so no zoom can ever decide a category', () => {
      // The strongest form of the rule, and the one that cannot be satisfied by
      // a gate that merely happens to be off today: `zoom` does not appear in
      // this filter. A type clause keyed on the camera is the defect itself,
      // not a tuning of it.
      expect(JSON.stringify(poiFilter(new Set()))).not.toContain('zoom')
      expect(JSON.stringify(poiFilter(new Set(['privy']), true))).not.toContain('zoom')
    })

    it('takes a category off the map only where the hiker asked for it', () => {
      // The one honest subtraction, and it is the hiker's own (#530, #865): a
      // row they switched off. Asserted beside the rule above so the two are
      // read together - "never hides" is about the MAP deciding, never about a
      // control the hiker can see and reverse.
      for (const zoom of EVERY_ZOOM) {
        expect(drawnAt(zoom, 'privy', ['privy'])).toBe(false)
        expect(drawnAt(zoom, 'shelter', ['privy'])).toBe(true)
      }
    })

    it('gives both ranks the same filter, so a category cannot be on one and off the other', () => {
      // attachPoiFilter computes it once and sets it on both; this is that
      // property from the layers' side. A type drawn as a dot and refused a pin
      // - or the reverse - would be the same hiding, one rank down.
      const hidden = new Set(['viewpoint'])
      const pins = poiFilter(hidden)
      const dots = poiFilter(hidden)

      expect(pins).toEqual(dots)
      expect(sourceOfLayer(buildPoiDotLayer())).toBe(sourceOfLayer(buildPoiLayer()))
    })

    it('never leaves a zoom where a waypoint is neither a pin nor a dot', () => {
      // "A pin or a dot and never neither" (#597) is the promise, and what
      // keeps it is that the dot rank's floor is never ABOVE the pin rank's.
      // The other way round is a band of ground where a waypoint that loses
      // its collision has nothing left to be drawn as - which is the deletion
      // the two ranks exist to end.
      expect(POI_DOT_MIN_ZOOM).toBeLessThanOrEqual(POI_PIN_MIN_ZOOM)
      expect(buildPoiDotLayer().minzoom).toBeLessThanOrEqual(
        buildPoiLayer().minzoom as number,
      )
    })

    it('puts every category into the source, so the filter is the only gate there is', () => {
      // One rank up from the filter: a type dropped on the way INTO the source
      // would be hidden with no filter to blame, and nothing above would catch
      // it. poiFeatureCollection emits one feature per drawn mark, whatever it
      // is.
      const one = POI_TYPES.map((type, index) => ({
        id: `p${index}`,
        type,
        // Degrees apart, so site folding has nothing to fold and the count is
        // the collection's own answer rather than a fold's.
        lat: 35 + index,
        lon: -84 + index,
        confidence: 'high' as const,
      }))

      const drawn = poiFeatureCollection(one).features

      expect(drawn.map((feature) => feature.properties.poi_type).sort()).toEqual(
        [...POI_TYPES].sort(),
      )
    })

    it('sits at the zoom a resupply carry fits, which is what moved it (#1585)', () => {
      // Measured on the calibrated mile axis: 100-120 trail miles fit a
      // 390x700 phone at a median z8.1-8.4, and fewer than one window in ten
      // fits at 9 (the constant carries the table). Held as a bound rather than
      // as the figure, so re-measuring against fresher data can move it without
      // this test becoming a second home for the number.
      expect(POI_PIN_MIN_ZOOM).toBeLessThanOrEqual(8)
      // And not so far out that the corridor view stops being a view of the
      // corridor: below the opening camera there is no walk to be about.
      expect(POI_PIN_MIN_ZOOM).toBeGreaterThan(5)
    })
  })

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
    // `>= 7` since the maintainer set the seam there on 2026-09-20, having
    // seen the carry frames. What this still holds is that a floor EXISTS and
    // sits well above the opening camera's z4.9, which is the whole of the
    // "eight hundred pins is a texture" argument; the block below holds the
    // other half, that the floor never decides WHICH categories draw.
    expect(POI_PIN_MIN_ZOOM).toBeGreaterThanOrEqual(7)
    // Measured, from the calibrated mile axis: nine in ten 120-mile windows
    // fit at z7.61 or nearer, so a seam above 7.6 stops clearing every carry.
    expect(POI_PIN_MIN_ZOOM).toBeLessThanOrEqual(7.6)
  })

  it('never lets the collision engine drop a pin, and never lets a pin drop anything else', () => {
    // THE test in this file since #1585, and the reverse of what it held
    // before. `icon-allow-overlap: false` was "the entire density story": at
    // z9 it dropped 59% of the waypoints reaching this layer and at the seam
    // 81%, each of them keeping a 2.5 px dot. The maintainer's rule of
    // 2026-09-18 is that the map may never take a mark away, so overlap is
    // allowed and every pin is drawn.
    //
    // `icon-ignore-placement` is the other half and is not decoration: a pin
    // that was drawn but still took part in placement would go on evicting
    // the trail names, waypoint labels and badges around it, and "hide
    // nothing" would have held for pins by hiding the names instead.
    const layout = buildPoiLayer().layout as Record<string, unknown>

    expect(layout['icon-allow-overlap']).toBe(true)
    expect(layout['icon-ignore-placement']).toBe(true)
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

  it('lets each pin claim its own air, which a flat padding could not', () => {
    // #1536. It used to be a flat 2 for every pin on every map. The corridor
    // and a city are crowded at DIFFERENT zooms - a blanket 24 costs the A.T.
    // half its pins at z9 - so the only scope that leaves the trail alone is
    // per-feature, and `icon-padding` being data-driven is what permits it.
    const layout = buildPoiLayer().layout as Record<string, unknown>

    expect(layout['icon-padding']).toBe(POI_ICON_PADDING_EXPRESSION)
    expect(
      evaluate(POI_ICON_PADDING_EXPRESSION, { [CROWDING_PROPERTY]: QUIET_NEIGHBOURS }),
    ).toBe(BASE_PADDING_PX)
    expect(
      evaluate(POI_ICON_PADDING_EXPRESSION, { [CROWDING_PROPERTY]: CROWDED_NEIGHBOURS }),
    ).toBeGreaterThan(BASE_PADDING_PX)
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
      // The name map/poiLabels.ts draws (#1194), and empty here because this
      // fixture's MapPoint carries none. Always a string for the same reason
      // the site key above always is: the label layer's filter is then one
      // comparison rather than a `coalesce`.
      [POI_NAME_PROPERTY]: '',
      // How crowded the ground is, which `icon-padding` interpolates on
      // (#1536, map/poiCrowding.ts). Zero here because this fixture's
      // waypoints are degrees apart; always a number for the same reason the
      // two strings above are always strings.
      [CROWDING_PROPERTY]: 0,
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

  it('folds a site member onto its anchor, so one place is one pin', () => {
    // REVERSED BACK, 2026-09-20, and the round trip is worth pinning because
    // both directions had a reason. For two days this held the opposite: the
    // privy drew its own pin at its own coordinate, on the rule that the map
    // may never take a mark away. What that actually drew was four pins on
    // one shelter - the privy sits a median 42 m from it, which is the same
    // pixel at every zoom a hiker walks at.
    //
    // The maintainer, having seen it: "The grouping of locations was working
    // before. You need to nest the Shelters, Campsites, Privies & Water as we
    // did before this PR."
    //
    // The member is NOT deleted, which is what lets this stand beside the
    // never-hide rule: it rides the anchor's pin as a badge and is listed on
    // the card behind it. What stayed gone is the collision culling, which
    // removed marks with no way back.
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
    // The anchor stays at its own coordinate - folding moves nothing.
    expect(collection.features[0].geometry.coordinates).toEqual([-77, 39])
    // And the privy is on the pin rather than gone: the badge key names it.
    expect(collection.features[0].properties[SITE_MEMBERS_PROPERTY]).toContain('privy')
  })

  it('names the folded member on the anchor, so the pin says what is there', () => {
    // The badge key stays present and always a string - the style's `match`
    // needs no `coalesce` - and now carries what rode in. A pin that folded a
    // privy away and then said nothing about it would be the deletion the
    // fold exists to avoid, with extra steps.
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

    expect(collection.features).toHaveLength(1)
    expect(collection.features[0].properties[SITE_MEMBERS_PROPERTY]).toContain('privy')
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

describe('the staleness ring on crowded ground (#1536)', () => {
  /** The ring's stroke opacity as MapLibre would compute it. */
  function ringOpacity(ring: string, crowding: number): number {
    const paint = buildPoiStalenessLayer().paint as Record<string, unknown>
    return evaluate(paint['circle-stroke-opacity'] as unknown[], {
      staleness_ring: ring,
      [CROWDING_PROPERTY]: crowding,
    }) as number
  }

  it('draws the ring at its full tier strength on quiet ground', () => {
    // The corridor, where every waypoint measures under QUIET_NEIGHBOURS.
    // Nothing about the A.T.'s rings changes.
    expect(ringOpacity('green', 0)).toBeCloseTo(0.9, 5)
    expect(ringOpacity('green', QUIET_NEIGHBOURS)).toBeCloseTo(0.9, 5)
    expect(ringOpacity('faint-invite', QUIET_NEIGHBOURS)).toBeCloseTo(0.35, 5)
  })

  it('takes the ring away entirely where the ground is crowded', () => {
    // 660 waypoints on one Brooklyn screen each wore a 42 px ring, which is
    // the "nothing here is trustworthy" wash RING_OPACITIES is written to
    // avoid. A circle layer joins no placement pass, so this is the only
    // question the layer can ask about whether a ring is on a pin.
    expect(ringOpacity('faint-invite', CROWDED_NEIGHBOURS)).toBe(0)
    expect(ringOpacity('green', CROWDED_NEIGHBOURS * 3)).toBe(0)
  })

  it('fades rather than switching, so no hard edge runs across a park', () => {
    const midpoint = (QUIET_NEIGHBOURS + CROWDED_NEIGHBOURS) / 2
    const faded = ringOpacity('faint-invite', midpoint)

    expect(faded).toBeGreaterThan(0)
    expect(faded).toBeLessThan(0.35)
  })

  it('leaves the per-tier strengths as the one home for how loud a tier is', () => {
    // A product, not a second `match`: this expression can only ever turn the
    // tier values down, so a tier whose opacity changes changes in one place.
    const quiet = ringOpacity('grey-dotted', QUIET_NEIGHBOURS)
    expect(quiet).toBeCloseTo(0.55, 5)
    expect(ringOpacity('grey-dotted', CROWDED_NEIGHBOURS)).toBeLessThan(quiet)
  })

  it('still draws nothing for a waypoint with no ring, at any crowding', () => {
    expect(ringOpacity(NO_RING, 0)).toBe(0)
    expect(ringOpacity(NO_RING, CROWDED_NEIGHBOURS)).toBe(0)
  })
})

describe('how crowded the ground is, on the feature (#1536)', () => {
  it('counts every drawn mark, now that every one of them is drawn', () => {
    // Crowding is computed AFTER the fold again (2026-09-20), so a shelter
    // carrying a privy and two campsites is one neighbour to the marks around
    // it rather than four. Counting before folding would report ground as
    // crowded that the fold had already uncrowded, and buy air nobody needed.
    const site = ['privy', 'campsite', 'campsite'].map((type, i) => ({
      id: `${type}-${i}`,
      type,
      lat: 39.0004,
      lon: -77 + i * 0.00001,
      confidence: 'high' as const,
      siteId: 'site_1',
      siteRole: 'member',
    }))
    const pois = [
      {
        id: 'shelter',
        type: 'shelter',
        lat: 39,
        lon: -77,
        confidence: 'high' as const,
        siteId: 'site_1',
        siteRole: 'anchor',
      },
      ...site,
    ]

    const collection = poiFeatureCollection(pois)

    expect(collection.features).toHaveLength(1)
    const shelter = collection.features.find((f) => f.id === 'shelter')
    expect(shelter).toBeDefined()
    // One mark on this ground, so nothing is crowding it.
    expect(shelter?.properties[CROWDING_PROPERTY]).toBe(0)
  })

  it('recounts when the hiker hides a category, so air is bought against pins that exist', () => {
    // The thing a pipeline-computed figure could not do. Ten privies around
    // one shelter make crowded ground; with privies hidden, the shelter is
    // alone and should be padded as though it is.
    const privies = Array.from({ length: 10 }, (_, i) => ({
      id: `privy-${i}`,
      type: 'privy',
      lat: 39 + i * 0.0005,
      lon: -77,
      confidence: 'high' as const,
    }))
    const pois = [
      { id: 'shelter', type: 'shelter', lat: 39, lon: -77, confidence: 'high' as const },
      ...privies,
    ]

    const withPrivies = poiFeatureCollection(pois).features.find(
      (f) => f.id === 'shelter',
    )
    expect(withPrivies?.properties[CROWDING_PROPERTY]).toBe(10)

    const hidden = poiFeatureCollection(
      pois.filter((poi) => poi.type !== 'privy'),
    ).features.find((f) => f.id === 'shelter')
    expect(hidden?.properties[CROWDING_PROPERTY]).toBe(0)
  })

  it('puts a number on every drawn feature, so the style never interpolates on a missing one', () => {
    const features = poiFeatureCollection([
      { id: 'a', type: 'water', lat: 39, lon: -77, confidence: 'high' },
      { id: 'b', type: 'shelter', lat: 41, lon: -74, confidence: 'high' },
    ]).features

    for (const feature of features) {
      expect(typeof feature.properties[CROWDING_PROPERTY]).toBe('number')
    }
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

  it('draws the shelter alone when nothing is hidden, the privy riding its pin', () => {
    // Folding again since 2026-09-20. The privy is not off the map: it is on
    // the shelter's pin as a badge and on the card behind it. #607's fallback
    // is the test below - hide the shelter and the privy takes the pin.
    expect(drawnPins(showAllTypes()).sort()).toEqual(['shelter'])
  })

  it('draws the shelter and not the privy when only shelters are asked for', () => {
    // The hiker's own filter, and the one subtraction that survives: they
    // asked for shelters. Nothing about #1585 touches this - it is the
    // control, not the map deciding.
    expect(drawnPins(onlyType('shelter'))).toEqual(['shelter'])
  })

  it('resolves every pin to an image that was actually registered', () => {
    // There is no promotion left to test - a privy is never folded away, so
    // it is never promoted back - but the property this guarded still has to
    // hold: an id nobody built draws as nothing at all, which would be the
    // blank map by another route. So every feature the source emits, under
    // every filter, must resolve to a registered image.
    for (const shown of [showAllTypes(), onlyType('privy'), onlyType('shelter')]) {
      const hiddenTypes = hiddenTypesFrom(shown)
      for (const feature of poiFeatureCollection(SITE, { hiddenTypes }).features) {
        expect(REGISTERED_ICON_IDS).toContain(
          evaluate(POI_ICON_EXPRESSION, feature.properties),
        )
      }
    }
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

/**
 * The zoom ladder the maintainer asked for on 2026-09-20: "Add Tests at every
 * zoom level to make sure the above happens."
 *
 * One list of zooms, walked by every rule this design turns on, so a change
 * that is right at z12 and wrong at z7 cannot pass. The three blocks above
 * check the FILTER (which categories) at every zoom; this one checks the
 * LAYERS (whether anything is drawn at all) and the SOURCE (what got folded),
 * which are the two other places a waypoint can be lost.
 */
describe('the zoom ladder (2026-09-20)', () => {
  // Every zoom a hiker's camera can be at, with the seam and the two zooms
  // either side of it named rather than assumed. MapLibre's own range is 0-24;
  // 22 is the furthest this app's basemap goes.
  const LADDER = [0, 2, 4.9, 6, 6.9, 7, 7.1, 8, 9, 10, 12, 14, 16, 18, 20, 22]
  const BELOW = LADDER.filter((z) => z < POI_PIN_MIN_ZOOM)
  const ATiOR_ABOVE = LADDER.filter((z) => z >= POI_PIN_MIN_ZOOM)

  /** Whether a layer draws at a zoom, by its own floor and ceiling. */
  function draws(layer: { minzoom?: number; maxzoom?: number }, zoom: number): boolean {
    return zoom >= (layer.minzoom ?? 0) && zoom < (layer.maxzoom ?? 25)
  }

  it('draws no waypoint mark of any kind below the seam', () => {
    // The seam the maintainer set: "We can keep a seam, and make it at zoom 7.
    // Yes the POI's can be hidden above there" - above meaning further out.
    // Both ranks, because a dot below the seam is still a waypoint mark and
    // the corridor view is meant to be trails and clubs.
    expect(BELOW.length).toBeGreaterThan(3)
    for (const zoom of BELOW) {
      expect({ zoom, pins: draws(buildPoiLayer(), zoom) }).toEqual({ zoom, pins: false })
      expect({ zoom, dots: draws(buildPoiDotLayer(), zoom) }).toEqual({
        zoom,
        dots: false,
      })
    }
  })

  it('draws both ranks at every zoom from the seam up, with no gap between them', () => {
    // "A pin or a dot and never neither" (#597), asserted across the ladder
    // rather than at the two ends: a ceiling on either layer would open a band
    // where a waypoint has no mark, and a ceiling is the one thing a floor
    // test cannot see.
    expect(ATiOR_ABOVE.length).toBeGreaterThan(5)
    for (const zoom of ATiOR_ABOVE) {
      expect({ zoom, pins: draws(buildPoiLayer(), zoom) }).toEqual({ zoom, pins: true })
      expect({ zoom, dots: draws(buildPoiDotLayer(), zoom) }).toEqual({
        zoom,
        dots: true,
      })
    }
    expect(buildPoiLayer().maxzoom).toBeUndefined()
    expect(buildPoiDotLayer().maxzoom).toBeUndefined()
  })

  it('crosses the seam exactly once, so there is no zoom that draws half a rank', () => {
    // The seam is a single boundary rather than two that nearly agree. Walking
    // the ladder, the number of times "does anything draw" changes answer must
    // be exactly one, and it must change at the seam.
    let flips = 0
    let at = -1
    for (let i = 1; i < LADDER.length; i += 1) {
      const before = draws(buildPoiLayer(), LADDER[i - 1])
      const now = draws(buildPoiLayer(), LADDER[i])
      if (before !== now) {
        flips += 1
        at = LADDER[i]
      }
      // And the two ranks flip together, always.
      expect({
        zoom: LADDER[i],
        same: now === draws(buildPoiDotLayer(), LADDER[i]),
      }).toEqual({ zoom: LADDER[i], same: true })
    }
    expect(flips).toBe(1)
    expect(at).toBe(POI_PIN_MIN_ZOOM)
  })

  it('folds a site the same way at every zoom, because the fold is in the source', () => {
    // THE NESTING AS A REQUIREMENT, which is what the maintainer asked for:
    // "The grouping of locations was working before. You need to nest the
    // Shelters, Campsites, Privies & Water as we did before this PR. Add a
    // test to make this a requirement."
    //
    // The honest form of "at every zoom" for this one: folding happens when
    // the source is built and carries no zoom term at all, so the assertion
    // is that it CANNOT vary with the camera. A fold that did would be a
    // waypoint appearing and disappearing as a hiker pinched.
    const site = poiFeatureCollection([
      {
        id: 'shelter',
        type: 'shelter',
        lat: 39,
        lon: -77,
        confidence: 'high',
        siteId: 'site_1',
        siteRole: 'anchor',
      },
      ...['privy', 'water', 'campsite'].map((type) => ({
        id: type,
        type,
        lat: 39.0004,
        lon: -77,
        confidence: 'high' as const,
        siteId: 'site_1',
        siteRole: 'member',
      })),
    ])

    // One pin for the place, carrying all three parts the pipeline groups on.
    expect(site.features).toHaveLength(1)
    const badge = site.features[0].properties[SITE_MEMBERS_PROPERTY] as string
    for (const member of ['privy', 'water', 'campsite']) {
      expect({ member, onThePin: badge.includes(member) }).toEqual({
        member,
        onThePin: true,
      })
    }
    // And nothing in the style that draws it consults the zoom to decide.
    const iconLayout = buildPoiLayer().layout as Record<string, unknown>
    expect(JSON.stringify(iconLayout['icon-image'])).not.toContain('zoom')
  })

  it('stands the pin on its point at every zoom, so the trail line passes under it', () => {
    // The jigger the maintainer chose on 2026-09-20, once the trail line went
    // over the waypoints: the pin steps clear rather than being sliced.
    //
    // ANCHORED, NOT OFFSET, and the test says so because the difference is
    // the whole of whether this is honest. An offset would move the drawn pin
    // off the place; an anchor says which part of the artwork lands ON the
    // place. A regression to `icon-offset` would look identical on screen and
    // would be the app drawing a waypoint where it is not.
    const layout = buildPoiLayer().layout as Record<string, unknown>
    expect(layout['icon-anchor']).toBe('bottom')
    expect(layout['icon-offset']).toBeUndefined()
    // No zoom term, so the pin stands on its point at every zoom rather than
    // at the two somebody checked.
    expect(typeof layout['icon-anchor']).toBe('string')
  })

  it('keeps the collision engine off at every zoom, so folding is the only grouping', () => {
    // The two are easy to confuse and must not be: FOLDING removes a member
    // from the source and puts it on the anchor's pin, where the hiker can
    // still reach it. CULLING dropped whichever pin lost a collision, with no
    // way back. The fold came back on 2026-09-20; the culling did not, and
    // this is the line that stops it returning by accident.
    const layout = buildPoiLayer().layout as Record<string, unknown>
    expect(layout['icon-allow-overlap']).toBe(true)
    expect(layout['icon-ignore-placement']).toBe(true)
    // Neither is a zoom expression, so there is no band where culling resumes.
    expect(typeof layout['icon-allow-overlap']).toBe('boolean')
    expect(typeof layout['icon-ignore-placement']).toBe('boolean')
  })
})
