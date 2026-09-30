// Browse challenges (#1780, frame #5a, handoff revision 5).
//
// Opens on the trail the hiker chose and, when they have a plan, on what
// touches it: "On your plan" first, with how many of a challenge's places the
// plan passes, then "Elsewhere on <trail>" by distance from the plan. Three
// filters - Trail, Club, Open now - offer only trails and clubs that have a
// published challenge. Works offline: the list came with the data refresh.
//
// NO POPULARITY SORT AND NO HIKER COUNTS. The two orderings are the hiker's
// own plan and the map. Nothing here says how many people joined anything.

import { useMemo, useState } from 'react'
import { windowLine, type Challenge } from '../lib/challenges'
import {
  browse,
  isJoined,
  type ChallengeState,
  type PlanDayRange,
} from '../lib/challengeProgress'
import { formatDistance, type UnitSystem } from '../lib/units'
import { DraftLabel, OrgMark } from '../chrome/ChallengeParts'
import { trailLabel } from '../lib/challengeText'

export interface ChallengeBrowseProps {
  challenges: readonly Challenge[]
  state: ChallengeState
  /** The trail the map is on - the Trail filter's starting value. */
  chosenTrail: string | null
  /** The planned route by day, or empty with no plan. */
  days: readonly PlanDayRange[]
  /** "Pearisburg → Daleville", for the first group's heading. */
  planName: string | null
  today: string
  units: UnitSystem
  onOpen: (challengeId: string) => void
  onJoin: (challengeId: string) => void
}

export function ChallengeBrowse(props: ChallengeBrowseProps) {
  const { challenges, state, days, today } = props
  const trails = useMemo(
    () => [...new Set(challenges.map((challenge) => challenge.trail))],
    [challenges],
  )
  const clubs = useMemo(() => {
    const seen = new Map<string, string>()
    for (const challenge of challenges) seen.set(challenge.org, challenge.orgName)
    return [...seen.entries()]
  }, [challenges])
  const [trail, setTrail] = useState<string | null>(() =>
    props.chosenTrail !== null && trails.includes(props.chosenTrail)
      ? props.chosenTrail
      : null,
  )
  const [org, setOrg] = useState<string | null>(null)
  const [openNow, setOpenNow] = useState(false)

  const groups = browse({ challenges, filters: { trail, org, openNow }, days, today })
  const shownCount = groups.onPlan.length + groups.elsewhere.length

  return (
    <section className="challenges" aria-labelledby="browse-title">
      <h1 className="challenges__title" id="browse-title">
        Browse challenges
      </h1>
      <div className="challenge-filter">
        <label>
          <span className="visually-hidden">Trail</span>
          <select
            value={trail ?? ''}
            onChange={(event) =>
              setTrail(event.target.value === '' ? null : event.target.value)
            }
          >
            <option value="">Trail: any</option>
            {trails.map((id) => (
              <option key={id} value={id}>
                Trail: {trailLabel(id)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="visually-hidden">Club</span>
          <select
            value={org ?? ''}
            onChange={(event) =>
              setOrg(event.target.value === '' ? null : event.target.value)
            }
          >
            <option value="">Club: any</option>
            {clubs.map(([key, name]) => (
              <option key={key} value={key}>
                Club: {name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="challenge-pill"
          aria-pressed={openNow}
          onClick={() => setOpenNow(!openNow)}
        >
          Open now
        </button>
      </div>

      {challenges.length === 0 && (
        <p className="challenges__empty">
          No club has published a challenge yet. They arrive with the data refresh, so
          this list works with no signal once one has.
        </p>
      )}

      {groups.onPlan.length > 0 && (
        <>
          <h2 className="challenge-group">
            On your plan{props.planName !== null ? ` · ${props.planName}` : ''}
          </h2>
          {groups.onPlan.map(({ challenge, placesOnPlan }) => (
            <Offer
              key={challenge.id}
              challenge={challenge}
              joined={isJoined(state, challenge.id)}
              line={`${placesOnPlan} ${placesOnPlan === 1 ? 'place' : 'places'} on your plan`}
              onOpen={() => props.onOpen(challenge.id)}
              onJoin={() => props.onJoin(challenge.id)}
            />
          ))}
        </>
      )}

      {groups.elsewhere.length > 0 && (
        <>
          <h2 className="challenge-group">
            {trail !== null ? `Elsewhere on the ${trailLabel(trail)}` : 'Elsewhere'}
          </h2>
          {groups.elsewhere.map(({ challenge, milesFromPlan }) => (
            <Offer
              key={challenge.id}
              challenge={challenge}
              joined={isJoined(state, challenge.id)}
              line={
                milesFromPlan !== null
                  ? `${formatDistance(milesFromPlan, props.units)} from your plan`
                  : null
              }
              onOpen={() => props.onOpen(challenge.id)}
              onJoin={() => props.onJoin(challenge.id)}
            />
          ))}
        </>
      )}

      {trail !== null && (
        <p className="challenges__note">
          {shownCount} on the {trailLabel(trail)}
          {groups.hiddenByTrail > 0 && (
            <>
              {' · '}
              <button
                type="button"
                className="challenge-link"
                onClick={() => setTrail(null)}
              >
                clear trail filter
              </button>{' '}
              to see {groups.hiddenByTrail} more
            </>
          )}
        </p>
      )}
    </section>
  )
}

function Offer({
  challenge,
  joined,
  line,
  onOpen,
  onJoin,
}: {
  challenge: Challenge
  joined: boolean
  line: string | null
  onOpen: () => void
  onJoin: () => void
}) {
  return (
    <div className="challenge-offer">
      <button type="button" className="challenge-offer__open" onClick={onOpen}>
        <OrgMark challenge={challenge} />
        <span className="challenge-offer__text">
          <span className="challenge-offer__name">{challenge.name}</span>
          <span className="challenge-offer__meta">
            {challenge.orgName} · {windowLine(challenge)}
          </span>
          <DraftLabel challenge={challenge} />
          {line !== null && <span className="challenge-offer__plan">{line}</span>}
        </span>
      </button>
      {joined ? (
        <span className="challenge-offer__joined">Joined</span>
      ) : (
        <button
          type="button"
          className="challenge-tag"
          aria-label={`Join ${challenge.name}`}
          onClick={onJoin}
        >
          Join
        </button>
      )}
    </div>
  )
}
