import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { POI_LAYER_ID, POI_PIN_MIN_ZOOM } from './poiLayers'
import { POI_PIN_PIXEL_RATIO } from './poiIcons'
import { WORKDAY_ICON_ID } from './workdayPin'
import {
  attachWorkdayData,
  attachWorkdayIcon,
  attachWorkdayTaps,
  buildWorkdayLayer,
  buildWorkdaySource,
  workdayFeatureCollection,
  workdayIdAt,
  WORKDAY_ID_PROPERTY,
  WORKDAY_LAYER_ID,
  WORKDAY_SOURCE_ID,
  WORKDAY_TAP_SLOP_PX,
} from './workdayLayers'

// The workday pins (#760). Two of these are rules rather than cartography,
// and both come from the fact that this is the first layer in the app whose
// data EXPIRES:
//
//  - an empty set is a first-class argument, because that is what a stale
//    feed passes, and
//  - a workday must not shove a waypoint aside, because the tab is what
//    promises completeness and the map is only where they are.

const WORKDAYS = [
  { id: 'wp-1', lon: -74.1, lat: 41.3 },
  { id: 'wp-2', lon: -73.9, lat: 41.1 },
]

describe('the layer', () => {
  it('asks for the image workdayPin.ts actually registers', () => {
    // A layout `icon-image` naming an image nobody added draws nothing and
    // logs once per tile - indistinguishable from having no workdays.
    expect(buildWorkdayLayer().layout).toMatchObject({ 'icon-image': WORKDAY_ICON_ID })
  })

  it('draws at every zoom, unlike the waypoints', () => {
    // Eight hundred waypoints on the corridor is a texture, so they start at
    // z9. There are a handful of workdays on 2,197 miles, and zoomed out to
    // plan a weekend is exactly when somebody is looking for one.
    expect(buildWorkdayLayer()).not.toHaveProperty('minzoom')
    expect(POI_PIN_MIN_ZOOM).toBeGreaterThan(0)
  })

  it('submits to the collision engine, unlike the warning pins', () => {
    // The one place this layer deliberately differs from the warning it is
    // modelled on. A warning dropped is a warning nobody was shown; a
    // workday hidden behind a shelter costs a hiker nothing they were
    // relying on, because the Volunteer tab lists every one of them. Letting
    // it push waypoints aside would be this feature pressing on the map.
    expect(buildWorkdayLayer().layout).not.toHaveProperty('icon-allow-overlap')
  })

  it('is its own layer rather than a filter on the waypoints', () => {
    expect(buildWorkdayLayer().id).not.toBe(POI_LAYER_ID)
  })
})

describe('the source', () => {
  it('starts empty, because workdays arrive over the network after the map', () => {
    expect(buildWorkdaySource()).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  })

  it('hands each style its own features array rather than one shared object', () => {
    expect(buildWorkdaySource().data).not.toBe(buildWorkdaySource().data)
  })
})

describe('workdayFeatureCollection', () => {
  it('puts each workday where the reviewed row placed it', () => {
    expect(
      workdayFeatureCollection(WORKDAYS).features.map((f) => f.geometry.coordinates),
    ).toEqual([
      [-74.1, 41.3],
      [-73.9, 41.1],
    ])
  })

  it('carries the project id where a tap can read it, and nothing else', () => {
    // Not the title, not the club, not the dates. What a workday SAYS is the
    // sheet's job; a title in a GeoJSON source is one `text-field` away from
    // being drawn on the map without the "check before travelling" line that
    // is the only thing making an expiring invitation honest.
    const properties = workdayFeatureCollection(WORKDAYS).features[0].properties

    expect(properties).toEqual({ [WORKDAY_ID_PROPERTY]: 'wp-1' })
    expect(Object.keys(properties)).toEqual([WORKDAY_ID_PROPERTY])
  })

  it('is empty for no workdays rather than absent', () => {
    // The frequent case, not the edge one: a stale feed, an empty window and
    // a trail no club has posted on all arrive here as an empty array.
    expect(workdayFeatureCollection([])).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })
})

