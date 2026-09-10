import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
// Explicitly imported rather than used as a global: tsconfig.app.json keeps
// node out of `types` so browser code cannot reach for it and still typecheck.
import { cwd } from 'node:process'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { POI_LAYER_ID, POI_PIN_MIN_ZOOM } from './poiLayers'
import { POI_PIN_PIXEL_RATIO } from './poiIcons'
import { WARNING_ICON_ID } from './warningPin'
import {
  attachWarningData,
  attachWarningTaps,
  warningIdAt,
  attachWarningIcon,
  buildWarningLayer,
  buildWarningSource,
  warningFeatureCollection,
  WARNING_ID_PROPERTY,
  WARNING_LAYER_ID,
  WARNING_SOURCE_ID,
} from './warningLayers'

// Two rules here are safety rules rather than cartographic ones, and both are
// asserted rather than left to the layer spec: a serious warning must not be
// decluttered away, and it must never become a notification.

const WARNINGS = [
  { id: 'r1', lon: -77.1, lat: 39.3 },
  { id: 'r2', lon: -78.4, lat: 40.1 },
]

describe('the layer', () => {
  it('is never dropped by the collision engine', () => {
    // Every other symbol on this map submits to placement. A warning dropped
    // because a shelter pin got there first is a warning nobody was shown -
    // and from the hiker's side that is indistinguishable from there being
    // none, which is the state this whole feature exists to prevent.
    expect(buildWarningLayer().layout).toMatchObject({ 'icon-allow-overlap': true })
  })

  it('still pushes waypoints aside, rather than ignoring placement entirely', () => {
    // `icon-ignore-placement: true` would let a shelter pin draw straight
    // through the warning. Left at the spec default so the warning wins the
    // space and the waypoint moves.
    expect(buildWarningLayer().layout).not.toHaveProperty('icon-ignore-placement')
  })

  it('starts at the seam, like the waypoints (#1292)', () => {
    // It drew at every zoom until 2026-09-08 - "zoomed out to plan a week is
    // exactly when someone wants to see where they are" - and the
    // maintainer's call that the opening camera shows trail lines only
    // reversed that. Below the seam a 44 px pin covered a hundred trail miles
    // and said "somewhere here"; the route banner still counts warnings at
    // every zoom. The module header carries the safety-path note.
    expect(buildWarningLayer().minzoom).toBe(POI_PIN_MIN_ZOOM)
  })

  it('holds its size instead of shrinking toward a minzoom', () => {
    // The waypoints interpolate down to 0.6 as they approach z9. A warning
    // drawn at 0.6 has stopped being the biggest thing on the map, which is
    // the one property lib/seriousWarnings.ts asks of it.
    expect(buildWarningLayer().layout).toMatchObject({ 'icon-size': 1 })
  })

  it('asks for the image warningPin.ts actually registers', () => {
    // A layout `icon-image` naming an image nobody added draws nothing at all
    // and logs once per tile - which looks exactly like having no warnings.
    expect(buildWarningLayer().layout).toMatchObject({ 'icon-image': WARNING_ICON_ID })
  })

  it('is a separate layer from the waypoints, not a filter on them', () => {
    expect(buildWarningLayer().id).not.toBe(POI_LAYER_ID)
  })
})

describe('the source', () => {
  it('starts empty, because reports arrive over the network after the map', () => {
    expect(buildWarningSource()).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  })

  it('hands each style its own features array rather than one shared object', () => {
    expect(buildWarningSource().data).not.toBe(buildWarningSource().data)
  })
})

describe('warningFeatureCollection', () => {
  it('puts each warning at the coordinates the report was written at', () => {
    const geojson = warningFeatureCollection(WARNINGS)

    expect(geojson.features.map((f) => f.geometry.coordinates)).toEqual([
      [-77.1, 39.3],
      [-78.4, 40.1],
    ])
  })

  it('carries the report id in the properties, where a tap could read it', () => {
    expect(warningFeatureCollection(WARNINGS).features[0].properties).toEqual({
      [WARNING_ID_PROPERTY]: 'r1',
    })
  })

  it('carries nothing else - not the note, not the type, not who wrote it', () => {
    // The canvas draws WHERE. What a warning says is the sheet's job, and it
    // stays the sheet's job now that #292 has trimmed that sheet to fields a
    // backend can fill: a note or a type in a GeoJSON source is one
    // `text-field` away from being drawn on the map itself, stripped of the
    // confirmation date and the "why your phone stayed silent" note that are
    // the whole reason the sheet can carry it responsibly.
    const properties = warningFeatureCollection(WARNINGS).features[0].properties

    expect(Object.keys(properties)).toEqual([WARNING_ID_PROPERTY])
  })

  it('is empty for no warnings, rather than absent', () => {
    expect(warningFeatureCollection([])).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })
})

