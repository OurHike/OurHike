// The junction (#1041, frame `D10`).
//
// The one moment a day hike has and a thru-hike essentially does not: three
// or four marked trails meeting, and only one of them is yours. So this card
// names ALL of them and says what each one isn't - a hiker checks the app
// against the blaze in front of them, not the other way round, and a card
// that named only the arm to take would be asking to be obeyed by somebody
// who cannot see whether it is right.
//
// EVERY ARM, NEVER COLLAPSED. The finished-hike card's ways-off rows fold a
// trail that CROSSES a junction onto one row, because there one trail is one
// way off. Here they must stay apart: to somebody standing at the crossing
// those are two different directions wearing the same name, which is exactly
// the confusion this card exists to settle.
//
// WHAT IT DOES NOT SAY. Frame `D10`'s "The next blaze is about 80 ft along,
// on the left" is not printed - see lib/turnText.ts for why, and for the rule
// of thumb that replaces it. And nothing here moves the camera: the map holds
// the whole day at one scale and the junction arrives as the diagram beside
// this text (chrome/JunctionDiagram.tsx), which is that frame's own rule.

import { AT_JUNCTION_MILES, type DayHikeTurn } from '../lib/dayHikeTurns'
import { JunctionDiagram } from './JunctionDiagram'
import {
  armBlaze,
  blazeCheckLine,
  cameFromLine,
  otherArmLine,
  turnHeading,
} from '../lib/turnText'
import { formatDistance, type UnitSystem } from '../lib/units'
import './chrome.css'

export interface TurnCardProps {
  turn: DayHikeTurn
  /** Miles still to walk to reach it, from lib/dayHikeTurns.ts's nextTurn.
   *  Null when the hiker has no fix, which is a real state on this screen:
   *  the junction can still be read, only the distance to it cannot. */
  milesAway: number | null
  units?: UnitSystem
  onClose: () => void
}

export function TurnCard({
  turn,
  milesAway,
  units = 'imperial',
  onClose,
}: TurnCardProps) {
  return (
    <section className="turn-card" aria-label="The next junction">
      <div className="turn-card__head">
        {/* "In 0.0 mi" is what a distance reads as once somebody is standing
            at the fork, and it is the one number on this card that says
            nothing. The header is already saying "at a junction" at exactly
            this threshold, so the two agree. */}
        <p className="turn-card__eyebrow">
          {milesAway === null
            ? 'Ahead on your route'
            : milesAway <= AT_JUNCTION_MILES
              ? 'At the junction'
              : `In ${formatDistance(milesAway, units)}`}
        </p>
        <button type="button" className="turn-card__close" onClick={onClose}>
          <span className="visually-hidden">Close the junction</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <div className="turn-card__lead">
        <div className="turn-card__instruction">
          <h2 className="turn-card__heading">{turnHeading(turn.onto)}</h2>
          <p className="turn-card__blaze">{armBlaze(turn.onto)}</p>
        </div>
        {/* Null whenever any arm's bearing is missing - see the diagram's own
            header for why a junction drawn with an arm left out is worse than
            no junction drawn at all. */}
        <JunctionDiagram turn={turn} />
      </div>

      <ul className="turn-card__arms">
        {turn.others.map((arm, at) => (
          <li key={`other-${at}`} className="turn-card__arm">
            {otherArmLine(arm)}
          </li>
        ))}
        <li className="turn-card__arm turn-card__arm--behind">
          {cameFromLine(turn.from)}
        </li>
      </ul>

      <p className="turn-card__check">{blazeCheckLine(turn.onto)}</p>
    </section>
  )
}
