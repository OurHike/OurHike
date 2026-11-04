// The season, at the bottom of Today (#1964, features/CHALLENGES_BLAZE_CARD.md
// slice 4; the frame is features/design/blaze-card/Home.dc.html): one strip
// per joined challenge with a finish line, ambient rather than a target at
// the top of the day. The maintainer's rule (2026-11-03): the season lives
// at the bottom of Today, never the top; top of Today is today's business,
// the walk prompt.
//
// WHAT IT SAYS: the mini card (BlazeCard at 8 px, decoration), how many
// blazes, the states they landed in and how many at home, and the club's
// finish line in the club's words. WHAT IT NEVER SAYS: how many are missing,
// days left, anyone else (features/VOLUNTEERING.md §5). It is one button
// that opens the challenge.
//
// DEFERRED (screens/deferred.ts), with the card and the icon set behind it:
// Today is the first frame and main sits a few hundred bytes under the
// launch budget (check-build-output, measured 2026-11-04: 246,044 of
// 246,784), so the strip loads after the first paint like FieldNoteSection.

import { CHALLENGE_WORDS } from '../lib/challengeWords'
import { trailLabel } from '../lib/challengeText'
import type { Challenge } from '../lib/challenges'
import { tagsFor, type ChallengeState } from '../lib/challengeProgress'
import { seasonSummary, seasonWord } from '../lib/seasonStrip'
import { BlazeCard } from './BlazeCard'
import { DraftLabel } from './ChallengeParts'
import '../screens/challenges.css'

export interface ChallengeSeasonStripProps {
  challenge: Challenge
  state: ChallengeState
  today: string
  onOpen: () => void
}

export function ChallengeSeasonStrip({
  challenge,
  state,
  today,
  onOpen,
}: ChallengeSeasonStripProps) {
  const tags = tagsFor(state, challenge.id)
  const { earned, states, atHome } = seasonSummary(challenge, tags)
  const where = [...states, ...(atHome > 0 ? [`${atHome} at home`] : [])].join(' · ')
  const finish =
    challenge.finish === null
      ? null
      : challenge.reward?.kind === 'drawing'
        ? `${challenge.finish.count} enters the drawing`
        : `${challenge.finish.count} ${challenge.finish.label ?? ''}`.trim()
  return (
    <section className="season" aria-labelledby={`season-${challenge.id}`}>
      <p className="challenges__eyebrow" id={`season-${challenge.id}`}>
        Your {seasonWord(challenge.window)} on the {trailLabel(challenge.trail)}
      </p>
      <button type="button" className="season__strip" onClick={onOpen}>
        <span className="season__card">
          <BlazeCard challenge={challenge} tags={tags} today={today} size="mini" />
        </span>
        <span className="season__text">
          <span className="season__count">
            <strong>{earned}</strong>{' '}
            {earned === 1 ? CHALLENGE_WORDS.noun : CHALLENGE_WORDS.nounPlural}
          </span>
          {where !== '' && <span className="season__where">{where}</span>}
          <span className="season__meta">
            {challenge.name} · {challenge.orgShort}
            {finish !== null ? ` · ${finish}` : ''}
          </span>
          <DraftLabel challenge={challenge} />
        </span>
        <span className="season__chevron" aria-hidden="true">
          ›
        </span>
      </button>
    </section>
  )
}
