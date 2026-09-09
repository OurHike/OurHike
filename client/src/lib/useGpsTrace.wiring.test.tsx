// The seam nothing was testing (#1180).
//
// Reported from a real walk: recording ran and stored ZERO points. The two
// halves each had a suite proving they worked - `useGeolocation.test.ts` shows
// `onFix` is called for every callback, `gpsTrace.test.ts` shows `record`
// stores what it is handed - and NOTHING asserted that App.tsx joins them up.
// A break anywhere in that join is invisible to both files and to the type
// checker, because the types line up whether or not the wire is connected.
//
// So this file drives the two hooks the way App.tsx does, over a real
// IndexedDB (fake-indexeddb, as archiveDownload.realIdb.test.ts does), and
// asserts a fix that enters the watch comes back out of the trace. It is the
// smallest test that would have failed before a walk rather than during one.

import 'fake-indexeddb/auto'

import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { clear as clearIdb } from 'idb-keyval'

import { createGpsTrace } from './gpsTrace'
import { useGpsTrace } from './useGpsTrace'
import { useGeolocation } from './useGeolocation'
import { buildTrailIndex, type TrailIndex } from './trailPosition'

type WatchSuccess = (position: GeolocationPosition) => void

function stubGeolocation({ pollAnswers = true }: { pollAnswers?: boolean } = {}) {
  let onSuccess: WatchSuccess | undefined
  let pollSuccess: WatchSuccess | undefined
  let pollFail: (() => void) | undefined
  let pollOptions: PositionOptions | undefined

  const watchPosition = vi.fn((success: WatchSuccess) => {
    onSuccess = success
    return 7
  })

  // The polled half. Held rather than answered immediately so a test can
  // decide whether a stationary phone hands one over at all - the open
  // question this whole mechanism exists to settle.
  const getCurrentPosition = vi.fn(
    (success: WatchSuccess, failure: () => void, options?: PositionOptions) => {
      pollSuccess = success
      pollFail = failure
      pollOptions = options
    },
  )

  vi.stubGlobal('navigator', {
    geolocation: { watchPosition, getCurrentPosition, clearWatch: vi.fn() },
  })

  return {
    watchPosition,
    getCurrentPosition,
    /** The options the poll was asked with. `maximumAge` is the load-bearing
     *  one, and reading it by tuple index would not survive the signature
     *  changing under the test. */
    pollOptions: () => pollOptions,
    /** The platform answering a poll, or refusing it. */
    answerPoll: (lon: number, lat: number, accuracy: number, timestamp: number) =>
      act(() => {
        if (!pollAnswers) {
          pollFail?.()
          return
        }
        pollSuccess?.({
          coords: {
            longitude: lon,
            latitude: lat,
            accuracy,
            altitude: null,
            altitudeAccuracy: null,
            speed: null,
            heading: null,
          },
          timestamp,
        } as unknown as GeolocationPosition)
      }),
    /** A fix arriving from the platform, exactly as the watch delivers one. */
    reportFix: (lon: number, lat: number, accuracy: number, timestamp: number) =>
      act(() => {
        onSuccess?.({
          coords: {
            longitude: lon,
            latitude: lat,
            accuracy,
            altitude: null,
            altitudeAccuracy: null,
            speed: null,
            heading: null,
          },
          timestamp,
        } as unknown as GeolocationPosition)
      }),
  }
}

/** App.tsx's two lines, and nothing else: the recorder, then the watch it
 *  taps. If these stop matching App.tsx this test is worth less, so the
 *  shape is kept deliberately literal. */
function useRecorderAndWatch(
  locationAllowed: boolean,
  trailIndex: TrailIndex | null = null,
) {
  const gpsTrace = useGpsTrace(trailIndex, locationAllowed)
  const gps = useGeolocation(locationAllowed, {
    onFix: gpsTrace.onFix,
    keepAwake: gpsTrace.status.recording,
  })
  return { gpsTrace, gps }
}

// The native watch is never available in jsdom, which is the correct answer
// and the one every field test on the PR preview also gets. What is asserted
// here is that the recorder does not fall over reaching for it, and that a
// browser reports `not-native` rather than a failure.
vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => false, getPlatform: () => 'web' },
  registerPlugin: () => ({
    addWatcher: () => Promise.reject(new Error('web')),
    removeWatcher: () => Promise.resolve(),
  }),
}))

