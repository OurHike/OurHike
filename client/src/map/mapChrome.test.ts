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

    attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: true,
    })

    expect(controlsOf(m, NavigationControl)[0].position).toBe('bottom-right')
    expect(controlsOf(m, GeolocateControl)[0].position).toBe('bottom-right')
  })

  it('puts the scale bar bottom-left, clear of the thumb zone', () => {
    const m = map()

    attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: true,
    })

    expect(controlsOf(m, ScaleControl)[0].position).toBe('bottom-left')
  })

  it('tracks the user continuously rather than taking a single fix', () => {
    const m = map()

    attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: true,
    })
    const locate = controlsOf(m, GeolocateControl)[0].control as GeolocateControl

    expect(locate.options?.trackUserLocation).toBe(true)
  })

  it('shows zoom buttons on web, where there is no pinch gesture', () => {
    const m = map()

    attachMapChrome(m, {
      showZoomButtons: true,
      units: 'imperial',
      locationEnabled: true,
    })
    const nav = controlsOf(m, NavigationControl)[0].control as NavigationControl

    expect(nav.options?.showZoom).toBe(true)
  })

  it('hides zoom buttons on touch, keeping the thumb zone for locate', () => {
    const m = map()

    attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: true,
    })
    const nav = controlsOf(m, NavigationControl)[0].control as NavigationControl

    expect(nav.options?.showZoom).toBe(false)
  })

  it('always keeps the compass, whatever the platform - tapping it resets north-up', () => {
    for (const showZoomButtons of [true, false]) {
      resetMapLibreMock()
      const m = map()

      attachMapChrome(m, { showZoomButtons, units: 'imperial', locationEnabled: true })
      const nav = controlsOf(m, NavigationControl)[0].control as NavigationControl

      expect(nav.options?.showCompass).toBe(true)
    }
  })

  it.each([
    ['imperial', 'imperial'],
    ['metric', 'metric'],
  ] as const)('renders the scale bar in the %s unit preference', (units, expected) => {
    const m = map()

    attachMapChrome(m, { showZoomButtons: false, units, locationEnabled: true })
    const scale = controlsOf(m, ScaleControl)[0].control as ScaleControl

    expect(scale.options?.unit).toBe(expected)
  })

  it('detaches every control it added, so a remount cannot stack duplicates', () => {
    const m = map()

    const detach = attachMapChrome(m, {
      showZoomButtons: true,
      units: 'imperial',
      locationEnabled: true,
    })
    expect(m.controls.length).toBeGreaterThan(0)

    detach()

    expect(m.controls).toHaveLength(0)
  })

  // The order MapView actually unmounts in: the map-building effect is declared
  // first, so React runs ITS cleanup - `map.remove()`, which detaches every
  // control itself - before this one. Removing them a second time called each
  // control's `onRemove` on a map reference it had already dropped, and the
  // TypeError escaped an effect cleanup with no error boundary over it: React
  // unmounted the entire app. Leaving the map tab went white, which is how the
  // Downloads tab came to "show nothing".
  it('survives a map that was already removed, rather than taking the app down', () => {
    const m = map()
    const detach = attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: true,
    })

    m.remove()

    expect(() => detach()).not.toThrow()
  })

  it('leaves a removed map alone rather than detaching its controls twice', () => {
    const m = map()
    const detach = attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: true,
    })

    m.remove()
    detach()

    // `remove()` already emptied it. The assertion that matters is that detach
    // did not reach for the controls again - `controls` staying empty is what
    // the (now faithful) mock lets us see.
    expect(m.controls).toHaveLength(0)
  })
})

describe('the locate control, against the location preference (#312)', () => {
  it('is not attached at all while location is off', () => {
    // Three things followed from attaching it regardless, and all three were
    // visible to a hiker who had tapped "Not now" during onboarding: a browser
    // permission prompt from a control the app's own gate said was off, a blue
    // dot on the map while the header still said "Looking for GPS…", and a
    // second high-accuracy watch on the same battery as lib/useGeolocation's.
    const m = map()

    attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: false,
    })

    expect(controlsOf(m, GeolocateControl)).toHaveLength(0)
  })

  it('keeps the compass and the scale bar, which owe nothing to location', () => {
    // The map does not lose chrome because GPS is off. North-up and a scale
    // bar are as useful on a map you are reading as on one you are standing in.
    const m = map()

    attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: false,
    })

    expect(controlsOf(m, NavigationControl)).toHaveLength(1)
    expect(controlsOf(m, ScaleControl)).toHaveLength(1)
  })

  it('detaches cleanly when it was never attached', () => {
    // The detach loop runs over what was built, and a null locate must not
    // reach removeControl - which throws on a control it does not hold, from
    // an effect cleanup with no error boundary above it (see the note in
    // mapChrome.ts).
    const m = map()

    const detach = attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: false,
    })

    expect(() => detach()).not.toThrow()
  })
})
