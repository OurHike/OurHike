// Your day hikes (#1008, storyboard frame D7) - the list that did not
// exist.
//
// Day hikes are saved and follow the account (#976), and until this screen
// the only way back to one was the shelf section on the Plan home - which
// shows the recent few and nothing else once the day home trims it. This is
// the day-hike counterpart to TripList.tsx: every saved hike, split by the
// only state that matters at 7am - **still to walk against already
// walked** - with the store's own cached figures, so the list never loads
// the routing graph to say "3.4 mi" (the rule PlanHome's rows established).
//
// TWO SORTS, THE SECOND ONLY WHEN IT CAN BE HONEST. "Recent" is the store's
// existing ordering. "Nearest me" sorts by straight-line distance from the
// GPS fix to each hike's saved start, so it exists only while a fix does -
// no fix, no chip, per the no-dead-controls rule every sheet here keeps.
//
// The walked shelf renders only when it holds something. Nothing in the
// client marks a hike walked yet (#982 builds that flow), so that section
// is usually absent - a header over an empty list is a shelf with a label
// and no answer on it (#805).

import { useState } from 'react'

import type { DayHike } from '../lib/dayHikes'
import { sortedByNearest, splitDayHikes } from '../lib/dayHikeShelf'
import { dayLongDateLabel } from '../lib/planDisplay'
import type { LonLat } from '../lib/trailGraph'
import { formatDistance, type UnitSystem } from '../lib/units'
import './plan.css'

export interface DayHikeListProps {
  dayHikes: readonly DayHike[]
  units: UnitSystem
  /** The GPS fix, or null - decides whether "nearest me" is offered. */
  at: LonLat | null
  onOpen: (id: string) => void
  onBack: () => void
  /** Start the builder, or null when the phone has no junction graph - the
   *  day home carries the sentence for that state, so this screen simply
   *  offers nothing rather than repeating it. */
  onNewDayHike: (() => void) | null
}

type ListSort = 'recent' | 'nearest'

export function DayHikeList({
  dayHikes,
  units,
  at,
  onOpen,
  onBack,
  onNewDayHike,
}: DayHikeListProps) {
  const [sort, setSort] = useState<ListSort>('recent')

  const shelf = splitDayHikes(dayHikes)
  const toWalk =
    sort === 'nearest' && at !== null ? sortedByNearest(shelf.toWalk, at) : shelf.toWalk

  return (
    <div className="day-hike-list">
      <header className="plan__head plan__head--day">
        <button type="button" className="plan__crumb" onClick={onBack}>
          <span className="plan__crumb-up">&lsaquo; Day hikes</span>
        </button>
        <h1 className="plan__title">
          Yours · {dayHikes.length === 1 ? '1 hike' : `${dayHikes.length} hikes`}
        </h1>
      </header>

      {/* The band stays OUT of this scroller. It bleeds to the screen edges
          through .plan's padding with negative margins, and a scroll
          container clips exactly that - which is what put a half-drawn band
          on this screen the first time the list was made to scroll. */}
      <div className="day-hike-list__scroll">
        {at !== null && shelf.toWalk.length > 1 && (
          // The group label WhatsLeft.tsx already gives the identical pattern:
          // without it these announce as two unrelated toggles rather than one
          // exclusive choice, and say nothing about what they order.
          <div className="day-hike-list__sorts" role="group" aria-label="Order these by">
            <button
              type="button"
              className="whats-left__sort"
              aria-pressed={sort === 'recent'}
              onClick={() => setSort('recent')}
            >
              recent
            </button>
            <button
              type="button"
              className="whats-left__sort"
              aria-pressed={sort === 'nearest'}
              onClick={() => setSort('nearest')}
            >
              nearest me
            </button>
          </div>
        )}

        {toWalk.length > 0 && (
          <section className="plan-home__section">
            <span className="plan-home__title">Ready to walk</span>
            {toWalk.map((hike) => (
              <button
                type="button"
                className="plan-home__row"
                key={hike.id}
                onClick={() => onOpen(hike.id)}
              >
                <span className="plan-home__row-name">{hike.name}</span>
                {/* Cached figures on purpose - see the header. Miles and legs
                  only: no walking time exists for network trails, and this
                  row must not invent one (the builder bar's own rule). */}
                <span className="plan-home__meta">
                  {formatDistance(hike.figures.miles, units)}
                  {hike.figures.legs.length > 0 &&
                    ` · ${hike.figures.legs.length} ${
                      hike.figures.legs.length === 1 ? 'leg' : 'legs'
                    }`}
                  {' · '}
                  {hike.date !== null ? dayLongDateLabel(hike.date) : 'no date yet'}
                </span>
              </button>
            ))}
          </section>
        )}

        {shelf.walked.length > 0 && (
          <section className="plan-home__section">
            <span className="plan-home__title">Walked</span>
            {shelf.walked.map((hike) => (
              <button
                type="button"
                className="plan-home__row day-hike-list__row--walked"
                key={hike.id}
                onClick={() => onOpen(hike.id)}
              >
                <span className="plan-home__row-name">{hike.name}</span>
                <span className="plan-home__meta">
                  {hike.date !== null ? dayLongDateLabel(hike.date) : 'no date'}
                </span>
              </button>
            ))}
          </section>
        )}

        {/* "Signed in" is not a hedge to be trimmed: day hikes ride the
          account exchange only while somebody has an account and sync is on
          (lib/useDayHikesSync.ts), and the app's default state is signed
          out. A flat "they follow your account" reads as backed up to the
          hiker most likely to lose them. */}
        {dayHikes.length === 0 && (
          <p className="day-hike-list__empty">
            Nothing saved yet. A day hike you build is kept on this phone — and, signed
            in, follows your account to the next one.
          </p>
        )}

        {dayHikes.length > 0 && (
          <p className="day-hike-list__note">
            All of these are on this phone. Signed in, they follow your account to the
            next one.
          </p>
        )}

        {onNewDayHike !== null && (
          <button type="button" className="plan__primary" onClick={onNewDayHike}>
            Plan a day hike
          </button>
        )}
      </div>
    </div>
  )
}
