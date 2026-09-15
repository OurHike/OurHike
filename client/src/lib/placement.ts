// What a placed point is CALLED - one function, for every surface that lets
// somebody put a report somewhere (#1439, D16).
//
// WHY THIS IS A MODULE AND NOT A FUNCTION INSIDE PressPlate.tsx, which is
// where it lived until now. There are two surfaces that name a point a hiker
// chose: the long-press plate on the map, and the report form's "Change",
// which drops a crosshair for somebody whose phone never got a fix or who
// walked on before filing. The handoff asks for exactly one placement
// function shared between them, and the reason is the three answers below -
// if the plate and the form each spelled them, one of them would eventually
// collapse two of the three into a single sentence.
//
// THE THREE ANSWERS, and the third is the one worth having:
//
//   - a MILE, when the point is on the corridor and the phone can say so;
//   - "This spot", when the trail index is not on the phone at all - nobody
//     has looked, and saying anything about the trail would be an invention;
//   - "More than 3 mi off the trail", when the index IS here and refused the
//     point (lib/trailPosition.ts's MAX_OFF_TRAIL_MILES).
//
// Collapsing the last two would tell a hiker with no download that they were
// standing three miles into the woods, which is a different and alarming
// claim. features/SAYING_THANKS.md states the same three as a commitment.

import { MAX_OFF_TRAIL_MILES } from './trailPosition'
import { formatDistance, type UnitSystem } from './units'

export function placeWords(
  mile: number | null,
  knowsTrail: boolean,
  units: UnitSystem,
): string {
  if (mile !== null) {
    // A MARKER, NOT A DISTANCE - so it is written the way every other mile
    // marker in this app is, and never through `formatDistance`. #986 is the
    // bug: the same number through a distance formatter reads "1,010.4 km" for
    // a metric hiker, which is a position on this trail naming somewhere else.
    return `mi ${mile.toLocaleString('en-US', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}`
  }
  if (!knowsTrail) return 'This spot'
  // A DISTANCE here, genuinely, so it goes through lib/units.ts: it is how far
  // the corridor search reaches, not a place on it.
  return `More than ${formatDistance(MAX_OFF_TRAIL_MILES, units, 'trimmed')} off the trail`
}
