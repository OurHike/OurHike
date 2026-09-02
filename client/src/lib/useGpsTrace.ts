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
import { createStallMeter } from './mainThreadStall'
import { locateOnTrail, type TrailIndex } from './trailPosition'
import { useWakeLock, type WakeLockState } from './useWakeLock'

/**
 * How often to ask, and how long to wait.
 *
 * 5 s because that is the only cadence anybody has measured - `watchPosition`
 * delivered a 5.71 s median over the third walk's 135 intervals - so a polled
 * stationary trace comes out directly comparable to a walked one rather than
 * on some new footing nothing else shares.
 *
 * The timeout is four intervals rather than one. A poll that has not answered
 * inside 5 s has not necessarily failed, and cancelling it early would throw
 * away exactly the slow fix a stationary phone is most likely to produce.
 * `inFlight` stops them stacking up in the meantime.
 */
const POLL_INTERVAL_MS = 5_000
const POLL_TIMEOUT_MS = 20_000

const IDLE: TraceStatus = {
  recording: false,
  startedAt: null,
  marker: null,
  samples: 0,
  lastSampleAt: null,
  lastAccuracyM: null,
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
  /** How often the recorder asked the platform for a fix, and how often it
   *  got one. A large gap is the finding, not a bug to hide. */
  polls: { asked: number; answered: number }
  /**
   * The worst the main thread has been jammed during this recording.
   *
   * Reported for the same reason `wakeLock` and `trailFix` are: it is a thing
   * about this recording the tester can see the consequences of - taps that
   * do nothing - and cannot otherwise tell from a phone that is simply not
   * producing fixes. `supported` is false on iOS, where the browser does not
   * measure it, and the screen must say so rather than print a reassuring
   * zero.
   */
  stall: { supported: boolean; worstMs: number | null }
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
  /**
   * How many times the poll asked, and how many times it was answered.
   *
   * REPORTED BECAUSE THE FIFTH TRACE'S POLL PRODUCED NOTHING AT ALL, and the
   * trace could not say whether it had run. A poll that times out records no
   * row, so "the poll is not working" and "the poll never ran" looked
   * identical in the file - the exact ambiguity `wake_lock` and `page_visible`
   * were added to end for the watch, reintroduced one commit later by the
   * mechanism meant to help. Two counters, on the screen, while the tester is
   * still standing there.
   */
  const [polls, setPolls] = useState({ asked: 0, answered: 0 })
  const [backgroundProblem, setBackgroundProblem] =
    useState<BackgroundWatchProblem | null>(null)
  /**
   * WHETHER THE APP ITSELF WAS THE THING NOT ANSWERING.
   *
   * The sixth walk produced 4h12m elapsed and about a minute of rows, and the
   * tester read that as a hang: "unresponsive to taps and unresponsive to
   * switch tabs". Every column in the trace was blind to it. `wake_lock` and
   * `page_visible` separate a dark screen from a pocketed phone; nothing
   * separated either from a main thread too busy to run the callback that
   * writes a row. See lib/mainThreadStall.ts for what this can and cannot
   * see - notably that iOS does not measure it at all, so an empty column is
   * "not measured" and never "nothing blocked".
   */
  const stallMeter = useMemo(() => createStallMeter(), [])
  const [worstStallMs, setWorstStallMs] = useState<number | null>(null)

  useEffect(() => {
    // A recording that survived a reload resumes without being asked - see
    // `resume`'s note. Nothing here starts one.
    void trace.resume().then(setStatus)
  }, [trace])

  // Started and stopped with the recording rather than left running: this is
  // a diagnostic, and an app that observes its own long tasks all the time is
  // a behaviour change outside the mode somebody deliberately turned on. The
  // cost is that a hang OUTSIDE a recording is not measured - which is worth
  // saying out loud, because the tester's report was that the app "hangs a
  // lot in general".
  useEffect(() => {
    if (!status.recording) return
    stallMeter.start()
    return () => stallMeter.stop()
  }, [status.recording, stallMeter])

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
      // Drained here, once per fix, so the number on a row is the interval
      // ending at that row. Two callbacks carrying the SAME platform
      // timestamp (the sixth walk's duplicate, `getCurrentPosition` answering
      // the poll and the watch with one position) drain in order, and the
      // first one is both the one that gets the real number and the one
      // `record` keeps - so the surviving row is the truthful one either way.
      const stall = stallMeter.take()
      setWorstStallMs(stallMeter.worst())
      return [
        reading,
        {
          wakeLock,
          stall,
          // Read at the moment the fix lands, not from a listener: this is
          // the state that actually applied to THIS sample. On a native
          // background fix this is routinely false, which is the point.
          visible: typeof document === 'undefined' ? null : !document.hidden,
        },
      ]
    },
    [trailIndex, wakeLock, stallMeter],
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
   * ASKING FOR FIXES, BECAUSE STANDING STILL THE PLATFORM VOLUNTEERS SO FEW.
   *
   * The W3C Geolocation API has NO rate control. `watchPosition` takes exactly
   * three options - `enableHighAccuracy`, `timeout`, `maximumAge` - and not one
   * of them asks for a frequency. The platform fires when it decides a new
   * position exists, and the fourth field trace measured what that means: 7.58
   * fixes a minute while walking, **0.87 while standing still**, with
   * `wake_lock` reading `held` and `page_visible` reading `yes` on every row.
   * Nothing was broken. There was simply nothing to hand over.
   *
   * That is a problem for the one measurement this instrument exists to take.
   * #1100 wants a phone "stationary under canopy for several minutes", and 34
   * samples in 39 minutes is a thin basis for anything.
   *
   * So this asks. `getCurrentPosition` with `maximumAge: 0` refuses a cached
   * answer, which is the only way to get an INDEPENDENT sample rather than the
   * same fix counted twice - and counting one twice would shrink the apparent
   * scatter, making the phone look better than it is.
   *
   * @unvalidated, AND IT MAY SIMPLY NOT WORK. There is no GPS in the sandbox
   * this was written in, so whether a stationary Android actually produces a
   * fresh fix on demand is unknown. Two ways it could fail: the platform may
   * make `getCurrentPosition` wait for the same update the watch is waiting
   * for, and time out; or it may answer instantly with the fix the watch
   * already delivered, which the identical `timestamp_ms` would expose.
   *
   * THE TRACE ANSWERS IT EITHER WAY, which is why this is safe to try: polled
   * samples are stamped `web-poll` and watch samples stay `web`, so one walk
   * says whether the poll produced anything the watch did not. Merging them
   * into one column would have deleted that answer while looking like better
   * data.
   */
  useEffect(() => {
    if (!status.recording) return
    if (typeof navigator === 'undefined' || !('geolocation' in navigator)) return

    // One request at a time. A poll that is waiting out its timeout must not
    // have three more stacked behind it, each holding the chipset awake.
    let inFlight = false
    let stopped = false

    const id = setInterval(() => {
      if (inFlight || stopped) return
      inFlight = true
      setPolls((count) => ({ ...count, asked: count.asked + 1 }))
      navigator.geolocation.getCurrentPosition(
        (position) => {
          inFlight = false
          if (stopped) return
          setPolls((count) => ({ ...count, answered: count.answered + 1 }))
          const [reading, conditions] = placeRef.current({
            lon: position.coords.longitude,
            lat: position.coords.latitude,
          })
          void trace
            .record(
              sampleFromPosition(position, reading, {
                ...conditions,
                source: 'web-poll',
              }),
            )
            .then(setStatus)
        },
        // A refused or timed-out poll is not an error worth surfacing: the
        // watch is still running and the screen already reports what it is
        // doing. Silence here shows up in the trace as an absence of
        // `web-poll` rows, which is the finding.
        () => {
          inFlight = false
        },
        { enableHighAccuracy: true, maximumAge: 0, timeout: POLL_TIMEOUT_MS },
      )
    }, POLL_INTERVAL_MS)

    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [status.recording, trace])

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
    polls,
    stall: { supported: stallMeter.supported, worstMs: worstStallMs },
    onBackgroundChange: setBackgroundWanted,
    // Tied to recording rather than offered as its own switch: holding a
    // screen awake for anything else in this app would be a battery cost
    // nobody asked for.
    wakeLock,
    onFix,
    onStart: useCallback(() => {
      setPolls({ asked: 0, answered: 0 })
      setWorstStallMs(null)
      void trace.start().then(setStatus)
    }, [trace]),
    onStop: useCallback(() => void trace.stop().then(setStatus), [trace]),
    onMark: useCallback(
      (marker: TraceMarker) => void trace.mark(marker).then(setStatus),
      [trace],
    ),
    onExport,
    onDelete: useCallback(() => void trace.clear().then(setStatus), [trace]),
  }
}
