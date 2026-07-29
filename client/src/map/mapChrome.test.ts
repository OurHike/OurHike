import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  MockMap,
  NavigationControl,
  GeolocateControl,
  ScaleControl,
  resetMapLibreMock,
} from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { attachMapChrome } from './mapChrome'

// WIREFRAMES.md, map screen §5 and Interactions: compass is a
// `NavigationControl`, locate is a `GeolocateControl` with continuous tracking,
// scale is a `ScaleControl` in imperial by default. Compass and locate stack
// bottom-RIGHT (the thumb zone - everything tapped mid-walk sits in the lower
// third); the scale bar sits bottom-LEFT above the attribution.
//
// Zoom buttons are web-only. On a phone, pinch already covers zoom and the
// thumb zone is reserved for locate - shipping zoom buttons there would spend
// the most reachable part of the screen on the least necessary control.

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

// The mock implements the slice of the map API this module actually uses
// (addControl / removeControl). The intersection keeps the recorded `controls`
// array visible to assertions while satisfying attachMapChrome's parameter,
// without loosening that function's real signature to accommodate a test.
function map() {
  return new MockMap({}) as unknown as MockMap & MapLibreMap
}

function controlsOf(m: MockMap, kind: new (...args: never[]) => unknown) {
  return m.controls.filter((c) => c.control instanceof kind)
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('attachMapChrome', () => {
  it('puts compass and locate in the bottom-right thumb zone', () => {
    const m = map()

    attachMapChrome(m, { showZoomButtons: false, units: 'imperial' })

    expect(controlsOf(m, NavigationControl)[0].position).toBe('bottom-right')
    expect(controlsOf(m, GeolocateControl)[0].position).toBe('bottom-right')
  })

  it('puts the scale bar bottom-left, clear of the thumb zone', () => {
    const m = map()

    attachMapChrome(m, { showZoomButtons: false, units: 'imperial' })

    expect(controlsOf(m, ScaleControl)[0].position).toBe('bottom-left')
  })

  it('tracks the user continuously rather than taking a single fix', () => {
    const m = map()

    attachMapChrome(m, { showZoomButtons: false, units: 'imperial' })
    const locate = controlsOf(m, GeolocateControl)[0].control as GeolocateControl

    expect(locate.options?.trackUserLocation).toBe(true)
  })

  it('shows zoom buttons on web, where there is no pinch gesture', () => {
    const m = map()

    attachMapChrome(m, { showZoomButtons: true, units: 'imperial' })
    const nav = controlsOf(m, NavigationControl)[0].control as NavigationControl

    expect(nav.options?.showZoom).toBe(true)
  })

  it('hides zoom buttons on touch, keeping the thumb zone for locate', () => {
    const m = map()

    attachMapChrome(m, { showZoomButtons: false, units: 'imperial' })
    const nav = controlsOf(m, NavigationControl)[0].control as NavigationControl

    expect(nav.options?.showZoom).toBe(false)
  })

  it('always keeps the compass, whatever the platform - tapping it resets north-up', () => {
    for (const showZoomButtons of [true, false]) {
      resetMapLibreMock()
      const m = map()

      attachMapChrome(m, { showZoomButtons, units: 'imperial' })
      const nav = controlsOf(m, NavigationControl)[0].control as NavigationControl

      expect(nav.options?.showCompass).toBe(true)
    }
  })

  it.each([
    ['imperial', 'imperial'],
    ['metric', 'metric'],
  ] as const)('renders the scale bar in the %s unit preference', (units, expected) => {
    const m = map()

    attachMapChrome(m, { showZoomButtons: false, units })
    const scale = controlsOf(m, ScaleControl)[0].control as ScaleControl

    expect(scale.options?.unit).toBe(expected)
  })

  it('detaches every control it added, so a remount cannot stack duplicates', () => {
    const m = map()

    const detach = attachMapChrome(m, { showZoomButtons: true, units: 'imperial' })
    expect(m.controls.length).toBeGreaterThan(0)

    detach()

    expect(m.controls).toHaveLength(0)
  })
})
