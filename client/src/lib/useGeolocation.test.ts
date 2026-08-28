import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useGeolocation } from './useGeolocation'

// A hiker reads their mile off this, so the states it can be in matter as much
// as the fix itself. "I don't know" has to stay distinguishable from
// "somewhere", and a denied permission has to settle rather than be retried -
// re-prompting for a fix that will never come costs battery on the one device
// someone has out here.

type WatchSuccess = (position: GeolocationPosition) => void
type WatchFailure = (error: GeolocationPositionError) => void

function stubGeolocation() {
  let onSuccess: WatchSuccess | undefined
  let onFailure: WatchFailure | undefined

  const clearWatch = vi.fn()
  const watchPosition = vi.fn((success: WatchSuccess, failure: WatchFailure) => {
    onSuccess = success
    onFailure = failure
    return 7
  })

  vi.stubGlobal('navigator', {
    geolocation: { watchPosition, clearWatch },
    userAgent: '',
    platform: '',
  })

  return {
    watchPosition,
    clearWatch,
    reportFix: (
      coords: { longitude: number; latitude: number; accuracy: number },
      timestamp = 0,
    ) =>
      act(() => {
        onSuccess?.({ coords, timestamp } as unknown as GeolocationPosition)
      }),
    reportFailure: (code: number) =>
      act(() => {
        onFailure?.({ code, PERMISSION_DENIED: 1 } as GeolocationPositionError)
      }),
  }
}

afterEach(() => {
  // Unmounting between cases is not housekeeping here, it is isolation. This
  // hook now listens on `document` for visibility, and a hook left mounted by
  // an earlier test keeps that listener - so one dispatched visibilitychange
  // reached every hook this file had ever rendered, each of them calling the
  // CURRENT test's navigator stub. The count that exposed it was 11 watches
  // where two were expected.
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('useGeolocation', () => {
  it('sits idle until it is switched on, rather than asking for a fix nobody wanted', () => {
    stubGeolocation()

    const { result } = renderHook(() => useGeolocation(false))

    expect(result.current).toEqual({ status: 'idle' })
  })

  it('does not even start a watch while disabled', () => {
    const gps = stubGeolocation()

    renderHook(() => useGeolocation(false))

    expect(gps.watchPosition).not.toHaveBeenCalled()
  })

  it('says it is locating as soon as it is switched on', () => {
    stubGeolocation()

    const { result } = renderHook(() => useGeolocation(true))

    expect(result.current).toEqual({ status: 'locating' })
  })

  it('asks for high accuracy, which is the whole point under tree cover', () => {
    // A coarse fix can be hundreds of feet out, and a mile marker a quarter
    // mile wrong at a junction is worse than no mile marker at all.
    const gps = stubGeolocation()

    renderHook(() => useGeolocation(true))

    expect(gps.watchPosition).toHaveBeenCalledWith(
      expect.any(Function),
      expect.any(Function),
      expect.objectContaining({ enableHighAccuracy: true }),
    )
  })

  it('reports a fix in lon/lat with its accuracy converted to feet', () => {
    const gps = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    gps.reportFix({ longitude: -77.1, latitude: 39.3, accuracy: 10 }, 1_700_000_000_000)

    expect(result.current).toMatchObject({
      status: 'located',
      at: { lon: -77.1, lat: 39.3 },
    })
    const located = result.current as Extract<
      typeof result.current,
      { status: 'located' }
    >
    expect(located.accuracyFeet).toBeCloseTo(32.8084, 3)
    expect(located.fixedAt).toEqual(new Date(1_700_000_000_000))
  })

  it('settles on denied when permission is refused', () => {
    const gps = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    gps.reportFailure(1)

    expect(result.current).toEqual({ status: 'denied' })
  })

  it('releases the watch on denial, making "denied simply stops" true', () => {
    // The header comment promised this and the code did not do it: the watch
    // registration outlived the denial for the life of the tab. Browsers go
    // quiet on a denied watch, but the promise about battery is this hook's
    // to keep, not the browser's.
    const gps = stubGeolocation()
    renderHook(() => useGeolocation(true))

    gps.reportFailure(1)

    expect(gps.clearWatch).toHaveBeenCalledWith(7)
  })

  it('keeps the watch through a timeout, which the next fix can heal', () => {
    // Losing sky for a minute in a canyon must not end the watch - only a
    // denial is settled.
    const gps = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    gps.reportFailure(3) // TIMEOUT
    expect(gps.clearWatch).not.toHaveBeenCalled()

    gps.reportFix({ longitude: -77.1, latitude: 39.3, accuracy: 10 })
    expect(result.current).toMatchObject({ status: 'located' })
  })

  it('separates a refused permission from a fix that merely did not arrive', () => {
    // Different answers to the hiker, and different next steps: one is a
    // settings screen, the other is standing still for a minute.
    const gps = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    gps.reportFailure(3) // TIMEOUT

    expect(result.current).toEqual({ status: 'unavailable' })
  })

  it('says so plainly where there is no geolocation at all', () => {
    vi.stubGlobal('navigator', { userAgent: '', platform: '' })

    const { result } = renderHook(() => useGeolocation(true))

    expect(result.current).toEqual({ status: 'unsupported' })
  })

  it('stops the watch when it is switched back off', () => {
    const gps = stubGeolocation()
    const { rerender, result } = renderHook(({ on }) => useGeolocation(on), {
      initialProps: { on: true },
    })

    rerender({ on: false })

    expect(gps.clearWatch).toHaveBeenCalledWith(7)
    expect(result.current).toEqual({ status: 'idle' })
  })

  it('stops the watch on unmount, so a closed screen is not still draining the battery', () => {
    const gps = stubGeolocation()
    const { unmount } = renderHook(() => useGeolocation(true))

    unmount()

    expect(gps.clearWatch).toHaveBeenCalledWith(7)
  })
})

describe('the watch in the pack (#313)', () => {
  // High-accuracy GNSS is 30-100 mW sustained, and nothing in this client
  // responded to the tab being hidden - not one visibilitychange handler
  // anywhere - so the chipset was pinned on for the life of the tab whether
  // the phone was in a hand or in a pack. On a three-day battery that is real
  // distance.

  /** Hide or show the tab, the way a browser reports it. */
  function setHidden(hidden: boolean) {
    Object.defineProperty(document, 'hidden', { value: hidden, configurable: true })
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
  }

  afterEach(() => {
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
  })

  it('releases the watch when the phone goes into the pocket', () => {
    const { clearWatch } = stubGeolocation()
    renderHook(() => useGeolocation(true))

    setHidden(true)

    expect(clearWatch).toHaveBeenCalledWith(7)
  })

  it('starts watching again when it comes back out', () => {
    const { watchPosition } = stubGeolocation()
    renderHook(() => useGeolocation(true))
    expect(watchPosition).toHaveBeenCalledTimes(1)

    setHidden(true)
    setHidden(false)

    expect(watchPosition).toHaveBeenCalledTimes(2)
  })

  it('keeps the last fix across the pause, so the mile does not blink', () => {
    // Deliberate, and the reason pausing is not just "stop": clearing the fix
    // would blank the header's mile every time the phone came out of a pocket,
    // and a paused watch leaves exactly the state a lost signal already leaves
    // - which this hook has always kept.
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })
    expect(result.current.status).toBe('located')

    setHidden(true)
    expect(result.current.status).toBe('located')

    setHidden(false)
    expect(result.current.status).toBe('located')
  })

  it('does not start a watch at all while hidden and disabled', () => {
    const { watchPosition } = stubGeolocation()
    const { rerender } = renderHook(({ on }) => useGeolocation(on), {
      initialProps: { on: false },
    })

    setHidden(true)
    rerender({ on: true })

    expect(watchPosition).not.toHaveBeenCalled()
  })
})

