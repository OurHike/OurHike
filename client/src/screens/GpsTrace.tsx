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
import type { BackgroundState, TrailFix } from '../lib/useGpsTrace'
import type { GeolocationState } from '../lib/useGeolocation'
import { feetFromMetres, formatShortDistance, type UnitSystem } from '../lib/units'

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
  /**
   * What the watch is actually doing (lib/useGeolocation.ts).
   *
   * Reported from a real walk: a recording ran and stored zero points, and
   * this screen said "Recording · 0 readings" and nothing else. The hook has
   * modelled `denied`, `unsupported` and `unavailable` from the beginning and
   * the header has printed them since #312 - this section simply never looked,
   * so the one screen whose entire job is collecting fixes was the one screen
   * that could not say why it had none.
   */
  gpsStatus?: GeolocationState['status']
  /**
   * Whether the trail columns are being filled (lib/useGpsTrace.ts).
   *
   * Reported from the first real trace: `mile`, `off_trail_ft` and
   * `off_tread_ft` came back empty on all 136 rows, and nothing on this screen
   * had said so. Those three columns are the entire reason #93 wants a trace -
   * drift measured against the trail rather than against a reconstruction of
   * it - so a walk that collects the other ten columns has collected the easy
   * half. Both reasons for the blank are the tester's to fix and only while
   * they are still outside, which is why this is here and not in the export.
   */
  trailFix?: TrailFix
  /** Whether fixes survive a dark screen, and if not why (#1182). */
  background?: BackgroundState
  /** How often the recorder asked for a fix, and how often it was answered
   *  (lib/useGpsTrace.ts). A large gap between them IS the finding. */
  polls?: { asked: number; answered: number }
  /** The hiker's chosen system, because the accuracy radius is a distance
   *  somebody reads — src/test/unitDisplay.test.ts holds this standard, and
   *  caught the first version of this row writing "m" into a string. */
  units?: UnitSystem
  /** Whether the tester has asked for it. Separate from `background` because
   *  a switch that is on and not working must still read as on. */
  backgroundWanted?: boolean
  onBackgroundChange?: (wanted: boolean) => void
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

/**
 * How long since the last reading, once that is long enough to be worth saying.
 *
 * THE REASON THIS EXISTS: on the third field walk the fixes stopped dead and
 * the tester stood still for several more minutes beside a recording that had
 * already ended. The count was on screen the whole time, and a count that has
 * stopped climbing looks identical to one climbing slowly unless you were
 * watching the digits.
 *
 * 180 s, RAISED FROM 60 s BY THE FOURTH FIELD TRACE, which is the measurement
 * this number should have waited for. That trace is 39 minutes of a phone
 * standing still with `wake_lock` reading `held` and `page_visible` reading
 * `yes` on every one of its 34 rows - so the screen was awake, the page was
 * running, and the platform simply delivered fewer fixes to a device that was
 * not moving. Its intervals: 5.6, 11.3, 17.0, 25.0, 28.2, 49.5, 59.7, 63.0,
 * 68.7, 93.8, 98.7, 150.2 seconds. SIX of them exceed 60 s, and five of those
 * six were a healthy recording doing exactly what it was asked to do.
 *
 * A warning that fires five times wrongly during the one activity this
 * instrument exists to measure is the cry-wolf failure `wrongWay.test.ts`
 * states outright - "false positives are the failure this whole module exists
 * to prevent" - committed on the screen a tester reads to decide whether their
 * afternoon is working.
 *
 * 180 s clears the largest healthy gap seen (150.2 s) with room, and still
 * catches the failure it was built for: the third walk's silence ran 272 s.
 * @unvalidated as a threshold - two recordings on one phone is not a
 * distribution, and the honest floor is "larger than the biggest ordinary gap
 * anybody has measured", which is what this is. More stationary traces move
 * it; a device that thins further under canopy would move it up.
 */
export const STALL_SECONDS = 180

