// Adding a day hike to a long hike (#1317).
//
// ONLY THE MILES ON THIS TRAIL COUNT, and that is what makes the door
// offerable at all. A day hike that wandered onto side trails is still a day
// on this trail for the part of it that was, so it can join - the hike's
// roll-up clips every section to its own ends already (`clipSpans`), and this
// is the same rule met one level up.
//
// A DAY HIKE NOT ON THIS TRAIL IS A SENTENCE, NEVER A DEAD BUTTON.
// chrome/LineSheet.tsx's rule, and the reasoning transfers exactly: a control
// that looks pressable and is not teaches a hiker the app is broken, where a
// sentence tells them what is missing. So an off-trail candidate renders as
// an unavailable door carrying its own reason rather than being hidden -
// hiding it would leave a hiker hunting for a walk they can see in the list
// one screen away.

import '../screens/plan.css'

export interface DayHikeCandidate {
  id: string
  name: string
  /** `8.8 mi · walked 4 May · mi 712.3–716.7 on this trail`, or the reason
   *  this one cannot join. */
  meta: string
  /** Whether any of it is on the hike's trail. */
  eligible: boolean
}

export interface AddDayHikeSheetProps {
  candidates: readonly DayHikeCandidate[]
  onAdd: (id: string) => void
  onClose: () => void
}

export function AddDayHikeSheet({ candidates, onAdd, onClose }: AddDayHikeSheetProps) {
  return (
    <div className="plan-kind" role="dialog" aria-label="Add a day hike to this hike">
      <div className="legend__head">
        <h2 className="legend__title">Add a day hike to this hike</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="plan-kind__lede">
        A day hike on this trail counts toward the hike like any section does. One that
        wandered onto side trails can still join — only the miles on this trail are
        counted.
      </p>

      {candidates.length === 0 && (
        <p className="plan-home__refused">
          No saved day hikes yet. One you walk on this trail can join this hike later.
        </p>
      )}

      {candidates.map((candidate) => (
        <button
          type="button"
          className={
            candidate.eligible
              ? 'plan-kind__door'
              : 'plan-kind__door plan-kind__door--unavailable'
          }
          key={candidate.id}
          disabled={!candidate.eligible}
          onClick={() => onAdd(candidate.id)}
        >
          <span className="plan-kind__door-name">{candidate.name}</span>
          <span className="plan-kind__door-note">{candidate.meta}</span>
        </button>
      ))}
    </div>
  )
}
