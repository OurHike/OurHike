import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { Location as PluginLocation } from '@capacitor-community/background-geolocation'

import {
  BACKGROUND_MESSAGE,
  backgroundWatchAvailable,
  fixFromPluginLocation,
  startBackgroundWatch,
  type BackgroundGeolocationLike,
} from './backgroundGeolocation'

// What CAN be tested from a machine with no Android SDK and no phone: the
// mapping, the platform gate, and the teardown. What cannot: anything on the
// far side of registerPlugin. The module header says so and so does the PR -
// a green run here is not evidence that background recording works.

vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => nativePlatform },
  registerPlugin: () => ({}),
}))

let nativePlatform = false

function pluginLocation(over: Partial<PluginLocation> = {}): PluginLocation {
  return {
    latitude: 41.7348,
    longitude: -74.1873,
    accuracy: 11,
    altitude: 180.4,
    altitudeAccuracy: 4,
    bearing: 268,
    speed: 0.55,
    simulated: false,
    time: 1_788_030_532_502,
    ...over,
  }
}

/** A stand-in for the plugin, with the watcher id arriving on a promise the
 *  way the real one does. */
function stubPlugin() {
  let deliver: ((l?: PluginLocation, e?: { code?: string } & Error) => void) | undefined
  let resolveId: (id: string) => void = () => {}
  const removeWatcher = vi.fn(() => Promise.resolve())

  const addWatcher = vi.fn((_options: unknown, callback: typeof deliver) => {
    deliver = callback
    return new Promise<string>((resolve) => {
      resolveId = resolve
    })
  })

  return {
    plugin: { addWatcher, removeWatcher } as unknown as BackgroundGeolocationLike,
    addWatcher,
    removeWatcher,
    registerId: (id = 'w1') => resolveId(id),
    fix: (over?: Partial<PluginLocation>) => deliver?.(pluginLocation(over)),
    fail: (code?: string) =>
      deliver?.(undefined, Object.assign(new Error('nope'), { code })),
  }
}

beforeEach(() => {
  nativePlatform = false
})
afterEach(() => vi.clearAllMocks())

describe('backgroundWatchAvailable', () => {
  it('is false in a browser, which is where every field test has been', () => {
    // The PR preview is a web deployment. Reporting this as broken rather
    // than as "not here" is how a tester stops reading the screen.
    expect(backgroundWatchAvailable()).toBe(false)
  })

  it('is true in a native shell', () => {
    nativePlatform = true
    expect(backgroundWatchAvailable()).toBe(true)
  })
})

describe('fixFromPluginLocation', () => {
  it('renames bearing to heading at the boundary, so one word means one thing', () => {
    expect(fixFromPluginLocation(pluginLocation({ bearing: 268 })).headingDeg).toBe(268)
  })

  it('keeps the platform fix time rather than the wall clock', () => {
    // The recorder measures CADENCE. Substituting Date.now() folds delivery
    // latency into the fix interval and hides it.
    const now = vi.fn(() => 999)
    expect(fixFromPluginLocation(pluginLocation({ time: 1_234 }), now).timestampMs).toBe(
      1_234,
    )
    expect(now).not.toHaveBeenCalled()
  })

  it('falls back to the wall clock only when the platform gives no time', () => {
    expect(
      fixFromPluginLocation(pluginLocation({ time: null }), () => 999).timestampMs,
    ).toBe(999)
  })

  it('carries a null altitude through rather than defaulting it to zero', () => {
    // Absent means unknown, never zero - a hiker at an unknown elevation is
    // not a hiker at sea level.
    const fix = fixFromPluginLocation(pluginLocation({ altitude: null, speed: null }))
    expect(fix.altitudeM).toBeNull()
    expect(fix.speedMps).toBeNull()
  })

  it('carries the mock-location flag, so a faked trace cannot read as real', () => {
    expect(fixFromPluginLocation(pluginLocation({ simulated: true })).simulated).toBe(
      true,
    )
  })
})