describe('a fix that says the phone has not moved (#1090)', () => {
  // The state object IS the re-render. Every consumer of this hook reads
  // `status` and `at` and nothing else, so an identical position arriving as a
  // new object re-renders a ~5,100-line App component and recomputes every memo
  // keyed on the fix, for an answer that has not moved. React bails out only
  // when an updater hands back the state it was given, which is what `toBe`
  // below is asserting and why `toEqual` would not do.

  it('keeps the state it already had', () => {
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })
    const first = result.current

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 }, 60_000)

    expect(result.current).toBe(first)
  })

  it('keeps it even when the accuracy and the clock have moved', () => {
    // The position is what this hook is asked for, and it is the only thing a
    // caller reads. A fix at the same coordinates with a better accuracy figure
    // is the same answer about where somebody is - and `fixedAt` freezing with
    // it is the documented cost of that, stated on the bail-out itself.
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    reportFix({ longitude: -77, latitude: 39, accuracy: 40 })
    const first = result.current

    reportFix({ longitude: -77, latitude: 39, accuracy: 4 }, 90_000)

    expect(result.current).toBe(first)
  })

  it('still moves on the smallest change to either coordinate', () => {
    // The other half, and the half that matters for a hiker: this suppresses a
    // repeat, never a movement. There is no threshold here on purpose -
    // suppressing small moves would suppress the first feet of somebody
    // starting to walk, and "lost" is the first of this app's four ways of
    // hurting someone.
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })
    const first = result.current

    reportFix({ longitude: -77, latitude: 39.000001, accuracy: 5 })
    expect(result.current).not.toBe(first)

    const second = result.current
    reportFix({ longitude: -77.000001, latitude: 39.000001, accuracy: 5 })
    expect(result.current).not.toBe(second)
  })

  it('reports the repeat as located after a lost signal, rather than staying unavailable', () => {
    // The bail-out is gated on the CURRENT state being `located`, so a repeat
    // arriving after a timeout is a real change and has to be taken. Missing
    // that gate would leave a hiker on "Looking for GPS..." over a phone that
    // is being told exactly where it is.
    const { reportFix, reportFailure } = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true))

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })
    reportFailure(3)
    expect(result.current.status).toBe('unavailable')

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })

    expect(result.current).toEqual({
      status: 'located',
      at: { lon: -77, lat: 39 },
      accuracyFeet: 5 * 3.28084,
      fixedAt: new Date(0),
    })
  })
})

