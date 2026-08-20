// The two controls that make an estimate the hiker's own (#880).
//
// features/PERSONALIZED_PACE.md §1: "a hiker who has been walking for thirty
// years should not have to wait a week for the app to discover what they
// already know."
//
// NOT WIRED THROUGH `onChange(patch: Partial<UserPreferences>)`
//
// Every other section in Settings.tsx writes through that one callback. This
// one does not, and the reason is not stylistic: a pace profile is deliberately
// NOT part of `UserPreferences`. That blob is a whole-blob sync target, and
// PERSONALIZED_PACE.md §4 keeps a pace profile off the wire even once an
// account exists. Settings.tsx already has the precedent - the background is
// "written through its own callback rather than `onChange`" - and this follows
// it for a stronger reason.
//
// THE PREVIEW IS THE CONTROL
//
// Nobody has a feel for "an hour per 480 metres". Both sliders are unintuitive
// in isolation and immediately legible through the only number that matters:
// what a real walk now reads. It is the SAME walk every time, so dragging
// shows change rather than noise.

import {
  DESCENT_STEP_MINUTES,
  FLAT_PACE_STEP_MPH,
  MAX_DESCENT_MINUTES_PER_1000M,
  MIN_DESCENT_MINUTES_PER_1000M,
  MAX_ASCENT_METERS_PER_HOUR,
  MAX_FLAT_PACE_MPH,
  MIN_ASCENT_METERS_PER_HOUR,
  MIN_FLAT_PACE_MPH,
  STANDARD_ASCENT_METERS_PER_HOUR,
  STANDARD_FLAT_PACE_MPH,
  STANDARD_PACE,
  isStandardPace,
  paceEstimate,
  type PaceProfile,
} from '../lib/pace'
import {
  feetFromMetres,
  formatDistance,
  formatElevation,
  formatSpeed,
  type UnitSystem,
} from '../lib/units'

/**
 * The walk the preview describes.
 *
 * McAfee Knob's leg, which is a real published highlight rather than a round
 * number: 4.0 miles and about 1,740 ft of climb. Fixed rather than "the walk
 * you last looked at", because a preview that changes its subject while you
 * drag shows two things moving and explains neither.
 */
const SAMPLE_WALK = { distanceMi: 4.0, ascentFt: 1740, descentFt: 1740 }

/**
 * "+1h / 480 m" - how much climbing buys an extra hour.
 *
 * Through lib/units.ts like every other height in the app, so it comes out in
 * the system the hiker chose. The profile stores METRES because that is how
 * Naismith's term is defined; formatElevation takes feet, and units.ts owns
 * the conversion between them rather than this file keeping a second copy.
 */
function climbLabel(metersPerHour: number, units: UnitSystem): string {
  return `+1h / ${formatElevation(feetFromMetres(metersPerHour), units)}`
}

/**
 * "+30 min / 1,000 m", or "None" (#900).
 *
 * Its own idiom rather than the ascent term's "+1h / N m", because it measures
 * a different thing: the ascent control is Naismith's own and keeps his units,
 * while descent is not in the rule at all. Reading them as one pair would
 * suggest a symmetry the arithmetic does not have.
 */
function descentLabel(minutesPer1000m: number, units: UnitSystem): string {
  if (minutesPer1000m <= 0) return 'None'
  const per = formatElevation(feetFromMetres(1000), units)
  return `+${Math.round(minutesPer1000m)} min / ${per}`
}

export interface PaceSettingsProps {
  pace: PaceProfile
  units: UnitSystem
  onChange: (next: PaceProfile) => void
}

