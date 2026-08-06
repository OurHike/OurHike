import { describe, it, expect, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { WARNING_PIN } from '../lib/seriousWarnings'
import { POI_PIN_PIXEL_RATIO, buildAlertPinIcon } from './poiIcons'
import {
  attachWarningData,
  attachWarningIcon,
  buildWarningLayer,
  warningFeatureCollection,
  WARNING_ICON_ID,
  WARNING_ID_PROPERTY,
  WARNING_LAYER_ID,
  WARNING_SOURCE_ID,
} from './warningLayers'

// WIREFRAMES.md §8: 44px, red, triangle-alert, and deliberately the biggest
// thing on the map. The layer's job is to make sure it also CANNOT be
// suppressed - which is a collision-engine setting, not a size.

beforeEach(() => {
  resetMapLibreMock()
})

describe('the warning layer', () => {
  it('is always placed - the collision engine may not thin warnings out', () => {
    // The ordinary pins let MapLibre declutter them, with POI_PRIORITY
    // deciding who survives. A serious warning must never lose that contest:
    // a bear warning hidden because a water pin got there first would be the
    // map suppressing exactly what a moderator escalated.
    const layout = buildWarningLayer().layout as Record<string, unknown>

    expect(layout['icon-allow-overlap']).toBe(true)
  })

  it('does not shoulder the ordinary pins out of placement either', () => {
    // The other half: a warning that ATE the shelter pin beside it would
    // erase somewhere to sleep. Ignore-placement lets both stand.
    const layout = buildWarningLayer().layout as Record<string, unknown>

    expect(layout['icon-ignore-placement']).toBe(true)
  })

  it('has no minzoom - someone planning miles from the corridor view is who it is for', () => {
    expect(buildWarningLayer().minzoom).toBeUndefined()
  })

  it('draws no text - a label needs glyphs, which need signal', () => {
    // Same reasoning as the POI layer: a label that vanishes on the ridge is
    // worse than none. The pin itself is the message.
    const layout = buildWarningLayer().layout as Record<string, unknown>

    expect(layout['text-field']).toBeUndefined()
  })
})

describe('the warning pin image', () => {
  it('is one full touch target, bigger than every ordinary pin', () => {
    const image = buildAlertPinIcon(WARNING_PIN.sizePx, WARNING_PIN.color)

    expect(WARNING_PIN.sizePx).toBe(44)
    expect(WARNING_PIN.sizePx).toBeGreaterThan(WARNING_PIN.ordinaryPinPx)
    expect(image.width).toBe(WARNING_PIN.sizePx * POI_PIN_PIXEL_RATIO)
    expect(image.height).toBe(WARNING_PIN.sizePx * POI_PIN_PIXEL_RATIO)
  })

  it('registers under the id the layer asks for, at the crispness ratio', () => {
    const map = new MockMap({})
    map.layerIds = [WARNING_LAYER_ID]

    attachWarningIcon(map as unknown as MapLibreMap)

    expect(map.images.has(WARNING_ICON_ID)).toBe(true)
    expect(map.imageOptions.get(WARNING_ICON_ID)).toEqual({
      pixelRatio: POI_PIN_PIXEL_RATIO,
    })
  })
})

describe('the warning data', () => {
  it('carries the report id in properties, where a tap can read it back', () => {
    const fc = warningFeatureCollection([{ id: 'report-9', lon: -83.5, lat: 35.6 }])

    expect(fc.features[0].properties[WARNING_ID_PROPERTY]).toBe('report-9')
    expect(fc.features[0].geometry.coordinates).toEqual([-83.5, 35.6])
  })

  it('pushes onto the live source, waiting for it like every other attach', () => {
    const map = new MockMap({})

    attachWarningData(map as unknown as MapLibreMap, [
      { id: 'report-9', lon: -83.5, lat: 35.6 },
    ])
    expect(map.sourceData.get(WARNING_SOURCE_ID)).toBeUndefined()

    map.sourceIds = [WARNING_SOURCE_ID]
    map.emit('styledata')

    const pushed = map.sourceData.get(WARNING_SOURCE_ID) as ReturnType<
      typeof warningFeatureCollection
    >
    expect(pushed.features).toHaveLength(1)
  })
})
