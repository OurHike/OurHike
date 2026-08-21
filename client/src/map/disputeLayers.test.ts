import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import type { SymbolLayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { POI_LAYER_ID } from './poiLayers'
import { DISPUTE_MARK_ID, DISPUTE_MARK_SIZE, buildDisputeMark } from './disputeMark'
import {
  attachDisputeData,
  attachDisputeIcon,
  buildDisputeLayer,
  buildDisputeSource,
  disputeFeatureCollection,
  DISPUTE_ID_PROPERTY,
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
  { poiId: 'atc_shelters:spring-1', lon: -74.1, lat: 41.3 },
  { poiId: 'osm_water:9', lon: -73.9, lat: 41.1 },
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

  it('sits on the shoulder of the pin rather than over its glyph', () => {
    const offset = layer().layout?.['icon-offset'] as [number, number]

    expect(offset[0]).toBeGreaterThan(0)
    expect(offset[1]).toBeLessThan(0)
  })

  it('asks for the image disputeMark.ts actually registers', () => {
    expect(buildDisputeLayer().layout).toMatchObject({ 'icon-image': DISPUTE_MARK_ID })
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

  it('carries the poi id and nothing else', () => {
    // Not the count, not the date. What a dispute SAYS is the card's job -
    // a count in a GeoJSON source is one `text-field` away from being drawn
    // on the map without the sentence that makes it honest.
    const properties = disputeFeatureCollection(DISPUTED).features[0].properties

    expect(properties).toEqual({ [DISPUTE_ID_PROPERTY]: 'atc_shelters:spring-1' })
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
