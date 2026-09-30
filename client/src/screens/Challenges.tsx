// More → Challenges: the challenges a hiker joined (#1780, frame #2b).
//
// One card per joined challenge, each drawn in its own unit - places tagged
// against a club's finish line, sections walked, or a row of diamonds for a
// record with no finish - and never a total across them, which would be the
// composite score features/VOLUNTEERING.md §5 rule 4 forbids.
//
// TWO DEPARTURES FROM THE MOCK, both toward the guardrail:
//   - The mock's ATC card carries "11 wk" - time left. A countdown is the
//     pressure §5 exists to prevent, so the card names the closing DATE in
//     its eyebrow and nothing counts down.
//   - The mock styles the ATC's card on the chrome as a special case. Here
//     any challenge with a finish line is drawn that way, and the ATC's is
//     one of them - design principle 5's "not a special case".

import { CHALLENGE_WORDS } from '../lib/challengeWords'
import { isPlaceItem, shortDate, type Challenge } from '../lib/challenges'
import {
  isItemDone,
  progress,
  tagsFor,
  type ChallengeState,
} from '../lib/challengeProgress'
import { Diamond, DraftLabel, FinishBar } from '../chrome/ChallengeParts'

export interface ChallengesProps {
  joined: readonly Challenge[]
  state: ChallengeState
  /** Challenges on the hiker's trails they have not joined - the footer's
   *  one number, which counts what is on offer and never anybody else. */
  onOffer: number
  onOpen: (challengeId: string) => void
  onBrowse: () => void
}

export function Challenges({
  joined,
  state,
  onOffer,
  onOpen,
  onBrowse,
}: ChallengesProps) {
  return (
    <section className="challenges" aria-labelledby="challenges-title">
      <p className="challenges__eyebrow">More · Challenges</p>
      <h1 className="challenges__title" id="challenges-title">
        {CHALLENGE_WORDS.yours}
      </h1>
      {joined.length === 0 ? (
        <p className="challenges__empty">
          A challenge is a club’s list of places on its own trails - walk there, and{' '}
          {CHALLENGE_WORDS.noun} them at camp. Join as many as you like.
        </p>
      ) : (
        joined.map((challenge) => (
          <ChallengeCard
            key={challenge.id}
            challenge={challenge}
            state={state}
            onOpen={() => onOpen(challenge.id)}
          />
        ))
      )}
      <button type="button" className="challenge-browse-row" onClick={onBrowse}>
        <span>
          {onOffer > 0
            ? `${onOffer} more on trails near you`
            : 'Challenges on your trails'}
        </span>
        <span className="challenge-browse-row__go">Browse ›</span>
      </button>
    </section>
  )
}

function ChallengeCard({
  challenge,
  state,
  onOpen,
}: {
  challenge: Challenge
  state: ChallengeState
  onOpen: () => void
}) {
  const { tagged, finish } = progress(challenge, state)
  const tags = tagsFor(state, challenge.id)
  const places = challenge.items.filter(isPlaceItem)
  const allSections = challenge.items.every(
    (item) => item.match.kind === 'section_walked',
  )
  const { closes } = challenge.window
  const eyebrow = `${challenge.orgShort} · ${closes !== null ? `until ${shortDate(closes)}` : 'no end date'}`
  return (
    <button
      type="button"
      className={
        finish !== null ? 'challenge-card challenge-card--finish' : 'challenge-card'
      }
      onClick={onOpen}
    >
      <span className="challenge-card__eyebrow">{eyebrow}</span>
      <span className="challenge-card__name">{challenge.name}</span>
      <DraftLabel challenge={challenge} />
      {finish !== null ? (
        <>
          <span className="challenge-card__line">
            <span>
              {tagged} of {finish}
              {challenge.finish?.label ? ` ${challenge.finish.label}` : ''}
            </span>
          </span>
          <FinishBar tagged={tagged} finish={finish} />
        </>
      ) : allSections ? (
        <span className="challenge-card__line">
          <span>
            {tagged} of {challenge.items.length} sections walked
          </span>
        </span>
      ) : (
        <>
          {places.length > 0 && (
            <span className="challenge-diamonds" aria-hidden="true">
              {places.map((item) => (
                <Diamond key={item.id} done={isItemDone(item, challenge.id, tags)} />
              ))}
            </span>
          )}
          <span className="challenge-card__line">
            <span>
              {tagged} {CHALLENGE_WORDS.past}
            </span>
          </span>
        </>
      )}
    </button>
  )
}