describe('pushing warnings onto a live map', () => {
  let map: MockMap

  beforeEach(() => {
    resetMapLibreMock()
    map = new MockMap({})
    map.layerIds = [WARNING_LAYER_ID]
    map.sourceIds = [WARNING_SOURCE_ID]
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('registers the pin image at the ratio it was drawn at', () => {
    map.styleLoaded = true

    attachWarningIcon(map as never)

    expect(map.images.has(WARNING_ICON_ID)).toBe(true)
    expect(map.imageOptions.get(WARNING_ICON_ID)).toEqual({
      pixelRatio: POI_PIN_PIXEL_RATIO,
    })
  })

  it('does not re-register an image a previous map screen already added', () => {
    // Images outlive a style reload and MapLibre throws on a duplicate id.
    // Every trip through the More tab builds a new map.
    map.styleLoaded = true
    attachWarningIcon(map as never)
    const addImage = vi.spyOn(map, 'addImage')

    attachWarningIcon(map as never)

    expect(addImage).not.toHaveBeenCalled()
  })

  it('pushes the warnings into the source as GeoJSON', () => {
    map.styleLoaded = true

    attachWarningData(map as never, WARNINGS)

    expect(map.sourceData.get(WARNING_SOURCE_ID)).toEqual(
      warningFeatureCollection(WARNINGS),
    )
  })

  it('still lands them when the style is busy at the moment they arrive', () => {
    map.sourceIds = []
    map.emit('load')
    map.styleLoaded = false

    attachWarningData(map as never, WARNINGS)
    expect(map.sourceData.get(WARNING_SOURCE_ID)).toBeUndefined()

    map.sourceIds = [WARNING_SOURCE_ID]
    map.emit('styledata')

    expect(map.sourceData.get(WARNING_SOURCE_ID)).toBeDefined()
  })

  it('keeps the map alive when the write fails, and says so', () => {
    map.styleLoaded = true
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    map.sources.set(WARNING_SOURCE_ID, {
      setData: () => {
        throw new Error('style replaced mid-write')
      },
    })

    expect(() => attachWarningData(map as never, WARNINGS)).not.toThrow()
    expect(warn).toHaveBeenCalled()
  })

  it('leaves no listener behind when detached before the style arrives', () => {
    map.layerIds = []
    map.sourceIds = []

    attachWarningIcon(map as never)()
    attachWarningData(map as never, WARNINGS)()

    expect(map.listenerCount('styledata')).toBe(0)
  })
})

describe('the rule that this never pushes', () => {
  it('imports nothing from a push module, at the level of the source text', () => {
    // OurHike sends no push notifications at all, and this test reads the
    // source of the module that finally mounts the warning path to keep it
    // that way - it is the one most likely to become the exception.
    // HIKER_SAFETY.md §1 is explicit that a warning about a named person
    // arriving as a phone notification is a different and much worse thing
    // than the same words on a map somebody chose to open.
    //
    // Read as text rather than asserted through behaviour because that is the
    // only way to catch the import before it has a call site.
    // Resolved from the working directory, which vitest does hand back -
    // import.meta.url is not a file:// URL here. Both candidates so this works
    // from the repo root or from client/.
    const src = [join(cwd(), 'src'), join(cwd(), 'client', 'src')].find((candidate) =>
      existsSync(candidate),
    ) as string
    const source = readFileSync(join(src, 'map', 'warningLayers.ts'), 'utf8')

    expect(source).toContain('WARNING_SOURCE_ID')
    expect(source).not.toMatch(/from '[^']*push'/)
    expect(source).not.toMatch(/Notification|registration\./)
  })
})

// #1373, F12: the tap #292 said "opens a sheet nothing can honestly fill",
// before it emptied the sheet of exactly that. What is left is what the wire
// carries, and the pin opens it now.
describe('tapping a pin', () => {
  function pin(id: string) {
    return { properties: { [WARNING_ID_PROPERTY]: id } }
  }
  function tappableMap(features: unknown[]): MockMap {
    const map = new MockMap({})
    map.layerIds = [WARNING_LAYER_ID, POI_LAYER_ID]
    map.renderedFeatures.set(WARNING_LAYER_ID, features)
    return map
  }

  it('tells the shell which warning was touched, and only on a hit', () => {
    const map = tappableMap([pin('r1')])
    const onSelect = vi.fn()

    attachWarningTaps(map as never, onSelect)
    map.emit('click', { point: { x: 120, y: 240 } })
    expect(onSelect).toHaveBeenCalledWith('r1')

    map.renderedFeatures.set(WARNING_LAYER_ID, [])
    onSelect.mockClear()
    map.emit('click', { point: { x: 1, y: 1 } })
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('is silent before the style holds the layer, and for a pin with no id', () => {
    const bare = new MockMap({})
    bare.layerIds = []
    const query = vi.spyOn(bare, 'queryRenderedFeatures')
    expect(warningIdAt(bare as never, { x: 10, y: 10 })).toBeNull()
    expect(query).not.toHaveBeenCalled()

    expect(
      warningIdAt(tappableMap([{ properties: {} }]) as never, { x: 1, y: 1 }),
    ).toBeNull()
  })

  it('stops listening when detached', () => {
    const map = tappableMap([pin('r1')])
    const onSelect = vi.fn()

    const detach = attachWarningTaps(map as never, onSelect)
    detach()
    map.emit('click', { point: { x: 1, y: 1 } })

    expect(onSelect).not.toHaveBeenCalled()
  })
})
