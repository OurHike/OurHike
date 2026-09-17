// The report's crosshair, open: a slim bar over the map saying what a tap
// will do, and then what the tap got (#1439, D16, frame 9f).
//
// WHY THIS IS NOT `RouteMapPickBar`, which it stands in the same slot as and
// looks like. Two differences, and both are about what the two picks mean.
//
// A ROUTE STOP OFF THE CORRIDOR IS MEANINGLESS, so that bar's whole second
// state is a refusal - "there's no honest mile to give it". A REPORT off the
// corridor is ordinary: `describeLocation`'s second state is exactly that,
// and features/SAYING_THANKS.md already settled the same question for the
// long-press plate ("off the corridor is accepted, not refused"). So every
// tap here is placeable, and there is no refusal to draw.
//
// AND THE MILE IS NAMED BEFORE IT IS KEPT. The route pick commits on the tap
// because a refusal is the only thing it has to say. Here what a hiker needs
// to see is WHICH of the three answers they got - a mile, "this spot", or
// more than three miles off the trail - before they agree to file under it.
// So the tap aims and a window commits (reporting/KeepSpotSheet.tsx, the
// maintainer's steer of 2026-09-17), which is also what makes a mis-tap
// free. Keep lived on this bar until then; what is left here is the aiming -
// what a tap will do, the answer it got, and Cancel.
//
// The three answers are lib/placement.ts's, shared with the press plate, so
// the two surfaces that let somebody choose a point cannot come to describe
// one differently.

import { placeWords } from '../lib/placement'
import type { UnitSystem } from '../lib/units'

export interface ReportPickBarProps {
  /** The point tapped so far, or null before the first tap. */
  aiming: { lat: number; lon: number } | null
  /** That point's trail mile, or null - see `placeWords` for the two very
   *  different things null means and why they are not merged. */
  mile: number | null
  knowsTrail: boolean
  units: UnitSystem
  /** Back to the form, changing nothing. */
  onCancel: () => void
}

export function ReportPickBar({
  aiming,
  mile,
  knowsTrail,
  units,
  onCancel,
}: ReportPickBarProps) {
  return (
    <div
      className="route-map-pick route-map-pick--report"
      role="dialog"
      aria-label="Say where this was"
    >
      <p className="route-map-pick__hint">
        {aiming === null ? (
          'Tap the map where this was.'
        ) : (
          // `role="status"` so the answer is announced when it changes: the
          // point of this bar is that the hiker reads what they got before
          // agreeing to it, and a hiker using a screen reader gets the same.
          <span role="status">{placeWords(mile, knowsTrail, units)}</span>
        )}
      </p>
      {/* No Keep here since the keep window: a tap opens it with the answer,
          so there is nothing to keep until there is something to keep (D10)
          and nothing pressable that does nothing. */}
      <button type="button" className="route-map-pick__cancel" onClick={onCancel}>
        Cancel
      </button>
    </div>
  )
}
