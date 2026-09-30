// "On your challenges" on a place card (#1780, frames #2 and #2c).
//
// One row per challenge item at this place - the item, whose list it is on
// and whose club set it, and Tag it - so where two clubs' lists meet at one
// place, each is credited to whoever set it. A place on a challenge the hiker
// has not joined gets one row offering to join it, and nothing is drawn or
// queued until they do.
//
// THE HAND TAG, AND WHY IT IS HERE. Principle 1 is "days, not clicks", and
// this is a tap - but it is a tap on the card of a place the hiker opened, the
// handoff's own answer to GPS gaps, and every tag records `hand` so the club
// can see which ones were. An item that tags itself from the day's walk reads
// "done" instead of offering a pill.

import { API_CONFIGURED } from '../lib/api'
import { CHALLENGE_WORDS } from '../lib/challengeWords'
import {
  isSealed,
  itemTitle,
  itemsAtPoi,
  type Challenge,
  type ChallengeItem,
} from '../lib/challenges'
import {
  isJoined,
  isItemDone,
  tagsFor,
  type ChallengeState,
} from '../lib/challengeProgress'
import { Diamond, DraftLabel, TagPill } from './ChallengeParts'

export interface PoiChallengesProps {
  /** Every POI id this card shows - the pin's own, and a site's parts. */
  poiIds: readonly string[]
  /** Every challenge on the phone, joined or not. */
  challenges: readonly Challenge[]
  state: ChallengeState
  today: string
  onTag: (challenge: Challenge, item: ChallengeItem, poi: string) => void
  onUntag: (challenge: Challenge, item: ChallengeItem) => void
  onJoin: (challengeId: string) => void
}

interface Row {
  challenge: Challenge
  item: ChallengeItem
  poi: string
}

export function PoiChallenges(props: PoiChallengesProps) {
  const { poiIds, challenges, state, today } = props
  const joinedRows: Row[] = []
  const offers: Challenge[] = []
  for (const challenge of challenges) {
    const rows: Row[] = []
    for (const poi of poiIds) {
      for (const item of itemsAtPoi(challenge, poi)) {
        if (!isSealed(item, today)) rows.push({ challenge, item, poi })
      }
    }
    if (rows.length === 0) continue
    if (isJoined(state, challenge.id)) joinedRows.push(...rows)
    else offers.push(challenge)
  }
  if (joinedRows.length === 0 && offers.length === 0) return null

  const joinedChallenges = [...new Set(joinedRows.map((row) => row.challenge))]
  const heading =
    joinedChallenges.length === 1
      ? `On the ${joinedChallenges[0].name}`
      : 'On your challenges'

  return (
    <section className="poi-card__section" aria-label="Challenges">
      {joinedRows.length > 0 && (
        <>
          <h3 className="poi-card__section-title">{heading}</h3>
          <ul className="challenge-rows">
            {joinedRows.map(({ challenge, item, poi }) => {
              const tags = tagsFor(state, challenge.id)
              const done =
                item.match.kind === 'places_all'
                  ? tags.some((tag) => tag.itemId === item.id && tag.poi === poi)
                  : isItemDone(item, challenge.id, tags)
              const fromWalk = tags.some(
                (tag) => tag.itemId === item.id && tag.how === 'gps',
              )
              const title = itemTitle(item, today) ?? ''
              return (
                <li key={`${challenge.id}/${item.id}/${poi}`} className="challenge-row">
                  <Diamond done={done} />
                  <span className="challenge-row__text">
                    <span className="challenge-row__title">{title}</span>
                    <span className="challenge-row__meta">
                      {challenge.name} · {challenge.orgShort}
                    </span>
                    <DraftLabel challenge={challenge} />
                  </span>
                  {done && fromWalk ? (
                    <span className="challenge-row__done">done</span>
                  ) : (
                    <TagPill
                      tagged={done}
                      label={`${done ? CHALLENGE_WORDS.done : CHALLENGE_WORDS.act}: ${title}`}
                      onPress={() =>
                        done
                          ? props.onUntag(challenge, item)
                          : props.onTag(challenge, item, poi)
                      }
                    />
                  )}
                </li>
              )
            })}
          </ul>
          <p className="challenges__note">
            {API_CONFIGURED
              ? 'Saved on this phone. With signal, OurHike counts it for the club - never your name.'
              : 'Saved on this phone. It waits here until OurHike’s server is running.'}
          </p>
        </>
      )}
      {offers.map((challenge) => (
        <div key={challenge.id} className="challenge-row">
          <Diamond done={false} />
          <span className="challenge-row__text">
            <span className="challenge-row__title">On the {challenge.name}</span>
            <span className="challenge-row__meta">{challenge.orgName}</span>
            <DraftLabel challenge={challenge} />
          </span>
          <button
            type="button"
            className="challenge-tag"
            aria-label={`Join ${challenge.name}`}
            onClick={() => props.onJoin(challenge.id)}
          >
            Join
          </button>
        </div>
      ))}
    </section>
  )
}
