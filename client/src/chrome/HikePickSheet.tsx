// "Which long hike?" - the door tapping Long hike opens when no hike is
// picked yet (#1317), and since #1329 the SWITCH as well: the Plan band's
// `The hike >` opens this same sheet where one is already active.
//
// ONE SHEET FOR BOTH, because they are one question asked at two moments -
// which of these hikes am I on - and a second list of the same hikes with
// the same figures would be the "one home per item" rule broken in the
// place it is easiest to break it. What varies is the title, the last
// sentence of the lede (closing means two different things: see
// `handleCancelHikePick`), and a mark on the hike you are already on.
//
// PlanKindSheet's anatomy, deliberately: this is the same kind of question
// asked in the same place, and a second door design would make two identical
// choices look like two different ones. The classes are that sheet's; only
// the doors differ.
//
// CANCELLING PUTS THE MODE BACK, and it is the one place in the app where
// tapping a mode segment is not instantaneous. The handoff records it as a
// deliberate exception rather than an oversight: Long hike means "the hike
// I'm on", and there is no such thing to mean until one is picked, so the
// alternative is a long-hike state with nothing in it - every screen that
// varies by the mode varying to an empty answer.
//
// The switch shows Long selected at reduced opacity while this is open
// (chrome/modeSwitch.css's `--pending`), so the revert is not a surprise
// arriving after the fact.

import { hikePickMeta } from '../lib/hikeText'
import type { Hike } from '../lib/hikes'
import { isUsableHike } from '../lib/hikes'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'
import type { UnitSystem } from '../lib/units'
import '../screens/plan.css'

export interface HikePickSheetProps {
  hikes: readonly Hike[]
  trips: readonly Trip[]
  pois: readonly StoredPoi[]
  units: UnitSystem
  /** The phone's local calendar day, for "11 months ago". */
  today: string
  /** The hike the app is already on, or null. Its presence is what turns
   *  this from a first pick into a switch - see the header. */
  activeHikeId?: string | null
  onPick: (hikeId: string) => void
  onNew: () => void
  /** Close without picking - which reverts the mode. See the header. */
  onClose: () => void
}

export function HikePickSheet({
  hikes,
  trips,
  pois,
  units,
  today,
  activeHikeId = null,
  onPick,
  onNew,
  onClose,
}: HikePickSheetProps) {
  // The dialog's accessible name and its heading are one string, so a screen
  // reader announcing the sheet and a hiker reading it are told the same
  // thing. They were two before this was a switch, and the label would have
  // gone on saying "Which long hike?" over a heading asking which one you
  // are on.
  const title = activeHikeId === null ? 'Which long hike?' : 'Which hike are you on?'

  return (
    <div className="plan-kind" role="dialog" aria-label={title}>
      <div className="legend__head">
        <h2 className="legend__title">{title}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {/* TWO LEDES BECAUSE THERE ARE TWO TRUTHS (#1329). The first sentence
          is the same either way; the last one describes what closing does,
          and closing does two different things. Saying "you're back on Day
          hike" to a hiker who has a hike would be false - `handleCancelHikePick`
          only reverts the mode where there is nothing to go back to - and a
          mode that reverts when the screen said it would not is a mode a
          hiker stops trusting, which is the failure this sentence exists on
          screen to prevent. */}
      <p className="plan-kind__lede">
        A long hike follows one trail and holds every trip you walk on it.{' '}
        {activeHikeId === null
          ? "Close this and you're back on Day hike."
          : 'Switching keeps both — the one you leave stays exactly as it is.'}
      </p>

      {hikes.map((hike) => (
        <button
          type="button"
          className={
            isUsableHike(hike)
              ? 'plan-kind__door'
              : 'plan-kind__door plan-kind__door--unavailable'
          }
          key={hike.id}
          // A hike with fewer than two points cannot be walked and is still
          // the hiker's - LineSheet's rule: a door that cannot open is a
          // sentence, never a control that looks pressable and is not.
          disabled={!isUsableHike(hike)}
          onClick={() => onPick(hike.id)}
        >
          <span className="plan-kind__door-name">
            {hike.name}
            {hike.id === activeHikeId && (
              // The one you are on, marked rather than hidden or moved to
              // the top. A switch whose list re-orders itself under the
              // finger is a switch that picks the wrong hike.
              <span className="plan-kind__door-here"> · you&rsquo;re on this one</span>
            )}
          </span>
          <span className="plan-kind__door-note">
            {isUsableHike(hike)
              ? hikePickMeta(hike, trips, pois, units, today)
              : 'Needs two ends before it can be walked.'}
          </span>
        </button>
      ))}

      <button type="button" className="plan-kind__door" onClick={onNew}>
        <span className="plan-kind__door-name">A new long hike</span>
        <span className="plan-kind__door-note">
          Two ends on one trail. Days and dates can wait.
        </span>
      </button>
    </div>
  )
}
