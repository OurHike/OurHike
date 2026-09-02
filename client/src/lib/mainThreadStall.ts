// How badly the main thread was jammed while a fix was being recorded (#1180).
//
// WHY THIS IS HERE. The sixth field walk came back with four hours elapsed and
// about a minute of it producing rows, and the tester's reading was "is it
// possible the app hung? it feels like the app is hanging a lot in general",
// then: "the app is both unresponsive to taps and unresponsive to switch
// tabs". Those two symptoms together are a main-thread report - React state
// and routing both run there, so a tap that does nothing AND a tab that does
// not change is the event loop being occupied, not a slow screen.
//
// The recorder was profiled against that claim and came back clean: at the
// measured field cadence (a watch fix every 5.7 s plus the 5 s poll) zero
// tasks crossed the 50 ms long-task threshold over ~40 s, and forcing 600
// fixes through as fast as the app would take them produced 2 long tasks,
// 138 ms of blocking in total, and a 36 ms tab switch afterwards, with the
// heap moving 9 -> 11 MB. That measurement was taken in a sandbox with NO MAP
// DATA, so `trailIndex` was null, `locateOnTrail` never ran, and MapLibre had
// nothing to draw - which is precisely the condition that makes the app cheap
// and is NOT the condition the tester's phone is in. So the profile exonerates
// the recorder and settles nothing about the phone.
//
// This is the part that can only be answered on the phone. It is the same
// argument as `wake_lock` and `page_visible`: a silence in the trace is
// evidence only if the rows either side say what the app knew about itself.
// Those two columns tell a dark screen from a pocketed phone. These two tell
// EITHER of those from a main thread that was awake, visible, and too busy to
// answer - which no column in the file can currently distinguish from a
// platform that simply had no fix to hand over.
//
// HOW TO READ THE NUMBER, because it is easy to read backwards. A blocked main
// thread cannot run the recorder's own callback, so the blocking is attributed
// to the fix AFTER the jam rather than to a fix during it. `blocked_ms` on a
// row means "in the interval ending here", never "while this was written".
//
// WHAT IT CANNOT SEE, and why an empty cell is not a zero:
//
//   - Safari and every browser on iOS. WebKit does not implement Long Tasks,
//     so `supported` is false there and both columns stay empty. Absent means
//     unknown, as everywhere else in this file's neighbourhood - an empty
//     `blocked_ms` must never be read as "nothing blocked".
//   - A page the OS suspended. Nothing runs, so nothing is observed, and the
//     gap shows up instead as missing rows with `page_visible` reading `no`
//     on the fix either side.
//   - A WebView the system killed outright, which produces no rows at all.
//
// Three silences with three signatures, which is the whole reason for adding
// columns rather than a verdict.
//
// THE THRESHOLD IS THE SPEC'S, NOT A CHOICE MADE HERE. W3C Long Tasks reports
// a task occupying the event loop for 50 ms or more; the browser decides what
// counts and this module only adds them up. So the numbers are comparable
// across traces and across devices without anybody agreeing on a threshold
// first, which is the opposite of every other constant in this branch.

/**
 * What the main thread did in one interval.
 *
 * Two numbers rather than one because they mean different things to a hiker:
 * 200 ms of blocking as one 200 ms task is a visible freeze, and as four
 * 50 ms tasks is a slightly sticky screen.
 */
export interface StallReading {
  /** Long-task milliseconds since the previous `take`. Null where the browser
   *  cannot measure it at all. */
  blockedMs: number | null
  /** The single longest task in that interval. Null likewise. */
  worstMs: number | null
}

export interface StallMeter {
  /** Whether this browser reports long tasks. False on all of iOS. */
  readonly supported: boolean
  start(): void
  stop(): void
  /** Drain and return what has accumulated since the last call. */
  take(): StallReading
  /** The longest single task since `start`, for the screen. Null if
   *  unsupported or if nothing has crossed the threshold yet. */
  worst(): number | null
}

const UNMEASURED: StallReading = { blockedMs: null, worstMs: null }

/** Whether `PerformanceObserver` will accept `longtask` here.
 *
 *  Feature-detected through `supportedEntryTypes` rather than by calling
 *  `observe` in a try/catch: Firefox throws on an unknown type and Chrome
 *  historically did not, so the catch would have had to distinguish "refused"
 *  from "accepted and silent". */
export function longTaskObservationSupported(): boolean {
  if (typeof PerformanceObserver === 'undefined') return false
  const types = PerformanceObserver.supportedEntryTypes
  return Array.isArray(types) && types.includes('longtask')
}

export function createStallMeter(): StallMeter {
  const supported = longTaskObservationSupported()
  let observer: PerformanceObserver | null = null
  let blockedMs = 0
  let worstInInterval = 0
  let worstOverall = 0
  let running = false

  return {
    supported,

    start() {
      if (!supported || running) return
      blockedMs = 0
      worstInInterval = 0
      worstOverall = 0
      observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          blockedMs += entry.duration
          worstInInterval = Math.max(worstInInterval, entry.duration)
          worstOverall = Math.max(worstOverall, entry.duration)
        }
      })
      // `buffered: false` (the default) deliberately. Buffered entries would
      // hand the first sample of a recording every long task since the page
      // loaded - including the map build, which is a real stall and is not
      // one that happened in that five-second interval. The column claims to
      // be an interval measurement and has to be one.
      observer.observe({ type: 'longtask' })
      running = true
    },

    stop() {
      observer?.disconnect()
      observer = null
      running = false
    },

    take() {
      if (!supported) return UNMEASURED
      const reading = {
        // Rounded because a fractional millisecond of blocking is noise
        // dressed as precision, and the CSV is read by humans first.
        blockedMs: Math.round(blockedMs),
        worstMs: Math.round(worstInInterval),
      }
      blockedMs = 0
      worstInInterval = 0
      return reading
    },

    worst() {
      if (!supported) return null
      return worstOverall === 0 ? null : Math.round(worstOverall)
    },
  }
}