export function stalledLabel(
  lastSampleAt: number | null,
  now: Date,
  recording: boolean,
): string | null {
  if (!recording || lastSampleAt === null) return null
  const seconds = Math.floor((now.getTime() - lastSampleAt) / 1000)
  if (seconds < STALL_SECONDS) return null
  const minutes = Math.floor(seconds / 60)
  // States the fact and offers both readings of it, rather than diagnosing.
  // The old sentence said "the screen probably went dark", which the fourth
  // trace showed is frequently WRONG: fixes thin out on a stationary phone
  // with the screen fully awake. Telling a standing tester their screen died
  // sends them to fix something that is not broken.
  return `No reading for ${minutes} minutes. If you are standing still that can be normal — the phone sends fewer readings when it is not moving. If you are walking, the screen has probably gone dark; wake the phone and it picks up on its own. Nothing already recorded is lost.`
}

/** Grouped with a separator so a four-figure count stays readable at a
 *  glance on a phone held at arm's length. */
const countLabel = (samples: number): string =>
  `${samples.toLocaleString('en-US')} ${samples === 1 ? 'reading' : 'readings'}`

/**
 * Why a recording has nothing in it, when it has nothing in it.
 *
 * Null once fixes are arriving - a count that is climbing says the same thing
 * better, and a caveat on every screen reads exactly like a caveat on none.
 * Every other branch names something the tester can act on, because a walk
 * that comes back empty has already cost the afternoon.
 */
/** The status-row value, in the fewest words that still distinguish the two
 *  failures - "not recorded" alone is the empty column all over again. */
const TRAIL_FIX_VALUE: Record<TrailFix, string> = {
  waiting: 'waiting for a fix',
  recorded: 'recording',
  'no-trail-data': 'trail not downloaded',
  'off-corridor': 'not near the trail',
}

/**
 * What to do about it, when there is something to do about it.
 *
 * Null while it is working, like `recordingTrouble` - the status row above
 * already says "recording" and a second line agreeing with it is the caveat
 * on every screen that CLAUDE.md warns reads like a caveat on none.
 *
 * Neither failing case is an error. Walking a mile from the house to shake the
 * recorder out is a completely reasonable thing to do with this, and it still
 * produces every accuracy reading the change to the readout needs. What it
 * does not produce is drift against the trail, and a tester who thinks they
 * are collecting that has spent the afternoon on the easy half.
 */
export function trailFixNote(trailFix: TrailFix): string | null {
  if (trailFix === 'no-trail-data') {
    return 'Where you are on the trail is not being recorded, because this phone has not downloaded the trail yet. Everything else is. Download it from the map, then start a new recording.'
  }
  if (trailFix === 'off-corridor') {
    return 'Where you are on the trail is not being recorded, because you are more than three miles from the Appalachian Trail. Everything else is — this is still a useful recording, just not one that can measure drift against the trail.'
  }
  return null
}

/**
 * What the background switch is actually doing (#1182).
 *
 * Null while it is off and while it is working - the switch itself says the
 * first and the reading count says the second, and a caveat on every state
 * reads like a caveat on none.
 *
 * `not-native` is deliberately not phrased as a failure. It is the ordinary
 * answer in a browser, which is where every field test so far has happened,
 * and telling a tester the app is broken when they are simply on the preview
 * link is how a tester stops reading this screen.
 */
export function backgroundNote(background: BackgroundState): string | null {
  if (background === 'not-native') {
    return 'This only works in the installed app, not in a web browser. The recording still runs while the screen is on.'
  }
  if (background === 'not-authorized') {
    return 'Android needs location set to "Allow all the time" for this, and that can only be changed in the phone\u2019s own settings — the app cannot ask for it. The recording still runs while the screen is on.'
  }
  if (background === 'failed') {
    return 'Recording with the screen off did not start, and the phone did not say why. The recording still runs while the screen is on.'
  }
  return null
}

export function recordingTrouble(
  gpsStatus: GeolocationState['status'],
  samples: number,
): string | null {
  if (gpsStatus === 'denied') {
    return 'Your browser is blocking location for this site, so nothing is being recorded. Allow it in the site settings, then start again.'
  }
  if (gpsStatus === 'unsupported') {
    return 'This browser cannot do GPS at all, so nothing can be recorded here.'
  }
  if (gpsStatus === 'unavailable') {
    return 'No GPS signal right now, so nothing is being added. That is normal indoors and under heavy tree cover — it picks up again on its own.'
  }
  if (samples === 0) {
    return 'Waiting for the first reading. If this does not move within a minute or two, step into the open — nothing is being recorded until it does.'
  }
  return null
}

