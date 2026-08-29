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

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  createGpsTrace,
  downloadTrace,
  sampleFromNativeFix,
  sampleFromPosition,
  traceFilename,
  traceToCsv,
  type TraceConditions,
  type TraceMarker,
  type TraceReading,
  type TraceStatus,
} from './gpsTrace'
import {
  backgroundWatchAvailable,
  startBackgroundWatch,
  type BackgroundWatchProblem,
} from './backgroundGeolocation'
import { locateOnTrail, type TrailIndex } from './trailPosition'
import { useWakeLock, type WakeLockState } from './useWakeLock'

const IDLE: TraceStatus = {
  recording: false,
  startedAt: null,
  marker: null,
  samples: 0,
  lastSampleAt: null,
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

/**
 * Whether fixes keep arriving with the screen off, and if not, why (#1182).
 *
 * Four answers because the tester's next move differs for each, and the one
 * that reads like a failure - `not-native` - is the ordinary case on the PR
 * preview every field test has used.
 */
export type BackgroundState =
  /** Not asked for: the switch is off, or nothing is recording. */
  | 'off'
  /** Running. Fixes should survive a dark screen and a pocket. */
  | 'on'
  /** A browser, so there is no such thing here. Not an error. */
  | 'not-native'
  /** The permission is missing. On Android 10+ "Allow all the time" is a
   *  settings screen, not a prompt the app can raise. */
  | 'not-authorized'
  /** The plugin failed for some other reason. */
  | 'failed'

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
  /** Whether the recording survives a dark screen, and if not, why. */
  background: BackgroundState
  /** Whether the tester has asked for background recording. Kept here so the
   *  switch is a control rather than a report. */
  backgroundWanted: boolean
  onBackgroundChange: (wanted: boolean) => void
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
  const [backgroundWanted, setBackgroundWanted] = useState(false)
  const [backgroundProblem, setBackgroundProblem] =
    useState<BackgroundWatchProblem | null>(null)

  useEffect(() => {
    // A recording that survived a reload resumes without being asked - see
    // `resume`'s note. Nothing here starts one.
    void trace.resume().then(setStatus)
  }, [trace])

  // Above `onFix` rather than below it, because every sample now carries this:
  // a gap in the trace is only readable if the fixes either side of it say
  // whether the screen was being held. See lib/gpsTrace.ts's header.
  const wakeLock = useWakeLock(status.recording)

  /**
   * Everything both watches share: place the fix, report whether the trail
   * columns are filling, and stamp the conditions.
   *
   * One function because the two sources must not drift apart in anything
   * except the fields that genuinely differ. What they build the sample WITH
   * differs (`sampleFromPosition` vs `sampleFromNativeFix`, because the
   * accuracy radii mean different things); everything around it must not.
   */
  const placeAndStamp = useCallback(
    (at: { lon: number; lat: number }): [TraceReading | null, TraceConditions] => {
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
      return [
        reading,
        {
          wakeLock,
          // Read at the moment the fix lands, not from a listener: this is
          // the state that actually applied to THIS sample. On a native
          // background fix this is routinely false, which is the point.
          visible: typeof document === 'undefined' ? null : !document.hidden,
        },
      ]
    },
    [trailIndex, wakeLock],
  )

  const onFix = useCallback(
    (position: GeolocationPosition) => {
      // Not gated on `status.recording`: this closure is held in a ref by
      // useGeolocation and would be reading a stale flag. The recorder owns
      // that decision and drops the sample itself.
      const [reading, conditions] = placeAndStamp({
        lon: position.coords.longitude,
        lat: position.coords.latitude,
      })
      void trace.record(sampleFromPosition(position, reading, conditions)).then(setStatus)
    },
    [trace, placeAndStamp],
  )

  /**
   * The native watch, which is the whole point of #1182.
   *
   * Only while recording AND only when asked: a foreground service and its
   * undismissable notification are not something to start on the tester's
   * behalf. Torn down by the effect's cleanup, so stopping the recording
   * stops the service - the notification outliving the recording that asked
   * for it would be the most visible possible version of a leak.
   *
   * `placeAndStamp` is deliberately NOT a dependency. It changes whenever the
   * wake-lock state changes, and re-running this effect would remove and
   * re-add the platform watcher mid-walk - restarting GNSS acquisition and
   * flickering the notification, the same defect `useGeolocation`'s derived
   * `awake` flag exists to avoid. A ref holds the current one instead.
   */
  const placeRef = useRef(placeAndStamp)
  placeRef.current = placeAndStamp

  const backgroundOn = status.recording && backgroundWanted && backgroundWatchAvailable()

  useEffect(() => {
    if (!backgroundOn) return
    setBackgroundProblem(null)
    return startBackgroundWatch({
      onFix: (fix) => {
        const [reading, conditions] = placeRef.current({ lon: fix.lon, lat: fix.lat })
        void trace.record(sampleFromNativeFix(fix, reading, conditions)).then(setStatus)
      },
      onProblem: setBackgroundProblem,
    })
  }, [backgroundOn, trace])

  const onExport = useCallback(() => {
    void trace
      .readAll()
      .then((samples) =>
        downloadTrace(traceToCsv(samples), traceFilename(trace.status().startedAt)),
      )
  }, [trace])

  const background: BackgroundState = !backgroundWanted
    ? 'off'
    : !backgroundWatchAvailable()
      ? 'not-native'
      : backgroundProblem === 'not-authorized'
        ? 'not-authorized'
        : backgroundProblem !== null
          ? 'failed'
          : status.recording
            ? 'on'
            : 'off'

  return {
    status,
    trailFix,
    background,
    backgroundWanted,
    onBackgroundChange: setBackgroundWanted,
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
