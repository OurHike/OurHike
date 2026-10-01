// "From today's walk" - the one question a challenge asks, at camp (#1780,
// frame #3, design principle 3).
//
// WHAT IT NEVER SAYS. It lists what the day's walk passed and nothing else:
// no item that was not passed, no count of what was missed, no "you haven't"
// (features/VOLUNTEERING.md §5 rule 2). The rows come from
// lib/challengeProgress.matchDay, which never computes a missed item at all,
// so there is nothing here that could leak one. ChallengeCampCard.test.tsx
// holds the words out.
//
// ONCE A DAY. "Tag all" and "Not tonight" both answer today's card and it
// does not come back until tomorrow; "Not tonight" leaves every row taggable
// from the challenge's own page.

import { CHALLENGE_WORDS } from '../lib/challengeWords'
import type { DayCandidate } from '../lib/challengeProgress'
import { itemTitle } from '../lib/challenges'
import { mileLabel } from '../lib/challengeText'
import { Diamond, DraftLabel } from './ChallengeParts'

export interface ChallengeCampCardProps {
  /** What today's walk passed and the hiker has not tagged. */
  candidates: readonly DayCandidate[]
  today: string
  onTagAll: () => void
  onNotTonight: () => void
}

export function ChallengeCampCard({
  candidates,
  today,
  onTagAll,
  onNotTonight,
}: ChallengeCampCardProps) {
  if (candidates.length === 0) return null
  const ask = `${CHALLENGE_WORDS.noun.charAt(0).toUpperCase()}${CHALLENGE_WORDS.noun.slice(1)} them?`
  return (
    <section className="challenge-camp" aria-labelledby="challenge-camp-ask">
      <p className="challenges__eyebrow">From today’s walk</p>
      {/* A heading, so a screen reader's list of Today's headings finds it. */}
      <h2 className="challenge-camp__ask" id="challenge-camp-ask">
        You passed places on your challenges. {ask}
      </h2>
      <ul className="challenge-rows">
        {candidates.map(({ challenge, item, place }) => (
          <li key={`${challenge.id}/${item.id}/${place.poi}`} className="challenge-row">
            <Diamond done={false} />
            <span className="challenge-row__text">
              <span className="challenge-row__title">
                {item.match.kind === 'poi_type' || item.match.kind === 'places_all'
                  ? place.name
                  : (itemTitle(item, today) ?? place.name)}
              </span>
              <span className="challenge-row__meta">
                {item.match.kind === 'poi_type'
                  ? `${itemTitle(item, today) ?? ''} · `
                  : ''}
                {challenge.name}
              </span>
              <DraftLabel challenge={challenge} />
            </span>
            <span className="challenge-row__trailing">{mileLabel(place.mile)}</span>
          </li>
        ))}
      </ul>
      <div className="challenge-actions">
        <button
          type="button"
          className="challenge-button challenge-camp__all"
          onClick={onTagAll}
        >
          {CHALLENGE_WORDS.actAll}
        </button>
        <button
          type="button"
          className="challenge-button challenge-camp__later"
          onClick={onNotTonight}
        >
          Not tonight
        </button>
      </div>
    </section>
  )
}
