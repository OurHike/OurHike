// Which way the hiker is walking, inferred from how their mile marker moves.
//
// There is no "which way are you going" question anywhere in onboarding, and
// deliberately so - it is one more thing to get wrong before the app has shown
// it is worth trusting, and the answer is observable anyway.
//
// Inference waits for a quarter mile of movement in one direction rather than
// reacting to consecutive fixes. A GPS under tree cover wanders by tens of
// feet while the phone sits still in a pocket, so a smaller threshold would
// have the header flipping NOBO/SOBO at a lunch stop - which reads as the app
// being confused about something the hiker can see plainly.

import type { HikeDirection } from '../chrome/Header'

export const DIRECTION_THRESHOLD_MILES = 0.25

export interface DirectionTracker {
  /** The mile the current comparison is measured from. */
  anchorMile: number
  /** Undefined until enough movement has happened to be sure. */
  direction: HikeDirection | undefined
}

export function startTracking(mile: number): DirectionTracker {
  return { anchorMile: mile, direction: undefined }
}

export function trackDirection(
  tracker: DirectionTracker,
  mile: number,
  thresholdMiles: number = DIRECTION_THRESHOLD_MILES,
): DirectionTracker {
  const moved = mile - tracker.anchorMile

  if (Math.abs(moved) < thresholdMiles) return tracker

  // The anchor resets to here, so the next quarter mile is measured from
  // where the hiker actually is. Without this a turnaround would need to
  // undo all the distance walked before it before the header caught up.
  return { anchorMile: mile, direction: moved > 0 ? 'NOBO' : 'SOBO' }
}
