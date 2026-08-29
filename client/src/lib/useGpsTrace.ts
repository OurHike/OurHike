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
//
// AND WHETHER THAT ENRICHMENT IS HAPPENING IS ITSELF REPORTED.
//
// The first field trace came back with `mile`, `off_trail_ft` and
// `off_tread_ft` empty on all 136 rows - the three columns #93 is waiting on,
// and the reason the enrichment above exists at all. Nothing was broken: the
// walk was about 27 miles from the AT corridor, `locateOnTrail` correctly
// declined to guess, and the recorder wrote what it was handed. The defect is
// that a tester could not learn any of that until the file was open, hours
// later, and that an empty column cannot afterwards say WHICH of the two
// reasons produced it - no trail downloaded on this phone, or nowhere near the
// trail. Same blank, different fix, and the tester is the only one who can do
// either. So the answer is computed per fix and reported to the screen while
// there is still a walk left to salvage.

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

/**
 * Whether the trail columns of the export are being filled, and if not, why.
 *
 * Three answers rather than a boolean because the two failing ones need
 * different things from the tester: `no-trail-data` is fixed by downloading
 * the trail on this phone, `off-corridor` only by walking somewhere else. A
 * boolean would collapse them into the blank column that caused the problem.
 */
export type TrailFix = 'waiting' | 'recorded' | 'no-trail-data' | 'off-corridor'

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
  /**
   * Whether `mile`, `off_trail_ft` and `off_tread_ft` are being written.
   *
   * Reported for the same reason `wakeLock` is: it is a thing about this
   * recording that only the tester can change, and only while they are still
   * out there.
   */
  trailFix: TrailFix
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
  const [trailFix, setTrailFix] = useState<TrailFix>('waiting')

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
      // Set from the fix rather than from `trailIndex` alone: a downloaded
      // trail and a fix 27 miles from it produce the same empty columns, and
      // the index by itself cannot tell them apart.
      setTrailFix(
        trailIndex === null
          ? 'no-trail-data'
          : reading === null
            ? 'off-corridor'
            : 'recorded',
      )
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
    trailFix,
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