afterEach(async () => {
  // Before cleanup: several tests below install fake timers, and the IndexedDB
  // teardown underneath needs real ones.
  vi.useRealTimers()
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  await clearIdb()
})

/** A stand-in for the browser's long-task observer, installed before the hook
 *  renders because `createStallMeter` reads support once at construction. */
function stubLongTasks() {
  const fire: ((durations: number[]) => void)[] = []

  class FakeObserver {
    private callback: PerformanceObserverCallback

    constructor(callback: PerformanceObserverCallback) {
      this.callback = callback
    }

    observe() {
      fire.push((durations) =>
        this.callback(
          {
            getEntries: () => durations.map((duration) => ({ duration })),
          } as unknown as PerformanceObserverEntryList,
          this as unknown as PerformanceObserver,
        ),
      )
    }
    disconnect() {}
    takeRecords() {
      return []
    }
    static supportedEntryTypes = ['longtask']
  }

  vi.stubGlobal('PerformanceObserver', FakeObserver)

  return (...durations: number[]) => act(() => fire.forEach((f) => f(durations)))
}

describe('the recorder wired to the watch, as App.tsx joins them', () => {
  it('stops ASKING for fixes when the hiker turns location off mid-recording', async () => {
    // #1201. The watch stopped correctly - useGeolocation gets the flag - and
    // the poll did not, so the app went on calling getCurrentPosition with
    // high accuracy on, every five seconds, after being told not to. Nothing
    // left the phone; that is not the point.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const gps = stubGeolocation()
    const { result, rerender } = renderHook(
      ({ allowed }) => useRecorderAndWatch(allowed),
      { initialProps: { allowed: true } },
    )

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })
    expect(gps.getCurrentPosition).toHaveBeenCalledOnce()

    rerender({ allowed: false })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    // Six more intervals passed and not one of them asked.
    expect(gps.getCurrentPosition).toHaveBeenCalledOnce()
  })

  it('leaves the recording OPEN rather than ending it for the hiker', async () => {
    // The other half of #1201, and the half it would be easy to get wrong.
    // gpsTrace.ts's `resume` argues the case: a recording that ends itself
    // hands back a truncated trace that looks complete, and the walk is not
    // repeatable that day. So the recording stays open and inert, and the
    // hiker decides - which is only a decision if More.tsx keeps the Stop
    // button on screen, asserted separately in More.test.tsx.
    stubGeolocation()
    const { result, rerender } = renderHook(
      ({ allowed }) => useRecorderAndWatch(allowed),
      { initialProps: { allowed: true } },
    )

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    rerender({ allowed: false })

    expect(result.current.gpsTrace.status.recording).toBe(true)
    expect(result.current.gpsTrace.locationAllowed).toBe(false)
  })

  it('stamps the main-thread stall onto the fix that follows it', async () => {
    // THE SIXTH WALK'S SEAM. A meter that measures perfectly and never reaches
    // a sample is the `useGeolocation`/`gpsTrace` failure again, one file
    // along: both halves pass their own suites while the column stays empty
    // and nobody learns that until a walk comes back.
    const jam = stubLongTasks()
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    jam(310, 80)
    reportFix(-71.3033, 44.2705, 12, 1_724_800_000_000)
    await waitFor(() => expect(result.current.gpsTrace.status.samples).toBe(1))

    // Stopped so the buffer reaches disk, then read by a recorder that shares
    // nothing with the hook's but the IndexedDB keys.
    await act(async () => {
      result.current.gpsTrace.onStop()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(false))
    const reader = createGpsTrace()
    await reader.resume()
    const [sample] = await reader.readAll()

    expect(sample.blockedMs).toBe(390)
    expect(sample.worstTaskMs).toBe(310)
    // And on the screen, where a tester can act on it while still outside.
    expect(result.current.gpsTrace.stall).toEqual({ supported: true, worstMs: 310 })
  })

  it('reports the stall as unmeasured where the browser has no long tasks', async () => {
    // jsdom by default, and every browser on iOS. The screen must say so
    // rather than print a reassuring zero.
    stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    expect(result.current.gpsTrace.stall).toEqual({ supported: false, worstMs: null })
  })

  it('stamps which phone and which runtime onto the sample', async () => {
    // The same seam as the stall meter above, and it fails the same silent
    // way: a platform reader that works perfectly and never reaches a sample
    // leaves the column empty, and nobody finds out until two traces from two
    // phones turn out to be unsortable.
    vi.stubGlobal('navigator', {
      geolocation: {
        watchPosition: vi.fn(() => 7),
        getCurrentPosition: vi.fn(),
        clearWatch: vi.fn(),
      },
      userAgent: 'Mozilla/5.0 (Linux; Android 15; Pixel 9) Mobile Safari/537.36',
    })
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    // Delivered through the watch the stub registered above.
    const success = (
      navigator.geolocation.watchPosition as unknown as { mock: { calls: unknown[][] } }
    ).mock.calls[0][0] as (position: GeolocationPosition) => void
    act(() => {
      success({
        coords: {
          longitude: -71.3033,
          latitude: 44.2705,
          accuracy: 12,
          altitude: null,
          altitudeAccuracy: null,
          speed: null,
          heading: null,
        },
        timestamp: 1_724_800_000_000,
      } as unknown as GeolocationPosition)
    })
    await waitFor(() => expect(result.current.gpsTrace.status.samples).toBe(1))

    await act(async () => {
      result.current.gpsTrace.onStop()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(false))
    const reader = createGpsTrace()
    await reader.resume()
    const [sample] = await reader.readAll()

    expect(sample.shell).toBe('web')
    expect(sample.deviceOs).toBe('android')
  })

  it('stores a fix that arrives while recording', async () => {
    // THE ONE THAT MATTERS. A walk that records zero points fails exactly
    // here, and passes both halves' own suites while doing it.
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    reportFix(-71.3033, 44.2705, 12, 1_724_800_000_000)

    await waitFor(() => expect(result.current.gpsTrace.status.samples).toBe(1))
  })

  it('keeps storing across several fixes', async () => {
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    reportFix(-71.3033, 44.2705, 12, 1_000)
    reportFix(-71.3034, 44.2706, 14, 2_000)
    reportFix(-71.3035, 44.2707, 11, 3_000)

    await waitFor(() => expect(result.current.gpsTrace.status.samples).toBe(3))
  })

  it('stores nothing before recording starts', async () => {
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    reportFix(-71.3033, 44.2705, 12, 1_000)

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(result.current.gpsTrace.status.samples).toBe(0)
  })

  it('records nothing when location is switched off, because there is no watch', async () => {
    // The section is gated on this preference for exactly this reason: with
    // it off `useGeolocation` registers nothing, so Start would look like it
    // worked and store zero.
    const gps = stubGeolocation()
    renderHook(() => useRecorderAndWatch(false))

    expect(gps.watchPosition).not.toHaveBeenCalled()
  })

  it('carries the marker the hiker set onto a fix that arrives after it', async () => {
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))
    await act(async () => {
      result.current.gpsTrace.onMark('walking')
    })

    reportFix(-71.3033, 44.2705, 12, 1_000)

    await waitFor(() => expect(result.current.gpsTrace.status.samples).toBe(1))
    expect(result.current.gpsTrace.status.marker).toBe('walking')
  })

  it('reports that the trail columns are empty because nothing is downloaded', async () => {
    // THE FIRST FIELD TRACE'S FINDING. 136 rows came back with `mile`,
    // `off_trail_ft` and `off_tread_ft` blank, and the screen had no way to
    // say so - the recorder wrote exactly what it was handed, which was null.
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    reportFix(-74.187, 41.735, 23, 1_000)

    await waitFor(() => expect(result.current.gpsTrace.trailFix).toBe('no-trail-data'))
  })

  it('tells a downloaded-but-distant trail apart from no trail at all', async () => {
    // The other half of the same blank, and the one a download does not fix.
    // The walk that produced the first trace was about 27 miles from the
    // corridor, so `locateOnTrail` declined to guess - correctly, and
    // indistinguishably from the case above until now.
    const { reportFix } = stubGeolocation()
    const index = buildTrailIndex({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: { source: 'centerline' },
          geometry: {
            type: 'LineString',
            coordinates: [
              [-73.58, 41.56],
              [-73.58, 41.58],
            ],
          },
        },
      ],
    })
    const { result } = renderHook(() => useRecorderAndWatch(true, index))

    await act(async () => {
      result.current.gpsTrace.onStart()
    })

    // On the centerline.
    reportFix(-73.58, 41.57, 12, 1_000)
    await waitFor(() => expect(result.current.gpsTrace.trailFix).toBe('recorded'))

    // Far west of it, which is where the first real trace was taken.
    reportFix(-74.187, 41.735, 23, 2_000)
    await waitFor(() => expect(result.current.gpsTrace.trailFix).toBe('off-corridor'))
  })

  it('calls a browser not-native rather than failed, once asked for', async () => {
    // The PR preview is a browser. `failed` there would read as a defect in
    // the app rather than as the platform saying no.
    stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onBackgroundChange(true)
    })

    await waitFor(() => expect(result.current.gpsTrace.background).toBe('not-native'))
  })

  it('leaves the background watch off until it is asked for', async () => {
    stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    expect(result.current.gpsTrace.background).toBe('off')
    expect(result.current.gpsTrace.backgroundWanted).toBe(false)
  })

  it('keeps recording from the web watch while the native one is unavailable', async () => {
    // The failure worth guarding: asking for background recording on a phone
    // that cannot do it must not cost the fixes that WERE arriving.
    const { reportFix } = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onStart()
      result.current.gpsTrace.onBackgroundChange(true)
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    reportFix(-74.187, 41.735, 23, 1_000)

    await waitFor(() => expect(result.current.gpsTrace.status.samples).toBe(1))
  })

  it('asks for a fix on a timer, because standing still the platform volunteers few', async () => {
    // The fourth field trace: 0.87 fixes a minute standing still against 7.58
    // walking, with the screen awake and the page visible the whole time. The
    // API has no rate control - watchPosition takes enableHighAccuracy,
    // timeout and maximumAge, and none of them asks for a frequency - so the
    // only lever left is asking.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const gps = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))
    expect(gps.getCurrentPosition).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    expect(gps.getCurrentPosition).toHaveBeenCalledOnce()
    // maximumAge 0, or the answer may be the fix the watch already gave us -
    // and counting one fix twice shrinks the apparent scatter, making the
    // phone look better than it is.
    expect(gps.pollOptions()).toMatchObject({
      enableHighAccuracy: true,
      maximumAge: 0,
    })
  })

  it('asks for nothing while no recording is running', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const gps = stubGeolocation()
    renderHook(() => useRecorderAndWatch(true))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(gps.getCurrentPosition).not.toHaveBeenCalled()
  })

  it('does not stack polls while one is still waiting', async () => {
    // A poll waiting out its timeout must not have four more queued behind
    // it, each holding the chipset awake on somebody's last 20%.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const gps = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))
    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(25_000)
    })

    expect(gps.getCurrentPosition).toHaveBeenCalledOnce()
  })

  it('records a polled fix, so a stationary trace is not only what was volunteered', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const gps = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))
    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })
    gps.answerPoll(-74.187, 41.735, 21, 2_000)

    await waitFor(() => expect(result.current.gpsTrace.status.samples).toBe(1))
  })

  it('does not re-register the watch when a recording starts', async () => {
    // `keepAwake` flips true on Start. If that re-ran the watch effect it
    // would tear the watch down and rebuild it at the moment recording
    // begins - the same defect the `awake` flag already fixed for pocketing,
    // in the one place it would cost the first fixes of every walk.
    const gps = stubGeolocation()
    const { result } = renderHook(() => useRecorderAndWatch(true))
    expect(gps.watchPosition).toHaveBeenCalledTimes(1)

    await act(async () => {
      result.current.gpsTrace.onStart()
    })
    await waitFor(() => expect(result.current.gpsTrace.status.recording).toBe(true))

    expect(gps.watchPosition).toHaveBeenCalledTimes(1)
  })
})
