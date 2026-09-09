// One day of a plan, wherever a day is listed (#1373, review rule R7).
//
// "Anywhere a day is listed - a plan, a diff, what's left - it carries
// distance, estimated time at the hiker's pace, and elevation gain, in one
// shared row component. Never distance alone, and never a second copy of the
// layout." Step 3's days, the cascade diff, What's left and the Plan timeline
// all mount this.
//
// FOUR THINGS THE TIMELINE'S ROW ENCODED ARE KEPT, because each one is a
// decision with a test behind it and a rebuilt row that dropped any of them
// would be a quiet regression:
//
//   1. ROW HEIGHT = WALKING HOURS (lib/planDisplay.ts dayRowHeight, wireframe
//      1b). A hard day is bigger on the screen, so a section's shape can be
//      felt by scrolling it. The floor is the app's own minimum touch target.
//   2. THE BASELINE BESIDE EVERY PACE-ADJUSTED TIME (#851, #1350,
//      test/paceBaseline.test.ts): a time at the hiker's own pace prints with
//      what it was adjusted from, or it does not print. `PricedLeg` makes the
//      two inseparable at the type level, which is why this row takes one
//      rather than a `text` string.
//   3. A HOLE IN THE DEM WITHHOLDS THE CLIMB AND THE TIME (#1039). Flat ground
//      understates both, and understated is the direction that gets somebody
//      caught out after dark - so the distance stays, the other two are
//      withheld, and the row says they were withheld.
//   4. "NEVER DISTANCE ALONE" MEANS THE ROW SAYS WHY when that is all it has:
//      with no profile at all it prints the distance and "no profile", not
//      the distance alone as though nothing were missing.
//
// STATES ARE WORDS ON THE FOOT, NEVER A COLOUR ALONE: walked, moved, new,
// zero. The diff before a cascade applies (F7) is read as these four words
// under each day, plus a note in the day's own mono - "was Wed · now Thu" -
// so what moved is a fact about the plan and never a verdict on the hiker.
//
// Every figure passes through lib/units.ts or arrives already formatted by
// it; this file rounds nothing.

import { MIN_ROW_PX, dayRowHeight } from '../lib/planDisplay'
import type { PricedLeg } from '../lib/route'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'
import './dayRow.css'

export type DayRowState = 'planned' | 'walked' | 'moved' | 'new' | 'zero'

export interface DayRowProps {
  /** The gutter's word: "D1", "Thu", "Day 4". */
  label: string
  /** "→ Mohican Outdoor Center", or "Zero in Unionville". */
  title: string
  distanceMi: number
  /** The day priced at the hiker's pace, or undefined with no profile. */
  figures?: PricedLeg
  units: UnitSystem
  state?: DayRowState
  resupply?: boolean
  /** What changed, in the plan's own words: "was Wed · now Thu",
   *  "was 17.1 mi". Null or undefined prints nothing. */
  note?: string | null
  /** The day's terrain, drawn by the caller (Plan's DayTerrain), so this row
   *  holds no second copy of the profile arithmetic. */
  terrain?: React.ReactNode
  /** The high point, already formatted: "1,480 ft". */
  high?: string
  /** Every listed day carries its own Edit (R9); omitted, none is drawn. */
  onEdit?: () => void
  /** Open the day. Omitted, the body is not a control. */
  onOpen?: () => void
  className?: string
}

const STATE_WORDS: Record<DayRowState, string | null> = {
  planned: null,
  walked: 'walked',
  moved: 'moved',
  new: 'new day',
  zero: 'zero',
}

export function DayRow({
  label,
  title,
  distanceMi,
  figures,
  units,
  state = 'planned',
  resupply = false,
  note,
  terrain,
  high,
  onEdit,
  onOpen,
  className,
}: DayRowProps) {
  const measured = figures !== undefined && figures.unmeasuredMi === 0
  const height = figures === undefined ? MIN_ROW_PX : dayRowHeight(figures.minutes)
  const stateWord = STATE_WORDS[state]

  const figuresLine =
    state === 'zero'
      ? 'no walking'
      : [
          formatDistance(distanceMi, units),
          measured ? figures.estimate.text : null,
          measured ? `${formatElevation(figures.ascentFt, units)} up` : null,
        ]
          .filter((part) => part !== null)
          .join(' · ')

  const body = (
    <>
      <span className="day-row__gutter">{label}</span>
      {resupply && (
        <span className="day-row__resupply" role="img" aria-label="resupply">
          ▣
        </span>
      )}
      <span className="day-row__text">
        <span className="day-row__title">{title}</span>
        <span className="day-row__figures">{figuresLine}</span>
        {measured && figures.estimate.relativeLine !== null && (
          <span className="day-row__figures day-row__figures--baseline">
            {figures.estimate.relativeLine}
          </span>
        )}
        {figures !== undefined && figures.unmeasuredMi > 0 && state !== 'zero' && (
          <span className="day-row__figures day-row__figures--unmeasured">
            no climb measured for {formatDistance(figures.unmeasuredMi, units, 'trimmed')}{' '}
            of this day
          </span>
        )}
        {figures === undefined && state !== 'zero' && (
          <span className="day-row__figures day-row__figures--unmeasured">
            no profile for this day
          </span>
        )}
        {note !== undefined && note !== null && note !== '' && (
          <span className="day-row__note">{note}</span>
        )}
      </span>
    </>
  )

  return (
    <div
      className={['day-row', `day-row--${state}`, className].filter(Boolean).join(' ')}
      style={{ minHeight: height }}
      data-state={state}
    >
      {onOpen === undefined ? (
        <div className="day-row__body">{body}</div>
      ) : (
        <button
          type="button"
          className="day-row__body day-row__body--opens"
          onClick={onOpen}
        >
          {body}
        </button>
      )}
      {terrain !== undefined && terrain !== null && (
        <div className="day-row__terrain">
          {terrain}
          {high !== undefined && <span className="day-row__high">{high}</span>}
        </div>
      )}
      {(stateWord !== null || onEdit !== undefined) && (
        <div className="day-row__foot">
          {stateWord !== null && <span className="day-row__state">{stateWord}</span>}
          {onEdit !== undefined && (
            <button type="button" className="day-row__edit" onClick={onEdit}>
              Edit this day ›
            </button>
          )}
        </div>
      )}
    </div>
  )
}
