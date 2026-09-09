// "Which long hike?" - the door tapping Long hike opens when no hike is
// picked yet (#1317).
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
  onPick,
  onNew,
  onClose,
}: HikePickSheetProps) {
  return (
    <div className="plan-kind" role="dialog" aria-label="Which long hike?">
      <div className="legend__head">
        <h2 className="legend__title">Which long hike?</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {/* The last sentence is the exception being stated on screen rather
          than only in this file - a mode that silently reverts is a mode a
          hiker stops trusting. */}
      <p className="plan-kind__lede">
        A long hike follows one trail and holds every trip you walk on it. Close this and
        you&rsquo;re back on Day hike.
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
          <span className="plan-kind__door-name">{hike.name}</span>
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
