// The switch that turns #106's walk into data (#1180).
//
// Its own file rather than more rows in Settings.tsx, for the reason
// AboutBuild.tsx gives: a screen everything is appended to becomes the file
// every branch collides in, and this section has state.
//
// WHO THIS IS FOR, AND WHY IT STILL READS PLAINLY.
//
// A tester, not a thru-hiker - it ships off and nothing offers it. That is a
// reason to keep it out of the way, not a licence for jargon: the person
// tapping it may be an NYNJTC or ATC volunteer (#106 asks for exactly that,
// "rather than only the maintainer"), standing in the rain, who has never
// read an issue in this repository. So no accuracy radii, no fix rates, no
// mention of what a chunk is. What it costs, what it holds, and where it
// goes.
//
// THE THREE BUTTONS ARE THE FEATURE.
//
// Not decoration on a recorder - they are the reason the trace is worth
// taking. #1100 needs a phone "stationary under canopy" told apart from one
// "walking from a standing start", and no amount of post-processing recovers
// that split, because a stationary phone under canopy and a slow walk look
// alike in exactly the data whose ambiguity is the finding. The hiker is the
// only instrument that knows.
//
// THE COPY SAYS BATTERY BEFORE IT SAYS ANYTHING ELSE, and it says what this
// CANNOT do before a tester finds out on the trail.
//
// The first version of this screen promised recording "including while the
// phone is in your pocket". That was false, and a real walk found it: a phone
// that locks suspends the page, `watchPosition` stops, and no application code
// changes that in a web app. `useGeolocation`'s `keepAwake` only stops THIS
// APP ending the recording; it cannot stop the platform. What a web app can do
// is hold the screen awake (lib/useWakeLock.ts) so the screen never sleeps on
// its own - and say plainly that locking the phone by hand still pauses it.
//
// That correction is the whole point rather than a caveat bolted on. A tester
// who believes the old sentence walks ninety minutes and comes back with
// twenty, which is exactly the "never let a display outrun its source" failure
// CLAUDE.md names, committed by the feature built to gather evidence.

import { useState } from 'react'
import type { TraceMarker, TraceStatus } from '../lib/gpsTrace'
import type { WakeLockState } from '../lib/useWakeLock'

export interface GpsTraceSettingsProps {
  status: TraceStatus
  onStart: () => void
  onStop: () => void
  onMark: (marker: TraceMarker) => void
  onExport: () => void
  onDelete: () => void
  /**
   * Whether the screen is actually being held awake (lib/useWakeLock.ts).
   *
   * Reported rather than assumed: a browser with no Screen Wake Lock API, or
   * one refusing it on low battery, leaves the screen sleeping - and a tester
   * needs that before the walk, not after.
   */
  wakeLock?: WakeLockState
  /** Injected so the elapsed reading can be asserted against a fixed clock -
   *  the real one would make every assertion about when the test ran. */
  now?: Date
}

/** What each marker is called by somebody who has not read #1100.
 *
 *  "Off the trail" rather than "off-trail excursion": the hiker is being
 *  asked what they are doing, and the answer should sound like something a
 *  person does. */
const MARKER_LABEL: Record<TraceMarker, string> = {
  stationary: 'Standing still',
  walking: 'Walking',
  'off-trail': 'Off the trail',
}

const MARKER_ORDER: readonly TraceMarker[] = ['stationary', 'walking', 'off-trail']

/**
 * Whole minutes, and never seconds.
 *
 * A counter ticking every second on a screen somebody has left open in a
 * pocket is a screen that never sleeps, and this is the one feature in the
 * app that already costs battery deliberately. Minutes also match what the
 * reading is for: #1100 asks for "several minutes" stationary, not several
 * hundred seconds.
 */
export function elapsedLabel(startedAt: number | null, now: Date): string {
  if (startedAt === null) return ''
  const minutes = Math.floor((now.getTime() - startedAt) / 60_000)
  if (minutes < 1) return 'just started'
  if (minutes === 1) return '1 minute'
  return `${minutes} minutes`
}

