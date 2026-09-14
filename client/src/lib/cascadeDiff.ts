// What a cascade would move, before it is applied (#1373, frame 7b).
//
// The cascade (lib/cascade.ts) hands back whole re-planned plans, and the
// choice sheet has offered each with one line of consequence since #758 -
// "finish ≈ 3 Jun, unchanged", "2 days more". What nobody could see before
// pressing was WHICH days move and how: the day arriving at Rutherford is a
// day later, the zero in Unionville slid to Friday, a seventh day appeared.
// The design's rule R7 is that anywhere a day is listed it carries its
// figures in one shared row, and its frame 7b lists the re-planned days with
// a word on each - walked, moved, new - and a note in the plan's own terms,
// "was Wed · now Thu", "was 17.1 mi". This computes those words and notes;
// the sheet prints them through DayRow.
//
// BY INDEX, WHICH IS THE PLAN'S OWN IDENTITY. A cascade re-plans between
// barriers and keeps the walked prefix, so day i after is what became of day
// i before, until the counts diverge: a day past the old count is new, and
// days the new plan has fewer of are counted rather than drawn, because
// there is no row of the new plan to hang "gone" on. A day is "moved" when
// its date, its length or its end changed; "kept" when nothing did, and the
// row says nothing - the absence of a word is the honest state of a day the
// cascade did not touch.
//
// No verdicts. Nothing here says ahead, behind, or short; the notes are facts
// about the plan and the walked days are records (cascade.ts's "THE PAST IS
// A RECORD"), printed as such.

import { planDayViews, type HikePlan, type PlanDayView, type PlanStop } from './plan'

export type DiffState = 'walked' | 'kept' | 'moved' | 'new'

export interface DiffRow {
  /** The day as the re-planned plan lists it. */
  day: PlanDayView
  state: DiffState
  /** The date it had before, when the date moved. */
  wasDate: string | null
  /** The length it had before, when the length moved. */
  wasDistanceMi: number | null
  /** The stop it ended at before, when the end moved. */
  wasEnd: PlanStop | null
}

export interface PlanDiff {
  rows: DiffRow[]
  /** Days the new plan has fewer of - counted, since they have no row. */
  fewer: number
}

/** Two lengths the same day, within the rounding lib/units.ts prints at -
 *  reasoned from the formatter's one decimal place, so a change this diff
 *  calls "moved" is one the row's own figure would show. */
const SAME_MI = 0.05

export function diffPlans(before: HikePlan, after: HikePlan): PlanDiff {
  const was = planDayViews(before)
  const rows = planDayViews(after).map((day): DiffRow => {
    if (day.walked) {
      return { day, state: 'walked', wasDate: null, wasDistanceMi: null, wasEnd: null }
    }
    const earlier = was[day.index]
    if (earlier === undefined) {
      return { day, state: 'new', wasDate: null, wasDistanceMi: null, wasEnd: null }
    }
    const length = Math.abs(day.end.mile - day.start.mile)
    const earlierLength = Math.abs(earlier.end.mile - earlier.start.mile)
    const dateMoved = (earlier.date ?? null) !== (day.date ?? null)
    const lengthMoved = Math.abs(length - earlierLength) > SAME_MI
    const endMoved = earlier.end.mile !== day.end.mile
    if (!dateMoved && !lengthMoved && !endMoved) {
      return { day, state: 'kept', wasDate: null, wasDistanceMi: null, wasEnd: null }
    }
    // Every row that says "moved" carries what moved (the header's promise
    // of "a note in the plan's own terms"): the first version carried the
    // date and the length, so a day whose END moved with neither was a
    // word with nothing behind it (#1374 review).
    return {
      day,
      state: 'moved',
      wasDate: dateMoved ? (earlier.date ?? null) : null,
      wasDistanceMi: lengthMoved ? earlierLength : null,
      wasEnd: endMoved ? earlier.end : null,
    }
  })
  return { rows, fewer: Math.max(0, was.length - rows.length) }
}
