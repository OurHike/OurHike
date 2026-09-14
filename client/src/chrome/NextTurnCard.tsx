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

import { useState } from 'react'

import type { DayHikeTurn } from '../lib/dayHikeTurns'
import { blazeLabel } from '../lib/blaze'
import { turnSummary } from '../lib/turnText'
import { formatDistance, type UnitSystem } from '../lib/units'
import { PoiRow } from './PoiRow'
import './chrome.css'

/** One thing still ahead on the route (#1373, frame 6b): a waypoint the
 *  walk passes, with the miles to it from where the hiker is. */
export interface AheadRow {
  key: string
  /** The waypoint's type - the map's own pin at row scale. */
  kind: string
  title: string
  milesAway: number
}

export interface NextTurnCardProps {
  /**
   * Whether this phone can say where the hiker is at all.
   *
   * False is an ordinary state and a frequent one: the first seconds of
   * following, and every time GPS drops under canopy. The card still renders,
   * because it carries the only way OUT of the mode - a hiker left in a mode
   * the header announces, with nothing on screen to leave it by, is the bug
   * this prop exists to have fixed (#1044 review).
   */
  positionKnown?: boolean
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
  /**
   * The hiker has walked off their download (#1373, frame 6a). The strip
   * still says it; this card says it again at its head, in the strip's own
   * words, because the card is the one thing on this screen a thumb is
   * already on and "you have walked off your download" is the one map
   * condition with something to do about it. The door is the download
   * sheet, and it is offered only where the shell has one.
   */
  outsideDownload?: boolean
  onTakeStretch?: () => void
  /**
   * What is still ahead on the route (frame 6b): the water it passes and
   * anything else the shell can place on it, each with the miles to it.
   * Undefined off-route and before a fix, where nothing is ahead of a
   * position nobody has.
   */
  ahead?: readonly AheadRow[]
  /** Miles walked so far - the figure the finish ask prints. */
  walkedMi?: number
  /**
   * The finish, asked and never assumed (frame 6c). Pressing "Finish here"
   * asks once, on this card; "Finish this walk" is the commit and "Still
   * going" is nothing at all. No arrival detector stands behind it: a
   * finish this app declared for a hiker at the wrong trailhead would be
   * crying wolf on the one record that says a walk was done.
   */
  onFinish?: () => void
}

export function NextTurnCard({
  positionKnown = true,
  turn,
  milesAway,
  onTrail,
  onTrailBlaze,
  toGoMi,
  units = 'imperial',
  onOpenTurn,
  onStopFollowing,
  outsideDownload = false,
  onTakeStretch,
  ahead,
  walkedMi,
  onFinish,
}: NextTurnCardProps) {
  const blaze = blazeLabel(onTrailBlaze)
  const nowOn = onTrail === null ? blaze : `${onTrail} · ${blaze.toLowerCase()}`
  // The ask replaces the card's body in the same frame - one surface
  // continuing, the convention every sheet on this map keeps.
  const [asking, setAsking] = useState(false)

  const coverage = outsideDownload ? (
    <div className="next-turn__coverage" role="note">
      <p className="next-turn__coverage-title">Outside what you downloaded</p>
      <p className="next-turn__coverage-body">
        The trail line and your position still work.
      </p>
      {onTakeStretch !== undefined && (
        <button type="button" className="next-turn__link" onClick={onTakeStretch}>
          Take this stretch
        </button>
      )}
    </div>
  ) : null

  if (asking && onFinish !== undefined) {
    return (
      <div className="next-turn" role="group" aria-label="Done for the day?">
        <p className="next-turn__ask-title">Done for the day?</p>
        <p className="next-turn__ask-figures">
          {walkedMi === undefined ? null : `${formatDistance(walkedMi, units)} walked`}
        </p>
        <p className="next-turn__ask-note">
          Nothing to tap if you&rsquo;d rather not — this asks again tomorrow morning and
          never closes the walk for you.
        </p>
        <div className="next-turn__ask-actions">
          <button
            type="button"
            className="next-turn__finish"
            onClick={() => {
              setAsking(false)
              onFinish()
            }}
          >
            Finish this walk
          </button>
          <button
            type="button"
            className="next-turn__link"
            onClick={() => setAsking(false)}
          >
            Still going
          </button>
        </div>
      </div>
    )
  }

  if (!positionKnown) {
    return (
      <div className="next-turn">
        {coverage}
        {/* No distances, no turn, no trail name. Everything this card
            normally says is a claim about where somebody is standing, and
            nothing here knows. What survives is the mode and the way out. */}
        <p className="next-turn__none">
          Waiting for GPS. Nothing here knows where you are yet, so no turn is being
          called.
        </p>
        <div className="next-turn__foot">
          <span className="next-turn__on">Following a day hike</span>
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

  return (
    <div className="next-turn">
      {coverage}
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

      {/* WHAT'S LEFT TODAY (frame 6b): the miles still ahead, the water the
          route passes before its end, and the finish - each with the miles
          to it from here, and no time to any of them, for the reason the
          turn above carries none. "Finish here instead" is the design's
          door onto the ask below; the same ask is a tap away whether a
          hiker is at the trailhead or a mile short of it. */}
      {ahead !== undefined && (
        <section className="next-turn__left" aria-label="What’s left today">
          <p className="next-turn__left-head">
            <span>What&rsquo;s left today</span>
            <span className="next-turn__left-figure">
              {formatDistance(toGoMi, units)}
            </span>
          </p>
          <ul className="next-turn__left-rows">
            {ahead.map((row) => (
              <li key={row.key}>
                <PoiRow
                  kind={row.kind}
                  title={row.title}
                  trailing={formatDistance(row.milesAway, units)}
                />
              </li>
            ))}
            <li>
              <PoiRow
                kind="finish"
                title="The finish"
                trailing={formatDistance(toGoMi, units)}
              />
            </li>
          </ul>
          {onFinish !== undefined && (
            <button
              type="button"
              className="next-turn__link"
              onClick={() => setAsking(true)}
            >
              Finish here instead<span aria-hidden="true"> ›</span>
            </button>
          )}
        </section>
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