describe('startBackgroundWatch', () => {
  it('asks for a background watch, not merely a foreground one', async () => {
    // `backgroundMessage` is what makes it background at all - the plugin
    // only guarantees foreground updates without it, on both platforms. This
    // is the assertion that the whole feature turns on.
    const { plugin, addWatcher } = stubPlugin()

    startBackgroundWatch({ onFix: vi.fn(), onProblem: vi.fn() }, plugin)

    expect(addWatcher.mock.calls[0][0]).toMatchObject({
      backgroundMessage: BACKGROUND_MESSAGE,
      distanceFilter: 0,
      stale: false,
    })
  })

  it('takes every fix, including the ones that have not moved', () => {
    // distanceFilter 0 on purpose: measuring how far a STATIONARY phone
    // appears to wander is the thing this instrument most needs and has
    // least of, and a distance filter deletes exactly that.
    const { plugin, addWatcher } = stubPlugin()

    startBackgroundWatch({ onFix: vi.fn(), onProblem: vi.fn() }, plugin)

    expect(addWatcher.mock.calls[0][0]).toHaveProperty('distanceFilter', 0)
  })

  it('hands fixes on in the recorder’s own shape', () => {
    const onFix = vi.fn()
    const { plugin, fix } = stubPlugin()

    startBackgroundWatch({ onFix, onProblem: vi.fn() }, plugin)
    fix({ accuracy: 23.2 })

    expect(onFix).toHaveBeenCalledWith(expect.objectContaining({ accuracyM: 23.2 }))
  })

  it('tells a refused permission apart from anything else', () => {
    // Different sentences on the screen: one is a settings screen the person
    // must visit, the other is "we do not know".
    const onProblem = vi.fn()
    const { plugin, fail } = stubPlugin()

    startBackgroundWatch({ onFix: vi.fn(), onProblem }, plugin)
    fail('NOT_AUTHORIZED')

    expect(onProblem).toHaveBeenCalledWith('not-authorized')
  })

  it('reports an unexplained failure as its own thing', () => {
    const onProblem = vi.fn()
    const { plugin, fail } = stubPlugin()

    startBackgroundWatch({ onFix: vi.fn(), onProblem }, plugin)
    fail('SOMETHING_ELSE')

    expect(onProblem).toHaveBeenCalledWith('failed')
  })

  it('removes the watcher when stopped', async () => {
    const { plugin, removeWatcher, registerId } = stubPlugin()

    const stop = startBackgroundWatch({ onFix: vi.fn(), onProblem: vi.fn() }, plugin)
    registerId('w7')
    await Promise.resolve()
    stop()

    expect(removeWatcher).toHaveBeenCalledWith({ id: 'w7' })
  })

  it('removes a watcher that arrives AFTER it was stopped', async () => {
    // The leak worth testing for. A recording started and stopped inside one
    // second would otherwise leave a foreground service and its
    // undismissable notification running for the life of the app.
    const { plugin, removeWatcher, registerId } = stubPlugin()

    const stop = startBackgroundWatch({ onFix: vi.fn(), onProblem: vi.fn() }, plugin)
    stop()
    registerId('w9')
    await Promise.resolve()

    expect(removeWatcher).toHaveBeenCalledWith({ id: 'w9' })
  })

  it('drops fixes that arrive after it was stopped', () => {
    const onFix = vi.fn()
    const { plugin, fix } = stubPlugin()

    const stop = startBackgroundWatch({ onFix, onProblem: vi.fn() }, plugin)
    stop()
    fix()

    expect(onFix).not.toHaveBeenCalled()
  })

  it('does not remove the same watcher twice', async () => {
    const { plugin, removeWatcher, registerId } = stubPlugin()

    const stop = startBackgroundWatch({ onFix: vi.fn(), onProblem: vi.fn() }, plugin)
    registerId()
    await Promise.resolve()
    stop()
    stop()

    expect(removeWatcher).toHaveBeenCalledTimes(1)
  })
})