export function PaceSettings({ pace, units, onChange }: PaceSettingsProps) {
  const estimate = paceEstimate(SAMPLE_WALK, pace)
  const standard = isStandardPace(pace)

  return (
    <section className="settings__group" aria-labelledby="pace-heading">
      <h2 className="settings__heading" id="pace-heading">
        Pace
      </h2>
      <p className="settings__note">
        Estimates start from a standard walking rule. Adjust it to match yourself.
      </p>

      <div className="settings__row settings__row--stacked">
        <label className="settings__label" htmlFor="pace-flat">
          Flat pace
        </label>
        <output className="settings__value" htmlFor="pace-flat">
          {formatSpeed(pace.flatPaceMph, units)}
        </output>
        <input
          id="pace-flat"
          type="range"
          min={MIN_FLAT_PACE_MPH}
          max={MAX_FLAT_PACE_MPH}
          step={FLAT_PACE_STEP_MPH}
          value={pace.flatPaceMph}
          onChange={(event) =>
            onChange({ ...pace, flatPaceMph: Number(event.target.value) })
          }
        />
        <p className="settings__scale">
          Standard is {formatSpeed(STANDARD_FLAT_PACE_MPH, units)}
        </p>
      </div>

      <div className="settings__row settings__row--stacked">
        <label className="settings__label" htmlFor="pace-climb">
          Climbing penalty
        </label>
        <output className="settings__value" htmlFor="pace-climb">
          {climbLabel(pace.ascentMetersPerHour, units)}
        </output>
        {/* Inverted: dragging RIGHT is a steeper penalty, which is fewer metres
            per hour. Left-to-right has to mean "harder for me" or the control
            reads backwards, and the underlying number runs the other way. */}
        <input
          id="pace-climb"
          type="range"
          min={MIN_ASCENT_METERS_PER_HOUR}
          max={MAX_ASCENT_METERS_PER_HOUR}
          step={10}
          value={
            MIN_ASCENT_METERS_PER_HOUR +
            MAX_ASCENT_METERS_PER_HOUR -
            pace.ascentMetersPerHour
          }
          onChange={(event) =>
            onChange({
              ...pace,
              ascentMetersPerHour:
                MIN_ASCENT_METERS_PER_HOUR +
                MAX_ASCENT_METERS_PER_HOUR -
                Number(event.target.value),
            })
          }
        />
        <p className="settings__scale">
          Standard is {climbLabel(STANDARD_ASCENT_METERS_PER_HOUR, units)}
        </p>
      </div>

      <div className="settings__row settings__row--stacked">
        <label className="settings__label" htmlFor="pace-descent">
          Descent penalty
        </label>
        <output className="settings__value" htmlFor="pace-descent">
          {descentLabel(pace.descentMinutesPer1000m, units)}
        </output>
        {/* NOT inverted, unlike the climbing control above: this number runs
            the same way the feeling does, so dragging right is harder. Zero is
            the left-most stop and is the standard - Naismith has no descent
            term, so "none" is the rule rather than an opt-out. */}
        <input
          id="pace-descent"
          type="range"
          min={MIN_DESCENT_MINUTES_PER_1000M}
          max={MAX_DESCENT_MINUTES_PER_1000M}
          step={DESCENT_STEP_MINUTES}
          value={pace.descentMinutesPer1000m}
          onChange={(event) =>
            onChange({
              ...pace,
              descentMinutesPer1000m: Number(event.target.value),
            })
          }
        />
        {/* Says which way this one can go, because it can only go one way and
            a hiker who is quick downhill will look for the other. */}
        <p className="settings__scale">
          Standard is none. This can only add time, never subtract it.
        </p>
      </div>

      <div className="settings__preview">
        <p className="settings__preview-head">Your estimates now read</p>
        <p className="settings__preview-time">{estimate.text}</p>
        {/* The baseline, whenever there is one. Absent at the standard pace,
            because "1.0× standard" on a fresh install is a caveat that teaches
            hikers to stop reading the ones that matter. */}
        {estimate.relativeLine !== null && (
          <p className="settings__preview-rel">{estimate.relativeLine}</p>
        )}
        {/* Converted too. Hardcoded, this line showed a metric hiker "4.0 mi
            with 1,740 ft of climb" under a preview in km/h - which the unit
            invariant test caught. */}
        <p className="settings__preview-of">
          for a {formatDistance(SAMPLE_WALK.distanceMi, units)} walk with{' '}
          {formatElevation(SAMPLE_WALK.ascentFt, units)} up and{' '}
          {formatElevation(SAMPLE_WALK.descentFt, units)} down
        </p>
      </div>

      <p className="settings__note">Kept on this phone, and never sent anywhere.</p>

      {/* Only once there is something to undo. A reset that is always there
          invites fiddling with a number a hiker has no reason to move. */}
      {!standard && (
        <button
          type="button"
          className="settings__action"
          onClick={() => onChange(STANDARD_PACE)}
        >
          Reset to standard
        </button>
      )}
    </section>
  )
}
