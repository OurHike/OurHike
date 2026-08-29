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

import { useGpsTrace } from './useGpsTrace'
import { useGeolocation } from './useGeolocation'
import { buildTrailIndex, type TrailIndex } from './trailPosition'

type WatchSuccess = (position: GeolocationPosition) => void

function stubGeolocation() {
  let onSuccess: WatchSuccess | undefined

  const watchPosition = vi.fn((success: WatchSuccess) => {
    onSuccess = success
    return 7
  })

  vi.stubGlobal('navigator', {
    geolocation: { watchPosition, clearWatch: vi.fn() },
  })

  return {
    watchPosition,
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
  const gpsTrace = useGpsTrace(trailIndex)
  const gps = useGeolocation(locationAllowed, {
    onFix: gpsTrace.onFix,
    keepAwake: gpsTrace.status.recording,
  })
  return { gpsTrace, gps }
}

afterEach(async () => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  await clearIdb()
})

describe('the recorder wired to the watch, as App.tsx joins them', () => {
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