export function GpsTraceSettings({
  status,
  onStart,
  onStop,
  onMark,
  onExport,
  onDelete,
  wakeLock = 'off',
  gpsStatus = 'located',
  trailFix = 'waiting',
  background = 'off',
  polls,
  units = 'imperial',
  backgroundWanted = false,
  onBackgroundChange,
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

          {/* A row rather than another note: this is the same kind of fact as
              the count above it, and the note pile below is already three
              deep. */}
          <p className="settings__row">
            <span className="settings__label">Trail position</span>
            <span className="settings__value">{TRAIL_FIX_VALUE[trailFix]}</span>
          </p>
          {/* WHAT THE LAST FIX ACTUALLY CLAIMED. The fifth field trace's one
              reading stated exactly 100 m with no speed and no heading - a
              network fix, not GNSS - and nothing on this screen said so, so a
              tester stood for 74 minutes waiting for a satellite lock that
              had never happened. A number, not a judgement: no threshold is
              being asserted here, because none has been validated. */}
          {status.lastAccuracyM !== null && (
            <p className="settings__row">
              <span className="settings__label">Last reading</span>
              <span className="settings__value">
                give or take{' '}
                {formatShortDistance(feetFromMetres(status.lastAccuracyM), units)}
              </span>
            </p>
          )}

          {/* Asked vs answered. A poll that times out writes no row, so
              without this "the poll is not working" and "the poll never ran"
              look identical in the exported file. */}
          {polls !== undefined && polls.asked > 0 && (
            <p className="settings__row">
              <span className="settings__label">Readings asked for</span>
              <span className="settings__value">
                {polls.answered.toLocaleString('en-US')} of{' '}
                {polls.asked.toLocaleString('en-US')} answered
              </span>
            </p>
          )}

          {backgroundWanted && (
            <p className="settings__row">
              <span className="settings__label">Screen off</span>
              <span className="settings__value">
                {background === 'on' ? 'still recording' : 'recording pauses'}
              </span>
            </p>
          )}
          {backgroundWanted && backgroundNote(background) !== null && (
            <p className="settings__note settings__note--trouble">
              {backgroundNote(background)}
            </p>
          )}
          {trailFixNote(trailFix) !== null && (
            <p className="settings__note">{trailFixNote(trailFix)}</p>
          )}

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

          {/* The reason there is nothing to show, when there is nothing to
              show. First among the notes because a tester reading "0 readings"
              needs this before anything about battery. */}
          {/* Before the GPS trouble note: a stalled recording is a stronger
              claim than "no signal right now", and on the third walk it was
              the true one. */}
          {stalledLabel(status.lastSampleAt, now, status.recording) !== null && (
            <p className="settings__note settings__note--trouble">
              {stalledLabel(status.lastSampleAt, now, status.recording)}
            </p>
          )}

          {recordingTrouble(gpsStatus, status.samples) !== null && (
            <p className="settings__note settings__note--trouble">
              {recordingTrouble(gpsStatus, status.samples)}
            </p>
          )}

          {/* Said while it matters rather than in the idle blurb: a lock that
              was granted and then refused on a low battery changes what the
              tester should do with the phone, and only this state can say so. */}
          <p className="settings__note">
            {wakeLock === 'held'
              ? 'The screen is being kept awake, so the recording keeps running. Locking the phone yourself still pauses it until you unlock.'
              : 'The screen is not being kept awake, so the recording pauses every time it goes dark — including while you stand still without touching it. Set the screen timeout as long as it will go, and tap the screen now and then.'}
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

          {/* Offered before the walk rather than during it, because it is a
              decision about the walk: turning it on mid-recording would leave
              the first half of the trace measuring one watch and the second
              half the other. The CSV says which either way. */}
          {onBackgroundChange !== undefined && (
            <>
              <label className="settings__row">
                <span className="settings__label">
                  Keep recording with the screen off
                </span>
                <input
                  type="checkbox"
                  checked={backgroundWanted}
                  onChange={(event) => onBackgroundChange(event.target.checked)}
                />
              </label>
              <p className="settings__note">
                Uses far less battery than keeping the screen on, and the phone shows a
                notice the whole time it is running. The readings it takes are measured
                slightly differently from the ones the browser takes — the saved file
                records which is which, so nothing gets mixed up.
              </p>
              {backgroundNote(background) !== null && (
                <p className="settings__note">{backgroundNote(background)}</p>
              )}
            </>
          )}
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
