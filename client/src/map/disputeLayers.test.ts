import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  createExpression,
  type SymbolLayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import {
  FULL_SIZE_POI_TYPES,
  POI_ICON_SIZE_EXPRESSION,
  POI_LAYER_ID,
  POI_PIN_MIN_ZOOM,
} from './poiLayers'
import { POI_PIN_INK_SIZE } from './poiIcons'
import { DISPUTE_MARK_ID, DISPUTE_MARK_SIZE, buildDisputeMark } from './disputeMark'
import {
  attachDisputeData,
  attachDisputeIcon,
  buildDisputeLayer,
  buildDisputeSource,
  disputeFeatureCollection,
  DISPUTE_ID_PROPERTY,
  DISPUTE_MARK_OFFSET_EXPRESSION,
  DISPUTE_TYPE_PROPERTY,
  DISPUTE_LAYER_ID,
  DISPUTE_SOURCE_ID,
} from './disputeLayers'

// The mark on a place the field says is not there (#876, FIELD_NOTES.md §4).
//
// Two of these are rules rather than cartography, and both come straight from
// §4:
//
//  - **The pin is never suppressed.** "A POI that vanishes is
//    indistinguishable from one that never existed." So the mark cannot be
//    decluttered away, and - the part that is easy to get backwards - it must
//    not push the pin it annotates away either.
//  - **It rides its own source.** The POI features' `confidence` is what the
//    legend's "Verified?" toggle filters on, so a dispute expressed there
//    would let a filter delete the pin the rule above protects.

/** The layer, at the type it actually is. `buildDisputeLayer` returns the
 *  union every sibling returns - `style.ts` wants that - and half of the
 *  union has neither `source` nor `icon-offset` on it. */
const layer = () => buildDisputeLayer() as SymbolLayerSpecification

const DISPUTED = [
  { poiId: 'atc_shelters:spring-1', poiType: 'water', lon: -74.1, lat: 41.3 },
  { poiId: 'osm_water:9', poiType: 'water', lon: -73.9, lat: 41.1 },
]

describe('the layer', () => {
  it('is never dropped by the collision engine', () => {
    // A mark the engine drops is a suppression a hiker cannot tell from an
    // absence, which is the exact ambiguity §4 refuses.
    expect(buildDisputeLayer().layout).toMatchObject({ 'icon-allow-overlap': true })
  })

  it('never pushes the pin it annotates aside, unlike the warning pins', () => {
    // The one place this deliberately differs from map/warningLayers.ts. A
    // warning should shove a waypoint out of the way; a footnote must not
    // shove its own sentence off the page.
    expect(buildDisputeLayer().layout).toMatchObject({ 'icon-ignore-placement': true })
  })

  it('sits on the drawn pin\u2019s upper-left edge, at every zoom and for both tiers (#1687)', () => {
    // The maintainer's choice from five real pins drawn both ways (poll,
    // 2026-09-26): centred ON the edge, upper left - clear of a site pin's
    // badges, which fan out upper right. Checked as geometry: the pin stands
    // on its point, so its drawn centre is half its drawn size above the
    // coordinate, and the mark's centre is one more radius out at 45 degrees.
    expect(layer().layout?.['icon-offset']).toBe(DISPUTE_MARK_OFFSET_EXPRESSION)
    const offsetAt = (zoom: number, poiType: string) => {
      const compiled = createExpression(
        DISPUTE_MARK_OFFSET_EXPRESSION,
        'layers[0].layout.icon-offset',
      )
      if (compiled.result === 'error') throw new Error(compiled.value[0].message)
      return compiled.value.evaluate({ zoom }, {
        properties: { [DISPUTE_TYPE_PROPERTY]: poiType },
        type: 'Point',
      } as never) as [number, number]
    }
    const sizeAt = (zoom: number, poiType: string) => {
      const compiled = createExpression(
        POI_ICON_SIZE_EXPRESSION,
        'layers[0].layout.icon-size',
      )
      if (compiled.result === 'error') throw new Error(compiled.value[0].message)
      return compiled.value.evaluate({ zoom }, {
        properties: { poi_type: poiType },
        type: 'Point',
      } as never) as number
    }

    for (const zoom of [POI_PIN_MIN_ZOOM, 10, 13, 16]) {
      for (const poiType of [FULL_SIZE_POI_TYPES[0], 'viewpoint']) {
        const radius = (POI_PIN_INK_SIZE / 2) * sizeAt(zoom, poiType)
        const [x, y] = offsetAt(zoom, poiType)
        const fromCentre = { x, y: y + radius }
        const where = `z${zoom} ${poiType}`
        expect(Math.hypot(fromCentre.x, fromCentre.y), where).toBeCloseTo(radius, 6)
        expect(fromCentre.x, where).toBeLessThan(0)
        expect(fromCentre.x, where).toBeCloseTo(fromCentre.y, 6)
      }
    }
  })

  it('follows the pin\u2019s own size stops rather than a copy of them', () => {
    // Same zooms, in the same places, as POI_ICON_SIZE_EXPRESSION - a pin
    // ramp moved without this following it would put the mark back off the
    // pin, which is how it got there the first time.
    const zooms = (expression: unknown[]) =>
      expression.filter((_, index) => index >= 3 && index % 2 === 1)
    expect(zooms(DISPUTE_MARK_OFFSET_EXPRESSION)).toEqual(zooms(POI_ICON_SIZE_EXPRESSION))
  })

  it('asks for the image disputeMark.ts actually registers', () => {
    expect(buildDisputeLayer().layout).toMatchObject({ 'icon-image': DISPUTE_MARK_ID })
  })

  it('starts where the pins it annotates start (#1292)', () => {
    // A footnote with no sentence under it: the waypoint pins draw from the
    // seam up, so a mark on a pin's shoulder below it would sit on nothing.
    expect(buildDisputeLayer().minzoom).toBe(POI_PIN_MIN_ZOOM)
  })

  it('is its own layer, not a property on the waypoints', () => {
    // The load-bearing one: `confidence` is what "Verified?" filters on, and
    // a dispute expressed there would let a filter delete the pin.
    expect(layer().id).not.toBe(POI_LAYER_ID)
    expect(layer().source).toBe(DISPUTE_SOURCE_ID)
  })
})