describe('pushing workdays onto a live map', () => {
  let map: MockMap

  beforeEach(() => {
    resetMapLibreMock()
    map = new MockMap({})
    map.layerIds = [WORKDAY_LAYER_ID]
    map.sourceIds = [WORKDAY_SOURCE_ID]
    map.styleLoaded = true
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('registers the pin image at the ratio it was drawn at', () => {
    attachWorkdayIcon(map as never)

    expect(map.images.has(WORKDAY_ICON_ID)).toBe(true)
    expect(map.imageOptions.get(WORKDAY_ICON_ID)).toEqual({
      pixelRatio: POI_PIN_PIXEL_RATIO,
    })
  })

  it('does not re-add an image that survived a style reload', () => {
    attachWorkdayIcon(map as never)
    const addImage = vi.spyOn(map, 'addImage')

    attachWorkdayIcon(map as never)

    // `addImage` throws on a duplicate, and images outlive a style reload -
    // every trip through the More tab builds a new map.
    expect(addImage).not.toHaveBeenCalled()
  })

  it('pushes the workdays into the source as GeoJSON', () => {
    attachWorkdayData(map as never, WORKDAYS)

    expect(map.sourceData.get(WORKDAY_SOURCE_ID)).toEqual(
      workdayFeatureCollection(WORKDAYS),
    )
  })

  it('clears the pins when the shell passes nothing', () => {
    // The stale-feed path, and the one that has to work: past the ceiling
    // the shell passes an empty set, and a pin left drawn from the last
    // render is an invitation to a workday nobody is running.
    attachWorkdayData(map as never, WORKDAYS)
    attachWorkdayData(map as never, [])

    expect(map.sourceData.get(WORKDAY_SOURCE_ID)).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })
})

describe('tapping a workday', () => {
  let map: MockMap

  beforeEach(() => {
    resetMapLibreMock()
    map = new MockMap({})
    map.layerIds = [WORKDAY_LAYER_ID]
    map.sourceIds = [WORKDAY_SOURCE_ID]
    map.styleLoaded = true
  })

  it('answers a near miss, not only a dead-centre hit', () => {
    // The app is used with a gloved thumb in rain. poiTaps.ts's reasoning,
    // and the slop is derived from the same touch target rather than
    // restated - so it cannot drift the day the pin size moves.
    expect(WORKDAY_TAP_SLOP_PX).toBeGreaterThanOrEqual(0)

    map.renderedFeatures.set(WORKDAY_LAYER_ID, [
      { properties: { [WORKDAY_ID_PROPERTY]: 'wp-2' } },
    ])

    expect(workdayIdAt(map as never, { x: 100, y: 100 })).toBe('wp-2')
    const box = map.featureQueries[0].geometry as [[number, number], [number, number]]
    expect(box[0][0]).toBe(100 - WORKDAY_TAP_SLOP_PX)
  })

  it('says nothing when the touch landed on empty map', () => {
    expect(workdayIdAt(map as never, { x: 10, y: 10 })).toBeNull()
  })

  it('says nothing when the layer is not on this style at all', () => {
    map.layerIds = []
    map.renderedFeatures.set(WORKDAY_LAYER_ID, [
      { properties: { [WORKDAY_ID_PROPERTY]: 'wp-1' } },
    ])

    // Queried against a layer that does not exist, MapLibre throws rather
    // than answering - and a workday tap must never be the thing that takes
    // the map down.
    expect(workdayIdAt(map as never, { x: 10, y: 10 })).toBeNull()
    expect(map.featureQueries).toHaveLength(0)
  })

  it('reports the tapped project and detaches cleanly', () => {
    map.renderedFeatures.set(WORKDAY_LAYER_ID, [
      { properties: { [WORKDAY_ID_PROPERTY]: 'wp-1' } },
    ])
    const onSelect = vi.fn()

    const detach = attachWorkdayTaps(map as never, onSelect)
    map.emit('click', { point: { x: 5, y: 5 } })
    expect(onSelect).toHaveBeenCalledWith('wp-1')

    detach()
    map.emit('click', { point: { x: 5, y: 5 } })
    expect(onSelect).toHaveBeenCalledTimes(1)
  })
})