/** Grouped with a separator so a four-figure count stays readable at a
 *  glance on a phone held at arm's length. */
const countLabel = (samples: number): string =>
  `${samples.toLocaleString('en-US')} ${samples === 1 ? 'reading' : 'readings'}`

export function GpsTraceSettings({
  status,
  onStart,
  onStop,
  onMark,
  onExport,
  onDelete,
  wakeLock = 'off',
  now = new Date(),
}: GpsTraceSettingsProps) {
  // Two presses to delete, like AccountDataSettings' own destructive path.
  // There is no undo and the walk is not repeatable that day.
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const hasTrace = status.samples > 0

  return (
    <section className="settings__group">
      <h2 className="settings__heading">Record a GPS trace</h2>

      {status.recording ? (
        <>
          <p className="settings__row">
            <span className="settings__label">Recording</span>
            <span className="settings__value">
              {countLabel(status.samples)} · {elapsedLabel(status.startedAt, now)}
            </span>
          </p>

          {/* The question, asked in the second person, because the answer is
              something only the person holding the phone knows. */}
          <p className="settings__note">What are you doing right now?</p>
          <div className="settings__exports">
            {MARKER_ORDER.map((marker) => (
              <button
                key={marker}
                type="button"
                className="settings__action"
                aria-pressed={status.marker === marker}
                onClick={() => onMark(marker)}
              >
                {MARKER_LABEL[marker]}
              </button>
            ))}
          </div>
          <p className="settings__note">
            Tap one whenever it changes. Without it, a phone standing still under trees
            and a slow walk look the same in the recording, and that is the difference we
            are trying to measure.
          </p>

          {/* Said while it matters rather than in the idle blurb: a lock that
              was granted and then refused on a low battery changes what the
              tester should do with the phone, and only this state can say so. */}
          <p className="settings__note">
            {wakeLock === 'held'
              ? 'The screen is being kept awake, so the recording keeps running. Locking the phone yourself still pauses it until you unlock.'
              : 'This phone will not let the screen stay awake, so the recording pauses every time the screen goes dark. Keep the screen on, or set the screen timeout as long as it will go.'}
          </p>

          <button type="button" className="settings__action" onClick={onStop}>
            Stop recording
          </button>
        </>
      ) : (
        <>
          <button type="button" className="settings__action" onClick={onStart}>
            Start recording
          </button>
          <p className="settings__note">
            Writes down where your phone thinks you are, several times a minute, and keeps
            the screen from going dark on its own so it can. It will use a lot more
            battery than usual — the screen is most of that. Start it at the trailhead and
            stop it when you finish.
          </p>
          <p className="settings__note">
            If you lock the phone yourself, recording pauses until you unlock it. Nothing
            already recorded is lost, and it picks up again on its own.
          </p>
          <p className="settings__note">
            The recording stays on this phone. It is never uploaded, never attached to a
            problem report, and nobody else can see it unless you send them the file
            yourself.
          </p>
        </>
      )}

      {hasTrace && !status.recording && (
        <>
          <p className="settings__row">
            <span className="settings__label">Saved recording</span>
            <span className="settings__value">{countLabel(status.samples)}</span>
          </p>

          <button type="button" className="settings__action" onClick={onExport}>
            Save the recording to a file
          </button>

          {confirmingDelete ? (
            <>
              <p className="settings__note">
                This deletes the recording for good. If you have not saved it to a file
                yet, it is gone.
              </p>
              <button
                type="button"
                className="settings__action"
                onClick={() => {
                  onDelete()
                  setConfirmingDelete(false)
                }}
              >
                Yes, delete it
              </button>
              <button
                type="button"
                className="settings__action"
                onClick={() => setConfirmingDelete(false)}
              >
                Keep it
              </button>
            </>
          ) : (
            <button
              type="button"
              className="settings__action"
              onClick={() => setConfirmingDelete(true)}
            >
              Delete the recording
            </button>
          )}
        </>
      )}
    </section>
  )
}
