// Planning a section WITHOUT leaving the hike room (#1344).
//
// The Plan tab's primary used to run `sweepForBuilder`, which does
// `setActiveTab('map')` and opens the route builder's entrance over the
// canvas. A maintainer's ask - "Plan the next section should be 'Plan a
// section', and that content should live on the same page" - is #1329's
// complaint one level along: the app kept moving them somewhere else.
//
// WHY THIS IS NOT A SECOND ROUTE BUILDER, which is the thing it would be
// easiest to accidentally become. Two pieces already do the whole job and
// neither of them needs a map:
//
//   RouteStopPicker   names a point on the centerline. #1329 already reuses
//                     it for a hike's own points, map door and all.
//   PlanTargetSheet   takes `route: ViaStop[]` plus a target and returns a
//                     finished `HikePlan` (planDaysVia + buildPlan). It is a
//                     form; it renders no canvas.
//
// So this panel is the join between them: two ends, and then the shell hands
// those ends to the target sheet in this same slot. Nothing here lays out a
// day, prices a leg or names a place - it would be a fourth opinion about
// each if it did.
//
// THE MAP DOOR STAYS, AND STAYS EXPLICIT. Tapping the trail is the one part
// that genuinely needs the canvas, and a hiker who wants it should have it -
// so it hands off to the route builder rather than reimplementing it. That
// is the same shape as the hike-point picker's own map door: inline by
// default, the map when you ask for it.

import { stopLabel } from '../lib/planDisplay'
import type { PlaceRef } from '../lib/hikes'
import '../screens/plan.css'

export interface SectionPlannerProps {
  /** The two ends, each null until it is named. */
  from: PlaceRef | null
  to: PlaceRef | null
  onPickFrom: () => void
  onPickTo: () => void
  /** Hand off to the route builder on the map - the one part of this that
   *  needs a canvas. */
  onChooseOnMap: () => void
  onCancel: () => void
}

export function SectionPlanner({
  from,
  to,
  onPickFrom,
  onPickTo,
  onChooseOnMap,
  onCancel,
}: SectionPlannerProps) {
  return (
    <section className="section-planner" aria-label="Plan a section">
      <div className="plan-home__section-head">
        <span className="plan-home__title">A section on this hike</span>
        <button type="button" className="plan-home__all" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {/* `RouteStopsPanel`'s row anatomy, at two rows. The classes are that
          panel's so the two never drift into two ways of drawing a stop. */}
      <div className="section-planner__ends">
        <End label="From" place={from} onPick={onPickFrom} />
        <End label="To" place={to} onPick={onPickTo} />
      </div>

      <button type="button" className="section-planner__map" onClick={onChooseOnMap}>
        Draw it on the map instead
      </button>

      <p className="plan-home__quiet-note">
        Two ends is the whole requirement here, the same as the hike&rsquo;s own. Name
        them and the next step asks how long a day is; the days come from the profile
        between them, not from this panel.
      </p>
    </section>
  )
}

function End({
  label,
  place,
  onPick,
}: {
  label: string
  place: PlaceRef | null
  onPick: () => void
}) {
  return (
    <button type="button" className="route-stops__field" onClick={onPick}>
      <span className="section-planner__end-label">{label}</span>
      <span className="section-planner__end-name">
        {/* An unnamed end says so rather than showing a gap: a blank field is
            indistinguishable from one whose name failed to render. */}
        {place === null ? 'Choose a place ›' : stopLabel(place)}
      </span>
    </button>
  )
}
