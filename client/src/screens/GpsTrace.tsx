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
// THE COPY SAYS BATTERY BEFORE IT SAYS ANYTHING ELSE. Recording holds the
// GPS on through a pocket (useGeolocation's `keepAwake`), which is the whole
// point and is also somebody's phone on a mountain. Burying that under a
// paragraph about CSV would be the "quiet inaccuracy" map/credits.ts objects
// to, applied to somebody's way home.

import { useState } from 'react'
import type { TraceMarker, TraceStatus } from '../lib/gpsTrace'

export interface GpsTraceSettingsProps {
  status: TraceStatus
  onStart: () => void
  onStop: () => void
  onMark: (marker: TraceMarker) => void
  onExport: () => void
  onDelete: () => void
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
            Keeps your GPS on — including while the phone is in your pocket — and writes
            down where it thinks you are, several times a minute. It will use noticeably
            more battery than usual. Start it at the trailhead and stop it when you
            finish.
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
