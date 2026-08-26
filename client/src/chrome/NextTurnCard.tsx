// The turn a hiker is walking toward (#1041, frame `D9`).
//
// The lower-third card on the map while a day hike is being followed, and the
// smallest thing that answers "am I still going the right way": how far to the
// next junction, which trail to take there, and which one you are on now.
//
// WHY THE TRAIL YOU ARE ON IS ON THIS CARD. It looks redundant beside the
// header's "leg 2 of 3 · Pine Meadow Tr" and it is not: this is the line a
// hiker checks against the blazes around them RIGHT NOW, before any turn
// happens. Harriman-Bear Mountain has a junction every 1.2 miles
// (features/NEARBY_TRAILS.md, measured by #771) and 48% of sampled A.T. points
// there sit within 150 m of a different marked trail - so "you should be
// seeing blue" is a live claim somebody can falsify from where they stand,
// which is the only kind of navigation statement worth printing.
//
// NO ARRIVAL CLOCK, and no estimate at all for the distance to the turn. The
// walk's ≈time is on the card a hiker read before they left (#980, #1011);
// pricing 0.4 mi mid-walk would be Naismith applied to a stretch far shorter
// than its own error bars, printed as though it were a promise.
//
// THE LINK OPENS ONE JUNCTION, NOT A LIST. Frame `D9` writes "All 11 turns ›"
// and #980's ledger still holds the whole-walk turn list as deferred. What
// unblocked it was the naming question, which lib/dayHikeTurns.ts answers, so
// the list is now a screen somebody can build rather than a decision somebody
// owes - but it is not this change, and a link promising a list that does not
// exist would be worse than the one that says what it does.

import type { DayHikeTurn } from '../lib/dayHikeTurns'
import { blazeLabel } from '../lib/blaze'
import { turnSummary } from '../lib/turnText'
import { formatDistance, type UnitSystem } from '../lib/units'
import './chrome.css'

export interface NextTurnCardProps {
  /** The turn ahead, or null once every turn is behind the hiker. */
  turn: DayHikeTurn | null
  /** Miles to it. Read only when `turn` is not null. */
  milesAway: number
  /** The trail under the hiker's feet, from lib/dayHikeFollow.ts's leg. */
  onTrail: string | null
  onTrailBlaze: string | null
  /** Miles of route still ahead - what the card says instead of a turn once
   *  there are none left. */
  toGoMi: number
  units?: UnitSystem
  onOpenTurn: () => void
  onStopFollowing: () => void
}

export function NextTurnCard({
  turn,
  milesAway,
  onTrail,
  onTrailBlaze,
  toGoMi,
  units = 'imperial',
  onOpenTurn,
  onStopFollowing,
}: NextTurnCardProps) {
  const blaze = blazeLabel(onTrailBlaze)
  const nowOn = onTrail === null ? blaze : `${onTrail} · ${blaze.toLowerCase()}`

  return (
    <div className="next-turn">
      {turn === null ? (
        /* The state most of a loop's last leg is in, and worth saying out
           loud rather than leaving the slot empty: on a network where a
           junction arrives every 1.2 miles, "no more turns" is what tells a
           hiker they can put the phone away. */
        <p className="next-turn__none">
          <strong>No more turns.</strong> Stay on this trail for the last{' '}
          {formatDistance(toGoMi, units)}.
        </p>
      ) : (
        <button type="button" className="next-turn__lead" onClick={onOpenTurn}>
          <span className="next-turn__distance">
            In {formatDistance(milesAway, units)}
          </span>
          <span className="next-turn__instruction">{turnSummary(turn.onto)}</span>
        </button>
      )}

      <div className="next-turn__foot">
        <span className="next-turn__on">On {nowOn}</span>
        {turn !== null && (
          <button type="button" className="next-turn__link" onClick={onOpenTurn}>
            This turn
          </button>
        )}
        {/* The way out, on the screen the hiker is actually looking at.
            Following is the app watching a fix against a route, and a mode
            you can only leave by finding the card you started it from is a
            mode that ends when the battery does. */}
        <button
          type="button"
          className="next-turn__link next-turn__link--stop"
          onClick={onStopFollowing}
        >
          Stop
        </button>
      </div>
    </div>
  )
}
