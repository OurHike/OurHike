// "On your challenges" on a place card (#1780, frames 2 and 2c).
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
  isOpen,
  isSealed,
  itemTitle,
  itemsAtPoi,
  windowNow,
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
  /** `poi` is this card's place, so a Triple Crown peak un-tags alone. */
  onUntag: (challenge: Challenge, item: ChallengeItem, poi: string) => void
  onJoin: (challengeId: string) => void
  /** Opens the challenge's own page, so a hiker can read it before joining. */
  onOpen?: (challengeId: string) => void
  /** Tags leave the phone only for a signed-in account; the note says so. */
  signedIn?: boolean
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
              // Per place for a Triple Crown: another peak walked is no reason
              // to take away this one's hand-tag undo.
              const fromWalk = tags.some(
                (tag) =>
                  tag.itemId === item.id &&
                  tag.how === 'gps' &&
                  (item.match.kind !== 'places_all' || tag.poi === poi),
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
                  ) : !done && !isOpen(challenge, today) ? (
                    // Tags only count inside the window, so outside it the
                    // card says when it is rather than offering one -
                    // ChallengeDetail.tsx's rule, which this card had missed
                    // (second Challenges review, 2026-10-01). A tag already
                    // made keeps its pill, so it can still be taken back.
                    <span className="challenge-row__done">
                      {windowNow(challenge, today)}
                    </span>
                  ) : (
                    <TagPill
                      tagged={done}
                      label={`${done ? CHALLENGE_WORDS.done : CHALLENGE_WORDS.act}: ${title}`}
                      onPress={() =>
                        done
                          ? props.onUntag(challenge, item, poi)
                          : props.onTag(challenge, item, poi)
                      }
                    />
                  )}
                </li>
              )
            })}
          </ul>
          <p className="challenges__note">
            {!API_CONFIGURED
              ? 'Saved on this phone. It waits here until OurHike’s server is running.'
              : props.signedIn === false
                ? 'Saved on this phone. Once you sign in and have signal, OurHike counts it for the club - never your name.'
                : 'Saved on this phone. With signal, OurHike counts it for the club - never your name.'}
          </p>
        </>
      )}
      {offers.length > 0 && joinedRows.length === 0 && (
        <h3 className="poi-card__section-title">On a club’s challenge</h3>
      )}
      {offers.map((challenge) => (
        <div key={challenge.id} className="challenge-row">
          <Diamond done={false} />
          <span className="challenge-row__text">
            {props.onOpen !== undefined ? (
              // Read it before joining it: the name opens the challenge.
              <button
                type="button"
                className="challenge-link challenge-row__title"
                onClick={() => props.onOpen?.(challenge.id)}
              >
                On the {challenge.name}
              </button>
            ) : (
              <span className="challenge-row__title">On the {challenge.name}</span>
            )}
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