describe('the seam the trace recorder taps (#1180)', () => {
  // #106's walk has to bring back a measurement, and the thing being measured
  // includes how often the platform actually answers. So the seam sees the
  // watch, not the state - a recorder fed from the deduplicated state would
  // be measuring #1090's optimisation instead of the GPS.

  /** Hide or show the tab, the way a browser reports it. */
  function setHidden(hidden: boolean) {
    Object.defineProperty(document, 'hidden', { value: hidden, configurable: true })
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
  }

  afterEach(() => {
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
  })

  it('hands every fix to onFix', () => {
    const onFix = vi.fn()
    const { reportFix } = stubGeolocation()
    renderHook(() => useGeolocation(true, { onFix }))

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })

    expect(onFix).toHaveBeenCalledTimes(1)
  })

  it('hands over a repeat the render bail-out drops', () => {
    // THE WHOLE REASON THE SEAM IS WHERE IT IS. `maximumAge` lets the platform
    // re-deliver an unchanged fix and #1090 stops that re-rendering the shell.
    // A recorder that inherited that silence would report a gap in the fix
    // cadence that the platform never had.
    const onFix = vi.fn()
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useGeolocation(true, { onFix }))

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })
    const first = result.current
    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })

    expect(result.current).toBe(first)
    expect(onFix).toHaveBeenCalledTimes(2)
  })

  it('reports the fix exactly once per callback', () => {
    // Called outside the setState updater on purpose: an updater may run more
    // than once for a single update, and a recorder inside it would write the
    // same fix twice - inventing a fix rate nobody observed.
    const onFix = vi.fn()
    const { reportFix } = stubGeolocation()
    renderHook(() => useGeolocation(true, { onFix }))

    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })
    reportFix({ longitude: -78, latitude: 40, accuracy: 5 })

    expect(onFix).toHaveBeenCalledTimes(2)
  })

  it('does not re-register the watch when the callback identity changes', () => {
    // A caller passing an inline function would otherwise tear the watch down
    // on every render, which on some platforms restarts acquisition entirely.
    const gps = stubGeolocation()
    const { rerender } = renderHook(({ fn }) => useGeolocation(true, { onFix: fn }), {
      initialProps: { fn: () => {} },
    })

    rerender({ fn: () => {} })
    rerender({ fn: () => {} })

    expect(gps.watchPosition).toHaveBeenCalledTimes(1)
  })

  it('still releases the watch in the pocket when nothing asked to stay awake', () => {
    const { clearWatch } = stubGeolocation()
    renderHook(() => useGeolocation(true, { onFix: vi.fn() }))

    setHidden(true)

    expect(clearWatch).toHaveBeenCalled()
  })

  it('keeps the watch through a pocket while keepAwake is set', () => {
    // A trace that stops when the phone pockets is missing the case #93 most
    // needs. This is not a promise of fixes in a pocket - a hidden tab's JS is
    // throttled regardless - only that this hook is not what ends them.
    const { clearWatch } = stubGeolocation()
    renderHook(() => useGeolocation(true, { onFix: vi.fn(), keepAwake: true }))

    setHidden(true)

    expect(clearWatch).not.toHaveBeenCalled()
  })

  it('goes on recording fixes while hidden and kept awake', () => {
    const onFix = vi.fn()
    const { reportFix } = stubGeolocation()
    renderHook(() => useGeolocation(true, { onFix, keepAwake: true }))

    setHidden(true)
    reportFix({ longitude: -77, latitude: 39, accuracy: 5 })

    expect(onFix).toHaveBeenCalledTimes(1)
  })

  it('leaves the ordinary path alone when nothing passes options', () => {
    const gps = stubGeolocation()
    renderHook(() => useGeolocation(true))

    setHidden(true)

    expect(gps.clearWatch).toHaveBeenCalled()
  })
})
