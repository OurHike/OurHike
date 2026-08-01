import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
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
