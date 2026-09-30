// Keeping a spot marked on the map, as a window of its own (#1563, the
// maintainer's steer of 2026-09-17: "the Keep this should be an emergent
// window").
//
// WHAT THIS REPLACES. The crosshair's bar (chrome/ReportPickBar.tsx) used to
// carry the Keep button beside its answer, so the one decision that commits
// a hand-placed location - the least trustworthy of the four kinds of place
// a report can carry - sat on a slim strip at the foot of the map, next to
// Cancel. It is a window now, opened by the tap that aimed: the answer the
// tap got, said large, and Keep under it. The bar stays for the aiming
// itself, because a window cannot say "tap the map" over a map that must be
// tappable.
//
// THE ANSWER IS THE POINT. lib/placement.ts's three - a mile, "This spot",
// "More than 3 mi off the trail" - and the hiker reads which one they got
// before agreeing to file under it. Dismissing (Escape, a tap beside the
// window) means "tap again", not "leave": the aim is cleared and the map is
// theirs once more. Cancel, in the header, is the way back to the report
// without a place.

import { Sheet } from './Sheet'
import './keepSpotSheet.css'

export interface KeepSpotSheetProps {
  /** What the tapped point is called - lib/placement.ts's `placeWords`. */
  words: string
  /** Keep the aimed point as the report's location. */
  onKeep: () => void
  /** Clear the aim and leave the map up to tap again. */
  onTapAgain: () => void
  /** Back to the report, changing nothing. */
  onCancel: () => void
}

export function KeepSpotSheet({
  words,
  onKeep,
  onTapAgain,
  onCancel,
}: KeepSpotSheetProps) {
  return (
    <Sheet
      name="keep-spot"
      title="Keep this spot?"
      action={{ label: 'Cancel', onClick: onCancel, testId: 'keep-spot-cancel' }}
      onDismiss={onTapAgain}
      className="keep-spot"
    >
      {/* `role="status"` so the answer is announced as the window opens: the
          point of this window is that the hiker reads what they got before
          agreeing to it, and a hiker using a screen reader gets the same. */}
      <p className="keep-spot__words" data-testid="keep-spot-words" role="status">
        {words}
      </p>
      <p className="keep-spot__hint">
        Marked by hand on the map. The report says so, and whoever reads it sees that
        beside the coordinates.
      </p>
      <button
        type="button"
        className="keep-spot__keep"
        data-testid="keep-spot-keep"
        onClick={onKeep}
      >
        Keep this spot
      </button>
      <button
        type="button"
        className="keep-spot__again"
        data-testid="keep-spot-again"
        onClick={onTapAgain}
      >
        Tap again
      </button>
    </Sheet>
  )
}
