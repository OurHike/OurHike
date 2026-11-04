// "Where your trail karma is" (#1965, frame features/design/blaze-card/
// Line.dc.html) - the challenge's second view, beside the card: where each
// earned item happened, as a list first, the map once anything is on the
// trail, and the fourteen states as a strip.
//
// THE LIST FIRST. Every earned item is a row under the state it landed in,
// south to north, with where and when; what was earned at home, or not on
// the trail, is a row of chips under "Not on the trail"; and the places still
// on the card are chips under "Also on your card" - named, never counted
// (features/VOLUNTEERING.md §5 rule 2; the frame's "+6" is gone).
//
// THE MAP ONLY ONCE SOMETHING IS ON IT, and only when the phone holds one
// (lib/useChallengeMap.ts). Without either, nothing says a map is missing:
// the list is the whole answer.
//
// WHERE STAYS ON THIS PHONE, and the page says so: the places a hiker said
// are lib/wherePlace.ts's device-only record, and the poster is made here.

import { useMemo, useState } from 'react'
import { BlazeTile } from '../chrome/BlazeTile'
import { PosterShareSheet } from '../chrome/PosterShareSheet'
import { drawChallengeMap } from '../lib/challengeMapSvg'
import { isPlaceItem, type Challenge } from '../lib/challenges'
import { isItemDone, type ChallengeTag } from '../lib/challengeProgress'
import { formatDay, mileLabel, placeWords, titleOrSealed } from '../lib/challengeText'
import { CHALLENGE_WORDS } from '../lib/challengeWords'
import { mapPins, stripMarks } from '../lib/challengePoster'
import { earnedPlaces, seasonWord, type EarnedPlace } from '../lib/seasonStrip'
import { drawStateStrip, walkedStates } from '../lib/stateStripSvg'
import { stateLookup, useChallengeMap } from '../lib/useChallengeMap'
import type { UnitSystem } from '../lib/units'
import type { MileRange } from '../lib/walkedMiles'
import { stateName, TRAIL_STATES, type TrailStateCode } from '../lib/wherePlace'
import './challenges.css'

export interface ChallengeWhereProps {
  challenge: Challenge
  tags: readonly ChallengeTag[]
  today: string
  /** All-time walked miles (lib/walkedMiles.ts), lit on the map and strip. */
  walked: readonly MileRange[]
  units: UnitSystem
}

function whereLine(place: EarnedPlace): string {
  const { item, tag } = place
  if (isPlaceItem(item)) {
    const parts = [
      place.placeName ?? '',
      place.mile === null ? '' : mileLabel(place.mile),
    ]
    if (item.match.offTrail) parts.push('off the trail')
    else if (tag.how === 'gps') parts.push('from your walk')
    return parts.filter(Boolean).join(' · ')
  }
  return tag.place === undefined ? 'at home' : placeWords(tag.place)
}

