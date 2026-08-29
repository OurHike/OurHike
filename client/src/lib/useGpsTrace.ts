// The recorder, wired (#1180).
//
// A hook rather than forty lines in App.tsx, and that is #937's argument
// rather than a preference: App.tsx is the file every branch collides in, and
// a diagnostic that ships off has no business widening it. What it exports is
// the shape `GpsTraceSettings` already takes, so the screen and the shell
// cannot disagree about what the buttons do.
//
// WHY THE ENRICHMENT HAPPENS HERE AND NOT IN THE RECORDER.
//
// `locateOnTrail` is what the app believed about a fix while somebody was
// standing there, and that belief is the datum - #93 wants drift measured
// against the trail, not against a reconstruction of it. Doing it live means
// the CSV carries the app's own answer; doing it later means shipping a trail
// index to whatever reads the file and hoping a second implementation agrees.
//
// It costs a bucket search per fix, which is the cost #1100 is trying to
// reduce. That is accepted here and nowhere else: this runs only while a
// recording is on, which is a mode somebody turned on deliberately and is
// already paying for in battery.

import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  createGpsTrace,
  downloadTrace,
  sampleFromPosition,
  traceFilename,
  traceToCsv,
  type TraceMarker,
  type TraceStatus,
} from './gpsTrace'
import { locateOnTrail, type TrailIndex } from './trailPosition'
import { useWakeLock, type WakeLockState } from './useWakeLock'

const IDLE: TraceStatus = {
  recording: false,
  startedAt: null,
  marker: null,
  samples: 0,
}

export interface GpsTraceControls {
  status: TraceStatus
  /**
   * Whether the screen is actually being held awake while recording.
   *
   * Passed to the screen rather than kept here: a refused lock means the
   * recording will pause every time the screen darkens, and the tester is the
   * only one who can do anything about that.
   */
  wakeLock: WakeLockState
  /** Hand this to `useGeolocation` - it wants every fix, unfiltered. */
  onFix: (position: GeolocationPosition) => void
  onStart: () => void
  onStop: () => void
  onMark: (marker: TraceMarker) => void
  onExport: () => void
  onDelete: () => void
}

export function useGpsTrace(trailIndex: TrailIndex | null): GpsTraceControls {
  // One recorder for the life of the app. A second would claim the same
  // IndexedDB keys and the two would overwrite each other's chunks.
  const trace = useMemo(() => createGpsTrace(), [])
  const [status, setStatus] = useState<TraceStatus>(IDLE)

  useEffect(() => {
    // A recording that survived a reload resumes without being asked - see
    // `resume`'s note. Nothing here starts one.
    void trace.resume().then(setStatus)
  }, [trace])

  const onFix = useCallback(
    (position: GeolocationPosition) => {
      // Not gated on `status.recording`: this closure is held in a ref by
      // useGeolocation and would be reading a stale flag. The recorder owns
      // that decision and drops the sample itself.
      const at = { lon: position.coords.longitude, lat: position.coords.latitude }
      const reading = trailIndex === null ? null : locateOnTrail(trailIndex, at)
      void trace.record(sampleFromPosition(position, reading)).then(setStatus)
    },
    [trace, trailIndex],
  )

  // Only while recording. See lib/useWakeLock.ts for what this does and does
  // not buy - it stops the screen sleeping on its own, and does not survive
  // the power button.
  const wakeLock = useWakeLock(status.recording)

  const onExport = useCallback(() => {
    void trace
      .readAll()
      .then((samples) =>
        downloadTrace(traceToCsv(samples), traceFilename(trace.status().startedAt)),
      )
  }, [trace])

  return {
    status,
    // Tied to recording rather than offered as its own switch: holding a
    // screen awake for anything else in this app would be a battery cost
    // nobody asked for.
    wakeLock,
    onFix,
    onStart: useCallback(() => void trace.start().then(setStatus), [trace]),
    onStop: useCallback(() => void trace.stop().then(setStatus), [trace]),
    onMark: useCallback(
      (marker: TraceMarker) => void trace.mark(marker).then(setStatus),
      [trace],
    ),
    onExport,
    onDelete: useCallback(() => void trace.clear().then(setStatus), [trace]),
  }
}
