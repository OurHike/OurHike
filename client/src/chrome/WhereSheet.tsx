// "Where did it happen?" (#1963, features/CHALLENGES_BLAZE_CARD.md slice 3;
// the frame is features/design/blaze-card/Where.dc.html): the second step
// of earning an item by hand, asked only when it can mean something
// (lib/wherePlace.ts asksWhere). Five answers, each a card:
//
//   Here · <place> - only with a fix inside the corridor; the snapped mile.
//   Somewhere I walked today - only on a day something was walked.
//   Pick a place - the phone's own waypoints, by name (lib/searchPoi.ts).
//   On the trail, somewhere - always, with a state; where the sheet opens
//     with no fix, for the hiker with no signal and no download.
//   Not on the trail - always.
//
// NO CHALLENGE SCREEN ASKS TO TURN LOCATION ON (the brief's "Second look"):
// with no fix the Here card is simply absent, and nothing here says why.
// WHERE STAYS ON THIS PHONE: the answer is kept beside the tag
// (lib/challengeProgress.ts) and the cargo does not change.

import { useEffect, useMemo, useRef, useState } from 'react'
import type { Challenge, ChallengeItem } from '../lib/challenges'
import { CHALLENGE_WORDS } from '../lib/challengeWords'
import { mileLabel, titleOrSealed } from '../lib/challengeText'
import { searchPois, type SearchablePoi } from '../lib/searchPoi'
import {
  TRAIL_STATES,
  type TagPlace,
  type TrailStateCode,
  type WhereOptions,
} from '../lib/wherePlace'
import '../screens/challenges.css'

export interface WhereSheetProps {
  challenge: Challenge
  item: ChallengeItem
  today: string
  options: WhereOptions
  /** The phone's own waypoints, for Pick a place; empty hides the card. */
  places: readonly SearchablePoi[]
  onChoose: (place: TagPlace) => void
  onBack: () => void
}

type Choice = 'here' | 'walked' | 'poi' | 'state' | 'off'

/** How many places the search lists; the box reaches the rest by name. */
const PLACE_LIMIT = 8

export function WhereSheet({
  challenge,
  item,
  today,
  options,
  places,
  onChoose,
  onBack,
}: WhereSheetProps) {
  const [choice, setChoice] = useState<Choice>(options.initial)
  const [state, setState] = useState<TrailStateCode | ''>('')
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<SearchablePoi | null>(null)
  const heading = useRef<HTMLHeadingElement | null>(null)
  useEffect(() => {
    heading.current?.focus()
  }, [])
  const found = useMemo(
    () => (choice === 'poi' ? searchPois(query, places, { limit: PLACE_LIMIT }) : []),
    [choice, query, places],
  )

  const chosen: TagPlace | null = (() => {
    switch (choice) {
      case 'here':
        return options.here === null ? null : { kind: 'here', mile: options.here.mile }
      case 'walked':
        return options.walked === null ? null : { kind: 'walked', ...options.walked }
      case 'poi':
        return picked === null
          ? null
          : { kind: 'poi', poi: picked.id, name: picked.name, mile: picked.mile ?? null }
      case 'state':
        return state === '' ? null : { kind: 'state', state }
      case 'off':
        return { kind: 'off' }
    }
  })()

  const card = (key: Choice, title: string, sub: string, body?: React.ReactNode) => (
    <div className="where-option">
      <button
        type="button"
        className="where-option__press"
        aria-pressed={choice === key}
        onClick={() => setChoice(key)}
      >
        <span className="where-option__title">{title}</span>
        <span className="where-option__sub">{sub}</span>
      </button>
      {choice === key && body}
    </div>
  )

  return (
    <div
      className="challenge-sheet where-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="where-heading"
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation()
          onBack()
        }
      }}
    >
      <header className="where-sheet__head">
        <div className="where-sheet__top">
          <button
            type="button"
            className="challenge-link where-sheet__back"
            onClick={onBack}
          >
            ‹ Back
          </button>
          <span className="challenges__eyebrow">
            Earning {CHALLENGE_WORDS.noun} · 2 of 2
          </span>
        </div>
        <h2
          className="where-sheet__heading"
          id="where-heading"
          ref={heading}
          tabIndex={-1}
        >
          Where did it happen?
        </h2>
        <p className="where-sheet__item">{titleOrSealed(item, challenge, today)}</p>
      </header>

      <div className="where-sheet__options">
        {options.here !== null &&
          card(
            'here',
            'Here',
            `${mileLabel(options.here.mile)} · your position right now`,
          )}
        {options.walked !== null &&
          card(
            'walked',
            'Somewhere I walked today',
            `${mileLabel(options.walked.fromMile)} – ${mileLabel(options.walked.toMile)}`,
          )}
        {places.length > 0 &&
          card(
            'poi',
            'Pick a place',
            picked === null
              ? 'any shelter, summit or town on the trail'
              : picked.mile === undefined
                ? picked.name
                : `${picked.name} · ${mileLabel(picked.mile)}`,
            <div className="where-option__body">
              <label className="challenge-field">
                <span className="challenges__eyebrow">Its name</span>
                <input
                  type="search"
                  value={query}
                  autoComplete="off"
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              {found.length > 0 && (
                <ul className="where-places" aria-label="Places">
                  {found.map((place) => (
                    <li key={place.id}>
                      <button
                        type="button"
                        className="where-places__row"
                        aria-pressed={picked?.id === place.id}
                        onClick={() => setPicked(place)}
                      >
                        <span>{place.name}</span>
                        {place.mile !== undefined && (
                          <span className="challenge-row__trailing">
                            {mileLabel(place.mile)}
                          </span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>,
          )}
        {card(
          'state',
          'On the trail, somewhere',
          'no signal, no download - just the state',
          <div className="where-option__body">
            <label className="challenge-field">
              <span className="challenges__eyebrow">Which state</span>
              <select
                value={state}
                onChange={(event) => setState(event.target.value as TrailStateCode | '')}
              >
                <option value="">Choose a state</option>
                {TRAIL_STATES.map((entry) => (
                  <option key={entry.code} value={entry.code}>
                    {entry.name}
                  </option>
                ))}
              </select>
            </label>
          </div>,
        )}
        {card('off', 'Not on the trail', 'at home, in town, on another trail')}
      </div>

      <p className="challenges__note where-sheet__note">
        Where stays on this phone. The {challenge.orgShort} gets the item and the day,
        never the place or a track.
      </p>
      <div className="challenge-actions where-sheet__actions">
        <button
          type="button"
          className="challenge-button"
          disabled={chosen === null}
          onClick={() => chosen !== null && onChoose(chosen)}
        >
          {choice === 'off' ? 'Earn it' : 'Earn it here'}
        </button>
      </div>
    </div>
  )
}
