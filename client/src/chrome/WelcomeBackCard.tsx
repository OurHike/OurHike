// Coming back to a long hike (#1317).
//
// DOING NOTHING CHANGES NOTHING, said on the screen and true in the code.
// This card offers two buttons and a sentence; neither button is a default,
// neither is pre-selected, and dismissing the card moves no date. A hiker who
// went quiet for eleven days has not asked the app to edit their plan, and a
// prompt that rolled one forward on their behalf would be doing exactly that.
//
// NEVER A COUNT OF WHAT THEY MISSED. The second card says what changed on the
// stretch ahead - closures raised, how much older the field notes are - and
// stops there. "You missed 14 reports" is a scold about being off the trail,
// which is where hikers are supposed to be when they are not on it.

import { shortDate } from '../lib/hikeText'
import '../screens/today.css'

export interface WelcomeBackCardProps {
  /** How many dated days are not yet walked - behind today included, since
   *  a hiker back from a pause has days dated in the past still on the plan
   *  - and the date they start from. Null
   *  when nothing is dated - and then there is nothing to offer moving, so
   *  the card says only the quiet line. */
  dated: { count: number; from: string } | null
  /** What changed on the stretch ahead while they were away. Empty when
   *  nothing did, or when this phone cannot say - and then the second card
   *  does not render at all rather than claiming "nothing happened". */
  changes: readonly string[]
  onMoveToToday: () => void
  onLeaveIt: () => void
  onSetWhereIAm: () => void
  onSeeOnMap: () => void
}

export function WelcomeBackCard({
  dated,
  changes,
  onMoveToToday,
  onLeaveIt,
  onSetWhereIAm,
  onSeeOnMap,
}: WelcomeBackCardProps) {
  return (
    <>
      <section className="today__card today__card--hike" aria-label="Welcome back">
        <p className="today__rule-label">Welcome back</p>
        {dated === null ? (
          <p className="today__hike-line">
            Nothing in this hike is dated, so there is nothing to move. Pick up wherever
            you are.
          </p>
        ) : (
          <>
            <p className="today__hike-title">
              {dated.count} {dated.count === 1 ? 'day is' : 'days are'} still dated from{' '}
              {shortDate(dated.from)}.
            </p>
            <p className="today__hike-line">
              Move them to start today, or leave the plan exactly as it is.
            </p>
            <div className="today__actions">
              <button type="button" className="plan__primary" onClick={onMoveToToday}>
                Move them to today
              </button>
              <button type="button" className="today__action" onClick={onLeaveIt}>
                Leave it
              </button>
            </div>
          </>
        )}
        <button type="button" className="today__quiet-line" onClick={onSetWhereIAm}>
          Got back on somewhere else? Set where you are and the days follow from there.
        </button>
      </section>

      {changes.length > 0 && (
        <section className="today__card" aria-label="While you were away">
          <p className="today__rule-label">While you were away</p>
          {changes.map((line) => (
            <p className="today__hike-line" key={line}>
              {line}
            </p>
          ))}
          <div className="today__actions">
            <button type="button" className="today__action" onClick={onSeeOnMap}>
              See it on the map
            </button>
          </div>
        </section>
      )}
    </>
  )
}