export function ChallengeWhere({
  challenge,
  tags,
  today,
  walked,
  units,
}: ChallengeWhereProps) {
  const map = useChallengeMap()
  const stateOf = useMemo(() => stateLookup(map), [map])
  const [sharing, setSharing] = useState(false)
  const places = useMemo(
    () => earnedPlaces(challenge, tags, stateOf),
    [challenge, tags, stateOf],
  )
  const onTrail = places.filter((place) => place.onTrail)
  const notOnTrail = places.filter((place) => !place.onTrail)
  const byState = TRAIL_STATES.map(({ code }) => ({
    code,
    places: onTrail.filter((place) => place.state === code),
  })).filter((group) => group.places.length > 0)
  const unplaced = onTrail.filter((place) => place.state === null)
  const stillOnCard = challenge.items.filter(
    (item) => isPlaceItem(item) && !isItemDone(item, challenge.id, tags),
  )
  const pins = useMemo(
    () => mapPins({ challenge, tags, stateOf }),
    [challenge, tags, stateOf],
  )
  const mapSvg = useMemo(
    () =>
      map !== null && pins.some((pin) => pin.earned)
        ? drawChallengeMap(map, {
            width: 358,
            height: 400,
            units,
            title: `Map of the trail with your ${CHALLENGE_WORDS.noun} marked along it as filled diamonds, places still on your card as hollow ones, and the stretches you walked in yellow`,
            pins,
            walked,
          })
        : null,
    [map, units, walked, pins],
  )
  const stripSvg = drawStateStrip(stripMarks({ challenge, tags, stateOf }), {
    width: 358,
    columnHeight: 64,
    walkedStates: walkedStates(walked, stateOf),
    termini: true,
    title: `The fourteen trail states, south to north, with a gold mark for ${CHALLENGE_WORDS.noun} ${CHALLENGE_WORDS.past} in each`,
  })
  const summary =
    places.length === 0
      ? `Nothing ${CHALLENGE_WORDS.past} yet. Where it happens shows here, and stays on this phone.`
      : `${onTrail.length} ${CHALLENGE_WORDS.past} on the trail, ${notOnTrail.length} at home. Where stays on this phone.`

  return (
    <section className="challenge-where" aria-labelledby="where-title">
      <p className="challenges__eyebrow">
        {challenge.name} · {challenge.orgShort}
      </p>
      <h1 className="challenges__title" id="where-title">
        Where your {CHALLENGE_WORDS.noun} is
      </h1>
      <p className="challenge-where__summary">{summary}</p>

      {mapSvg !== null && (
        <div
          className="challenge-where__map"
          dangerouslySetInnerHTML={{ __html: mapSvg }}
        />
      )}
      <div className="challenge-where__strip">
        <p className="challenges__eyebrow">Where it happened</p>
        <div dangerouslySetInnerHTML={{ __html: stripSvg }} />
      </div>

      {byState.map(({ code, places: here }) => (
        <WhereGroup
          key={code}
          title={stateName(code)}
          places={here}
          challenge={challenge}
          today={today}
        />
      ))}
      {unplaced.length > 0 && (
        <WhereGroup
          title="On the trail"
          places={unplaced}
          challenge={challenge}
          today={today}
        />
      )}
      {notOnTrail.length > 0 && (
        <div className="challenge-where__group">
          <h2 className="challenge-where__heading">Not on the trail</h2>
          <ul className="challenge-where__chips">
            {notOnTrail.map((place) => (
              <li
                key={place.item.id}
                className="challenge-where__chip challenge-where__chip--earned"
              >
                {titleOrSealed(place.item, challenge, today)} · {whereLine(place)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {stillOnCard.length > 0 && (
        <div className="challenge-where__group">
          <h2 className="challenge-where__heading">Also on your card</h2>
          <ul className="challenge-where__chips">
            {stillOnCard.map((item) => {
              const place = isPlaceItem(item) ? item.match.places[0] : null
              const state: TrailStateCode | null =
                place === null ? null : stateOf(place.mile)
              return (
                <li key={item.id} className="challenge-where__chip">
                  {place?.name ?? titleOrSealed(item, challenge, today)}
                  {state !== null ? ` · ${state}` : ''}
                </li>
              )
            })}
          </ul>
        </div>
      )}

      <button type="button" className="challenge-button" onClick={() => setSharing(true)}>
        Share your {seasonWord(challenge.window)}
      </button>
      {sharing && (
        <PosterShareSheet
          challenge={challenge}
          tags={tags}
          today={today}
          stateOf={stateOf}
          walked={walked}
          units={units}
          map={map}
          onClose={() => setSharing(false)}
        />
      )}
    </section>
  )
}

function WhereGroup({
  title,
  places,
  challenge,
  today,
}: {
  title: string
  places: readonly EarnedPlace[]
  challenge: Challenge
  today: string
}) {
  return (
    <div className="challenge-where__group">
      <h2 className="challenge-where__heading">{title}</h2>
      <ul className="challenge-where__rows">
        {places.map((place) => (
          <li key={place.item.id} className="challenge-where__row">
            <BlazeTile icon={place.item.icon} done sealed={false} />
            <span className="challenge-where__text">
              <span className="challenge-where__title">
                {titleOrSealed(place.item, challenge, today)}
              </span>
              <span className="challenge-where__line">{whereLine(place)}</span>
            </span>
            <span className="challenge-where__date">{formatDay(place.tag.at)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