describe('the source', () => {
  it('starts empty, because verdicts arrive over the network after the map', () => {
    expect(buildDisputeSource()).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  })

  it('carries the place\u2019s id and type, and nothing the dispute says', () => {
    // Not the count, not the date. What a dispute SAYS is the card's job -
    // a count in a GeoJSON source is one `text-field` away from being drawn
    // on the map without the sentence that makes it honest. The type is the
    // PLACE's, and only decides how big its pin is drawn (#1687).
    const properties = disputeFeatureCollection(DISPUTED).features[0].properties

    expect(properties).toEqual({
      [DISPUTE_ID_PROPERTY]: 'atc_shelters:spring-1',
      [DISPUTE_TYPE_PROPERTY]: 'water',
    })
  })

  it('puts each mark where its waypoint is', () => {
    expect(
      disputeFeatureCollection(DISPUTED).features.map((f) => f.geometry.coordinates),
    ).toEqual([
      [-74.1, 41.3],
      [-73.9, 41.1],
    ])
  })
})

describe('pushing marks onto a live map', () => {
  let map: MockMap

  beforeEach(() => {
    resetMapLibreMock()
    map = new MockMap({})
    map.layerIds = [DISPUTE_LAYER_ID]
    map.sourceIds = [DISPUTE_SOURCE_ID]
    map.styleLoaded = true
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('registers the mark image', () => {
    attachDisputeIcon(map as never)

    expect(map.images.has(DISPUTE_MARK_ID)).toBe(true)
  })

  it('clears the marks when a dispute decays or is cleared', () => {
    attachDisputeData(map as never, DISPUTED)
    attachDisputeData(map as never, [])

    // Decay is a real path here, not a hypothetical: a dispute stands for a
    // season and then stops, and a mark left drawn from the last render is a
    // claim nobody is making any more.
    expect(map.sourceData.get(DISPUTE_SOURCE_ID)).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })
})

describe('the mark itself', () => {
  it('is smaller than a waypoint pin', () => {
    // A footnote on a pin, not a second pin. This feature's posture is that
    // a dispute is a thing to SAY, not a claim that the place is gone.
    const mark = buildDisputeMark(DISPUTE_MARK_SIZE, 2)

    expect(mark.width).toBe(DISPUTE_MARK_SIZE * 2)
    expect(mark.width).toBeLessThan(38 * 2)
  })

  it('draws ink through the middle - the bar that makes it a negation', () => {
    const mark = buildDisputeMark(DISPUTE_MARK_SIZE, 2)
    const centre = ((mark.height / 2) * mark.width + mark.width / 2) * 4

    // Without the bar this is a ring, and a ring on a pin reads as emphasis
    // rather than as "not here".
    expect(mark.data[centre]).toBeLessThan(128)
    expect(mark.data[centre + 3]).toBe(255)
  })

  it('is transparent outside its circle, so it does not box the pin', () => {
    const mark = buildDisputeMark(DISPUTE_MARK_SIZE, 2)

    expect(mark.data[3]).toBe(0)
  })
})
