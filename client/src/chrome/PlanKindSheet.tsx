// "What are you planning?" - the door into the builder (#977, wireframe frame
// `1i`, features/HIKE_PLANNING.md "The day hike on a network").
//
// WHY A SHEET AND NOT A SECOND BUTTON
//
// screens/PlanHome.tsx has one primary action by design, and #805 settled that
// after a maintainer walking through the built app missed the 11-px link the
// tab's other half lived behind. "Plan a new trip" stays the single button;
// this is what it OPENS. The alternative - a second call to action on the Plan
// tab - would undo the one rule that page was rebuilt around.
//
// THE SENTENCE THAT DOES THE WORK
//
// "A day hike can use as many trails as you like. A trip follows one trail and
// breaks into days." Two options whose names both start with a duration would
// otherwise read as the same choice asked twice, and the difference that
// actually matters is not how long the walk is - it is whether it has one mile
// axis. That is the whole reason #928 exists, said in a sentence a hiker can
// use.
//
// WHEN THERE IS NO NETWORK TO ROUTE ON
//
// A day hike needs the junction graph (pipeline/build_trail_graph.py), and a
// phone can be without it - a release older than the artifact, a bucket a
// publish has not reached, or no signal on a first run. Then the option is a
// SENTENCE rather than a control that looks pressable and is not, which is
// chrome/LineSheet.tsx's rule and the reasoning transfers exactly: a dead
// button teaches a hiker the app is broken, where a sentence tells them what
// is missing.
//
// THE THIRD DOOR GOES SOMEWHERE OF ITS OWN
//
// "A walk I've already done" is #982, not #968's day-summary card
// (screens/DaySummary.tsx). That card describes a day inside an A.T. plan -
// its figures come from the plan's own days via lib/daySummary.ts; this
// describes a walk with no plan behind it,
// across a network. Two surfaces that look alike and know different things is
// the cheaper mistake - decided 2026-08-25.

import '../screens/plan.css'

export interface PlanKindSheetProps {
  /**
   * Whether the junction graph is loaded, so a day hike can actually be
   * routed. False is an ordinary state, not an error - see the header.
   */
  networkAvailable: boolean
  /** Whether the past-walk flow exists to open. False until #982 builds it -
   *  and false renders a sentence, not a dead control (LineSheet's rule). */
  walkedAvailable: boolean
  onPickDayHike: () => void
  onPickTrip: () => void
  onPickWalked: () => void
  onClose: () => void
}

export function PlanKindSheet({
  networkAvailable,
  walkedAvailable,
  onPickDayHike,
  onPickTrip,
  onPickWalked,
  onClose,
}: PlanKindSheetProps) {
  return (
    <div className="plan-kind" role="dialog" aria-label="What are you planning?">
      <div className="legend__head">
        <h2 className="legend__title">What are you planning?</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="plan-kind__lede">
        A day hike can use as many trails as you like. A trip follows one trail and breaks
        into days.
      </p>

      {networkAvailable ? (
        <button type="button" className="plan-kind__door" onClick={onPickDayHike}>
          <span className="plan-kind__door-name">A day hike</span>
          <span className="plan-kind__door-note">
            Out and back, a loop, or point to point — across any trails on the map.
          </span>
        </button>
      ) : (
        <div className="plan-kind__door plan-kind__door--unavailable">
          <span className="plan-kind__door-name">A day hike</span>
          <span className="plan-kind__door-note">
            Out and back, a loop, or point to point — across any trails on the map.
          </span>
          {/* Not a disabled button (LineSheet's rule): a sentence that names
              what is missing, so this reads as a thing the phone has not got
              yet rather than a thing the app cannot do. */}
          <span
            className="plan-kind__door-note plan-kind__door-note--refused"
            role="note"
          >
            This phone hasn&rsquo;t got the trail network yet, so there&rsquo;s nothing to
            build a day hike on. It arrives with the next data sync.
          </span>
        </div>
      )}

      <button type="button" className="plan-kind__door" onClick={onPickTrip}>
        <span className="plan-kind__door-name">A multi-day trip</span>
        <span className="plan-kind__door-note">
          Stops along one trail, then days, zeros and resupply.
        </span>
      </button>

      {walkedAvailable ? (
        <button type="button" className="plan-kind__door" onClick={onPickWalked}>
          <span className="plan-kind__door-name">A walk I&rsquo;ve already done</span>
          <span className="plan-kind__door-note">
            The same two ends, in the past tense.
          </span>
        </button>
      ) : (
        <div className="plan-kind__door plan-kind__door--unavailable">
          <span className="plan-kind__door-name">A walk I&rsquo;ve already done</span>
          <span className="plan-kind__door-note">
            The same two ends, in the past tense.
          </span>
          <span
            className="plan-kind__door-note plan-kind__door-note--refused"
            role="note"
          >
            Recording a finished walk isn&rsquo;t built yet. It&rsquo;s coming.
          </span>
        </div>
      )}
    </div>
  )
}
