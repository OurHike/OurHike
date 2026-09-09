// What a launch actually costs, on the phone it happened on (#1299).
//
// THE GAP THIS CLOSES. The maintainer reported "about six seconds" to a usable
// screen on 2026-09-09. The stopwatch (client/scripts/measure-first-run.mjs)
// reported 1,152-1,572 ms to first content on its throttled profile the same
// day. Neither number can see the other: the profile is a desktop core at a
// quarter speed with no browser process start, no phone storage and no thermal
// state in it, and the phone had nothing that said where its six seconds went.
// features/LAUNCH_BUDGET.md §1 and §6 record that as the plan's first unknown.
//
// So the app marks the moments its own budget is written against, and three
// places read the same marks: Settings -> About this build, the bug-report
// prefill, and the stopwatch. A number from a phone and a number from the
// profile then name the same events.
//
// WHY `performance.mark` AND NOT A CLOCK OF OUR OWN. The marks are timed
// against `performance.timeOrigin` - the navigation itself - which is the one
// clock that includes the parts this app does not run: the document request,
// the module script's own download and parse. A `Date.now()` taken in
// `main.tsx` starts counting after all of that, which is the half a hiker
// waits through and the half a laptop never sees.
//
// THIS IS NOT TELEMETRY. Nothing here leaves the phone on its own. The marks
// live in the page for as long as the page does; the bug-report prefill puts
// them in a URL the hiker is looking at, and only if they open that form -
// the same footing lib/bugReport.ts already puts the build on, and the same
// line it draws: the build and its timings are facts about OUR software, the
// device is a fact about them (features/IDENTITY_AND_PRIVACY.md,
// TECHNICAL_ARCHITECTURE.md's "Nothing is recorded").

/**
 * The moments the budget in features/LAUNCH_BUDGET.md §3 is written against.
 *
 * The names are the contract the stopwatch reads back, so they are values
 * rather than string literals scattered across the shell.
 */
export const LAUNCH_MARKS = {
  /** `main.tsx` began evaluating - the app's own code is on the thread. */
  script: 'ourhike:script',
  /** The shell committed a frame with the tab bar in it: the first thing a
   *  hiker can see and tap. */
  shell: 'ourhike:shell',
  /** The phone's own preferences came back from IndexedDB. */
  preferences: 'ourhike:preferences',
  /** Today has the release's waypoints - its journal can rank something. */
  today: 'ourhike:today',
  /** The centerline index landed, so a fix can be placed on the trail. */
  index: 'ourhike:index',
} as const

export type LaunchMarkName = (typeof LAUNCH_MARKS)[keyof typeof LAUNCH_MARKS]

/** Every mark, in the order a launch reaches them - which is the order they
 *  are shown in and the order the stopwatch prints. */
export const LAUNCH_MARK_ORDER: readonly LaunchMarkName[] = [
  LAUNCH_MARKS.script,
  LAUNCH_MARKS.shell,
  LAUNCH_MARKS.preferences,
  LAUNCH_MARKS.today,
  LAUNCH_MARKS.index,
]

/** What each mark is called on screen. Short enough for a settings row. */
export const LAUNCH_MARK_LABELS: Record<LaunchMarkName, string> = {
  [LAUNCH_MARKS.script]: 'App code started',
  [LAUNCH_MARKS.shell]: 'Tab bar on screen',
  [LAUNCH_MARKS.preferences]: 'Your settings read',
  [LAUNCH_MARKS.today]: 'Waypoints ready',
  [LAUNCH_MARKS.index]: 'Trail index ready',
}

/**
 * Records a moment, the FIRST time it happens.
 *
 * First rather than latest, because every one of these is a "when did the
 * launch reach this" question and a later re-render reaching the same line
 * again would answer a different one. Never throws: a browser with no
 * `performance.mark` (or one that has run out of buffer) costs the readout,
 * not the app.
 */
export function markLaunch(name: LaunchMarkName): void {
  try {
    if (typeof performance === 'undefined' || typeof performance.mark !== 'function') {
      return
    }
    if (performance.getEntriesByName(name, 'mark').length > 0) return
    performance.mark(name)
  } catch {
    // A readout is not worth a throw on the launch path.
  }
}

export interface LaunchMoment {
  name: string
  label: string
  /** Milliseconds since the navigation began, or null where the launch has
   *  not reached this moment - which is a real answer, not a zero. */
  at: number | null
}

/**
 * The launch so far.
 *
 * A moment the launch has not reached reads `null`, never 0 and never a
 * guess: "the waypoints are not ready yet" and "the waypoints were ready
 * immediately" are different answers, and a readout that confused them would
 * be the display outrunning its source.
 */
export function launchTimeline(): LaunchMoment[] {
  const moments: LaunchMoment[] = []
  for (const name of LAUNCH_MARK_ORDER) {
    moments.push({ name, label: LAUNCH_MARK_LABELS[name], at: markedAt(name) })
  }
  const paint = paintAt('first-contentful-paint')
  if (paint !== null) {
    moments.splice(1, 0, {
      name: 'first-contentful-paint',
      label: 'First pixels',
      at: paint,
    })
  }
  return moments
}

function markedAt(name: string): number | null {
  try {
    if (typeof performance === 'undefined') return null
    const entries = performance.getEntriesByName(name, 'mark')
    return entries.length === 0 ? null : Math.round(entries[0].startTime)
  } catch {
    return null
  }
}

function paintAt(name: string): number | null {
  try {
    if (typeof performance === 'undefined') return null
    const entry = performance
      .getEntriesByType('paint')
      .find((candidate) => candidate.name === name)
    return entry === undefined ? null : Math.round(entry.startTime)
  } catch {
    return null
  }
}

/**
 * The timeline as one line, for the bug-report prefill and the copy button.
 *
 * Written so it survives being pasted into an issue body by somebody who
 * cannot see this screen: every moment named, milliseconds since the
 * navigation, and the ones the launch never reached said out loud rather than
 * omitted - an omitted row reads as "fast" to whoever is reading.
 */
export function launchSummary(timeline: LaunchMoment[] = launchTimeline()): string {
  const reached = timeline.filter((moment) => moment.at !== null)
  if (reached.length === 0) return 'Launch timings: not recorded on this browser'
  return `Launch timings (ms from navigation): ${timeline
    .map((moment) => `${moment.label} ${moment.at === null ? 'not reached' : moment.at}`)
    .join(', ')}`
}
