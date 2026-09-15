import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  MockMap,
  NavigationControl,
  GeolocateControl,
  ScaleControl,
  resetMapLibreMock,
} from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { attachMapChrome, ReportControl } from './mapChrome'
import { POI_PIN_MIN_ZOOM } from './poiLayers'

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

  it('caps how far one tap of locate takes the camera (#315)', () => {
    // MapLibre's default fits the accuracy circle, which for a good fix is a
    // few metres across - so one tap flew from the corridor view to roughly
    // z15 and traded the whole picture of where somebody is going for the
    // answer to where they are.
    const m = map()

    attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled: true,
    })
    const locate = controlsOf(m, GeolocateControl)[0].control as GeolocateControl

    // The zoom the waypoint pins start drawing at, so the camera lands on the
    // closest view that also shows what is around them. Asserted against the
    // constant rather than a literal, so the two cannot drift.
    // Cast because MapLibre types the control's `fitBoundsOptions` as `{}` -
    // the property is real at runtime and invisible to the compiler.
    const fit = locate.options?.fitBoundsOptions as { maxZoom?: number } | undefined
    expect(fit?.maxZoom).toBe(POI_PIN_MIN_ZOOM)
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

describe('the report control, in the shared chrome (#1438, D15)', () => {
  // D15: "Report a problem" gets a named door on exactly two screens - Today
  // and the Map. The map's is a `report` control on the SHARED chrome, never a
  // button drawn on one screen, because a control that is part of the chrome
  // cannot become a control one map has and another does not. The long press
  // keeps working and keeps raising PressPlate; what it stops being is the
  // only way in.

  function attach(onReport: (() => void) | undefined, locationEnabled = true) {
    const m = map()
    const detach = attachMapChrome(m, {
      showZoomButtons: false,
      units: 'imperial',
      locationEnabled,
      onReport,
    })
    return { m, detach }
  }

  function reportControl(m: MockMap): ReportControl {
    const found = m.controls.find((c) => c.control instanceof ReportControl)
    if (found === undefined) throw new Error('no report control attached')
    return found.control as ReportControl
  }

  it('sits in the bottom-right stack with the controls a walking hiker reaches for', () => {
    const { m } = attach(vi.fn())

    expect(controlsOf(m, ReportControl)[0].position).toBe('bottom-right')
  })

  it('is absent when the shell has nowhere to send a report', () => {
    // A door with nothing behind it is the control D10 forbids - one that
    // looks pressable and is not. Absent is the honest shape.
    const { m } = attach(undefined)

    expect(controlsOf(m, ReportControl)).toHaveLength(0)
  })

  it('goes on BELOW locate, so the mid-walk controls stay nearest the thumb', () => {
    // Order of addition is order down the stack in MapLibre, and the stack
    // grows away from the thumb. Locate is what somebody uses while walking;
    // filing a report is a thing you stop to do.
    const { m } = attach(vi.fn())
    const order = m.controls
      .filter((c) => c.position === 'bottom-right')
      .map((c) => c.control.constructor.name)

    expect(order.indexOf('ReportControl')).toBe(order.length - 1)
    expect(order.indexOf('ReportControl')).toBeGreaterThan(
      order.indexOf('GeolocateControl'),
    )
  })

  it('stays last in the stack when location is off and there is no locate', () => {
    const { m } = attach(vi.fn(), false)
    const order = m.controls
      .filter((c) => c.position === 'bottom-right')
      .map((c) => c.control.constructor.name)

    expect(order).toEqual(['NavigationControl', 'ReportControl'])
  })

  it('wears the same chip as compass and locate rather than drawing its own', () => {
    // THE ACCEPTANCE SENTENCE, asserted structurally because jsdom does no
    // layout: it is "visually indistinguishable in size/radius/shadow from
    // compass and locate". Those three properties come from maplibre-gl.css's
    // `.maplibregl-ctrl-group` plus chrome.css's `--map-control-size` override,
    // so the way to be indistinguishable is to be the same construction - a
    // ctrl-group holding one button - and not a hand-set width and radius that
    // agree with the neighbours until one of them changes.
    const { m } = attach(vi.fn())
    const container = reportControl(m).container

    expect(container?.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['maplibregl-ctrl', 'maplibregl-ctrl-group']),
    )
    expect(container?.querySelectorAll('button')).toHaveLength(1)
  })

  it('says what it is, for a thumb and for a screen reader', () => {
    const { m } = attach(vi.fn())
    const button = reportControl(m).container?.querySelector('button')

    expect(button?.getAttribute('aria-label')).toBe('Report a problem')
    expect(button?.getAttribute('title')).toBe('Report a problem')
    expect(button?.getAttribute('type')).toBe('button')
  })

  it('opens the report window when pressed', () => {
    const onReport = vi.fn()
    const { m } = attach(onReport)

    reportControl(m).container?.querySelector('button')?.click()

    expect(onReport).toHaveBeenCalledTimes(1)
  })

  it('comes off with the rest, so a remount cannot stack two', () => {
    const { m, detach } = attach(vi.fn())
    expect(controlsOf(m, ReportControl)).toHaveLength(1)

    detach()

    expect(m.controls).toHaveLength(0)
  })
})
