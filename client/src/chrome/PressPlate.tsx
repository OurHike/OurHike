// What a press and hold on the map opens (#1137).
//
// The third door into the crew relationship, after Today's foot and a place's
// card, and the only one that can name a spot the app has no name for. Both
// the others anchor on something already named - the hiker's own fix, or a
// waypoint. This one anchors on a point, which is what the "somebody cleared
// forty blowdowns out of this mile" case in features/SAYING_THANKS.md needs.
//
// SMALL, AND AT THE PRESS. It is not a sheet and not a screen: a hiker who
// pressed a spot is looking at that spot, and a panel that slid up from the
// bottom would cover the thing they were pointing at. It is also why the plate
// closes on the first map movement rather than following the point around -
// see App.tsx's handler. A transient plate that goes when you pan is honest
// about being transient; one that chases its anchor across the screen is a
// second thing to dismiss.
//
// WHAT IT DOES NOT DO IS FILE ANYTHING. Both buttons open a door - the report
// window for a problem, the thanks form for a thanks - and neither writes a
// record. That is deliberate against #1133's own one-tap rule: a tap on a
// category tile files because the hiker has already said what they found, and
// a press on bare map has said only where.

import { Button } from '../design-system/components/core/Button'
import { MAX_OFF_TRAIL_MILES } from '../lib/trailPosition'
import { formatDistance, type UnitSystem } from '../lib/units'
import './pressPlate.css'

export interface PressPlateProps {
  /** Where the plate sits, in canvas pixels - the point that was pressed. */
  point: { x: number; y: number }
  /** The map's own size, so the plate can stay inside it. */
  within: { width: number; height: number }
  /**
   * The trail mile under the press, or null.
   *
   * Null carries TWO different facts and the plate must not merge them, which
   * is #249's distinction on a new surface: `knowsTrail` false means the phone
   * has no trail index and cannot answer, and null WITH an index means the
   * point is genuinely off the corridor (lib/trailPosition.ts refuses past
   * MAX_OFF_TRAIL_MILES). "We could not check" and "you are three miles into
   * the woods" are opposite things to tell somebody.
   */
  mile: number | null
  knowsTrail: boolean
  units: UnitSystem
  onReport: () => void
  onThanks: () => void
  onClose: () => void
}

/** Roughly the plate's own size, for keeping it on screen. Measured from the
 *  stylesheet rather than the DOM: reading it back would mean a layout pass
 *  and a second render, for a panel whose size is fixed by its own CSS. */
const PLATE_WIDTH = 208
const PLATE_HEIGHT = 132
const PLATE_MARGIN = 8

export function PressPlate({
  point,
  within,
  mile,
  knowsTrail,
  units,
  onReport,
  onThanks,
  onClose,
}: PressPlateProps) {
  // Clamped rather than flipped. A plate that jumps to the other side of the
  // finger when it nears an edge is a plate that moved for reasons the hiker
  // cannot see; sliding it back onto the screen keeps it where they pressed,
  // as nearly as the screen allows.
  const left = Math.min(
    Math.max(point.x - PLATE_WIDTH / 2, PLATE_MARGIN),
    Math.max(within.width - PLATE_WIDTH - PLATE_MARGIN, PLATE_MARGIN),
  )
  const top = Math.min(
    Math.max(point.y - PLATE_HEIGHT - PLATE_MARGIN, PLATE_MARGIN),
    Math.max(within.height - PLATE_HEIGHT - PLATE_MARGIN, PLATE_MARGIN),
  )

  return (
    <div
      className="press-plate"
      role="dialog"
      aria-label="Report or thank at this spot"
      data-testid="press-plate"
      style={{ left, top }}
    >
      <p className="press-plate__where" data-testid="press-plate-where">
        {whereWords(mile, knowsTrail, units)}
      </p>
      {/* Located by their accessible names rather than test ids: the
          design-system Button destructures a fixed prop list and does not
          forward `data-testid`, so one written here would be silently dropped
          - an attribute that looks like a hook and is not. Widening a shared
          component for one screen is the wrong trade, and the label is what a
          hiker reads anyway. */}
      <div className="press-plate__actions">
        <Button
          variant="secondary"
          size="s"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={onReport}
        >
          Report a problem
        </Button>
        <Button
          variant="primary"
          size="s"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={onThanks}
        >
          Say thanks
        </Button>
      </div>
      <button
        type="button"
        className="press-plate__close"
        data-testid="press-plate-close"
        onClick={onClose}
      >
        Not here
      </button>
    </div>
  )
}

/**
 * The one line naming where the press landed.
 *
 * Three answers, and the third is the one worth having: a mile when there is
 * one, "we could not check" when the trail index is not on the phone, and "off
 * the trail" when the index IS here and refused the point. Collapsing the last
 * two into one sentence would tell a hiker with no download that they were
 * standing in the woods.
 */
export function whereWords(
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
