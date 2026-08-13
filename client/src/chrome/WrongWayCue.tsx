// The in-app wrong-way cue (WIREFRAMES.md §9, beat 1).
//
// The hedge in "You may be off the trail" is deliberate. GPS under tree
// canopy is not reliable enough to justify certainty, and telling someone
// standing squarely on the trail that they are off it is precisely the false
// positive that spends this feature's entire trust budget - the cost
// HIKER_SAFETY.md singles out as mattering more here than almost anywhere
// else in the project. "May be" is the strongest claim the data supports.
//
// "Show me the way back" points; it does not route. Same position the closure
// sheet takes - OurHike does not work out detours.

import { formatShortDistance, type UnitSystem } from '../lib/units'

export interface WrongWayCueProps {
  open: boolean
  /** The displacement lib/wrongWay.ts measured, in the feet it computes in.
   *  Converted for display only - see lib/units.ts. */
  distanceFt: number
  minutes: number
  /** Which units the sentence reads in. Defaults as every other display
   *  component here does, to lib/userPreferences.ts's own default. */
  units?: UnitSystem
  onShowWayBack: () => void
  onDismiss: () => void
}

export function WrongWayCue({
  open,
  distanceFt,
  minutes,
  units = 'imperial',
  onShowWayBack,
  onDismiss,
}: WrongWayCueProps) {
  if (!open) return null

  return (
    <div className="wrong-way-cue" role="alert">
      <p className="wrong-way-cue__text">
        {`You may be off the trail — about ${formatShortDistance(distanceFt, units)} from the blazes for the last ${minutes} minutes.`}
      </p>

      <div className="wrong-way-cue__actions">
        <button type="button" className="wrong-way-cue__primary" onClick={onShowWayBack}>
          Show me the way back
        </button>
        <button type="button" className="wrong-way-cue__secondary" onClick={onDismiss}>
          I&rsquo;m fine
        </button>
      </div>
    </div>
  )
}
