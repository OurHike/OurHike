// A plan's challenge places (#1780, frames #6 and #6b), under Plan's day list.
//
// JOINED: "Challenge places on this route" - each place on the route with
// the day it falls on and its mile. SUGGESTED: when the hiker has joined no
// challenge touching the route, the one best match, dashed, with Join and
// Hide (handoff revision 6). Suggested is not joined - no pins, no camp card,
// nothing queued until Join - and Hide is remembered for this hike.
//
// NEITHER CHANGES THE PLAN. The route, the mileage and every day's target are
// read here and never written: a challenge is something to notice on a walk
// already planned, never a reason the plan moved. Plan.test.tsx's standing
// negative assertions (no behind, no ahead of, no score) are extended over it.

import type { Challenge } from '../lib/challenges'
import { itemTitle } from '../lib/challenges'
import {
  isItemDone,
  tagsFor,
  type ChallengeState,
  type PlanRow,
} from '../lib/challengeProgress'
import { mileLabel } from '../lib/challengeText'
import { Diamond, DraftLabel, OrgMark } from './ChallengeParts'

/** How many rows a suggestion shows before "+N more" - the handoff's three. */
const SUGGESTION_ROWS = 3

export interface PlanChallengesProps {
  /** Places of joined challenges on this route. */
  rows: readonly PlanRow[]
  state: ChallengeState
  /** The one suggestion, when no joined challenge touches the route. */
  suggestion: { challenge: Challenge; rows: readonly PlanRow[] } | null
  today: string
  onJoin: (challengeId: string) => void
  onHide: (challengeId: string) => void
  onOpen: (challengeId: string) => void
}

function rowKey(row: PlanRow): string {
  return `${row.challenge.id}/${row.item.id}/${row.place.poi}`
}

/** Whether a row's place is tagged - per place, for a `places_all` item. */
function rowDone(row: PlanRow, state: ChallengeState): boolean {
  const tags = tagsFor(state, row.challenge.id)
  return row.item.match.kind === 'places_all'
    ? tags.some((tag) => tag.itemId === row.item.id && tag.poi === row.place.poi)
    : isItemDone(row.item, row.challenge.id, tags)
}

function dayLabel(dayNumber: number | null): string {
  return dayNumber === null ? 'Zero' : `Day ${dayNumber}`
}

export function PlanChallenges(props: PlanChallengesProps) {
  const { rows, suggestion, today } = props
  if (rows.length > 0) {
    const allOnRoute = [...new Set(rows.map((row) => row.item))].filter(
      (item) =>
        item.match.kind === 'places_all' &&
        item.match.places.every((place) =>
          rows.some((row) => row.item === item && row.place.poi === place.poi),
        ),
    )
    return (
      <section className="challenge-plan" aria-labelledby="plan-challenges-title">
        <div className="challenge-plan__head">
          <h2 className="challenge-row__title" id="plan-challenges-title">
            Challenge places on this route
          </h2>
          <span className="challenge-row__meta">{rows.length}</span>
        </div>
        <ul className="challenge-plan__rows">
          {rows.map((row) => (
            <li key={rowKey(row)} className="challenge-plan__row">
              <span className="challenge-plan__day">{dayLabel(row.dayNumber)}</span>
              <Diamond done={rowDone(row, props.state)} />
              <button
                type="button"
                className="challenge-link"
                onClick={() => props.onOpen(row.challenge.id)}
              >
                {row.item.match.kind === 'places_all'
                  ? row.place.name
                  : (itemTitle(row.item, today) ?? row.place.name)}
              </button>
              <span className="challenge-plan__mile">{mileLabel(row.place.mile)}</span>
            </li>
          ))}
        </ul>
        {allOnRoute.map((item) => (
          <p key={item.id} className="challenge-plan__note">
            Every place of “{itemTitle(item, today)}” is on this route.
          </p>
        ))}
      </section>
    )
  }

  if (suggestion === null) return null
  const { challenge } = suggestion
  const shown = suggestion.rows.slice(0, SUGGESTION_ROWS)
  const more = suggestion.rows.length - shown.length
  return (
    <section
      className="challenge-plan challenge-plan--suggested"
      aria-labelledby="plan-suggestion-title"
    >
      <div className="challenge-plan__head">
        <OrgMark challenge={challenge} />
        <span className="challenge-row__text">
          <span className="challenges__eyebrow">Challenge on your route</span>
          {/* Read it before joining it: the name opens the challenge. */}
          <button
            type="button"
            className="challenge-link challenge-row__title"
            id="plan-suggestion-title"
            onClick={() => props.onOpen(challenge.id)}
          >
            {challenge.name}
          </button>
          <DraftLabel challenge={challenge} />
        </span>
      </div>
      <ul className="challenge-plan__rows">
        {shown.map((row) => (
          <li key={rowKey(row)} className="challenge-plan__row">
            <span className="challenge-plan__day">{dayLabel(row.dayNumber)}</span>
            <Diamond done={false} />
            <span>
              {row.item.match.kind === 'places_all'
                ? row.place.name
                : (itemTitle(row.item, today) ?? row.place.name)}
            </span>
          </li>
        ))}
      </ul>
      {more > 0 && (
        <button
          type="button"
          className="challenge-link challenges__note"
          onClick={() => props.onOpen(challenge.id)}
        >
          +{more} more on this hike
        </button>
      )}
      <div className="challenge-actions">
        <button
          type="button"
          className="challenge-button"
          onClick={() => props.onJoin(challenge.id)}
        >
          Join
        </button>
        <button
          type="button"
          className="challenge-button challenge-button--ghost"
          onClick={() => props.onHide(challenge.id)}
        >
          Hide
        </button>
      </div>
    </section>
  )
}
