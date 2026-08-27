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
// THREE SORTS, EACH ONLY WHEN IT CAN BE HONEST. "Recent" is the store's
// existing ordering. "Nearest me" sorts by straight-line distance from the
// GPS fix to each hike's saved start, so it exists only while a fix does -
// no fix, no chip, per the no-dead-controls rule every sheet here keeps.
// "Shortest first" is the storyboard's "fits my time", and it appears only
// once at least one hike carries a cached climb to price a walk from - which
// before 2026-08-27 was none of them, because `DayHikeFigures` held miles and
// legs and no ascent (features/HIKE_PLANNING.md recorded that as the thing
// blocking this sort and the ≈time below).
//
// WHY IT IS "SHORTEST FIRST" AND NOT "FITS MY TIME". The storyboard's phrase
// implies the app knows how long a hiker has, and it does not: there is no
// field for it, and asking would be a planner that keeps a schedule, which
// value #1 rules out. What the app can honestly offer is the list in order of
// how long each walk takes at this hiker's own pace, and let them stop reading
// when the numbers get too big.
//
// The walked shelf renders only when it holds something. Nothing in the
// client marks a hike walked yet (#982 builds that flow), so that section
// is usually absent - a header over an empty list is a shelf with a label
// and no answer on it (#805).

import { useState } from 'react'

import type { DayHike } from '../lib/dayHikes'
import {
  cachedEstimate,
  sortedByNearest,
  sortedByTime,
  splitDayHikes,
} from '../lib/dayHikeShelf'
import type { PaceProfile } from '../lib/pace'
import { dayLongDateLabel } from '../lib/planDisplay'
import type { LonLat } from '../lib/trailGraph'
import { formatDistance, type UnitSystem } from '../lib/units'
import './plan.css'

export interface DayHikeListProps {
  dayHikes: readonly DayHike[]
  units: UnitSystem
  /** The GPS fix, or null - decides whether "nearest me" is offered. */
  at: LonLat | null
  /** The hiker's own pace, so a row's time is the one the card would print
   *  rather than the standard rule's (#1040). */
  pace: PaceProfile
  onOpen: (id: string) => void
  onBack: () => void
  /** Start the builder, or null when the phone has no junction graph - the
   *  day home carries the sentence for that state, so this screen simply
   *  offers nothing rather than repeating it. */
  onNewDayHike: (() => void) | null
}

type ListSort = 'recent' | 'nearest' | 'shortest'

export function DayHikeList({
  dayHikes,
  units,
  at,
  pace,
  onOpen,
  onBack,
  onNewDayHike,
}: DayHikeListProps) {
  const [sort, setSort] = useState<ListSort>('recent')

  const shelf = splitDayHikes(dayHikes)
  // Offered only when a walk here can actually be priced. A hike saved before
  // the climb was cached carries none, and a "shortest first" that silently
  // put every such hike last would be sorting on the record's age.
  const canPrice = shelf.toWalk.some((hike) => cachedEstimate(hike, pace) !== null)
  const toWalk =
    sort === 'nearest' && at !== null
      ? sortedByNearest(shelf.toWalk, at)
      : sort === 'shortest' && canPrice
        ? sortedByTime(shelf.toWalk, pace)
        : shelf.toWalk

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
        {(at !== null || canPrice) && shelf.toWalk.length > 1 && (
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
            {at !== null && (
              <button
                type="button"
                className="whats-left__sort"
                aria-pressed={sort === 'nearest'}
                onClick={() => setSort('nearest')}
              >
                nearest me
              </button>
            )}
            {canPrice && (
              <button
                type="button"
                className="whats-left__sort"
                aria-pressed={sort === 'shortest'}
                onClick={() => setSort('shortest')}
              >
                shortest first
              </button>
            )}
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
                {/* Cached figures on purpose - see the header. The ≈time is
                  cached too and is absent rather than approximated when the
                  record holds no climb: this row still may not load the
                  routing graph, and may not invent a walking time either. */}
                <span className="plan-home__meta">
                  {formatDistance(hike.figures.miles, units)}
                  {hike.figures.legs.length > 0 &&
                    ` · ${hike.figures.legs.length} ${
                      hike.figures.legs.length === 1 ? 'leg' : 'legs'
                    }`}
                  {cachedEstimate(hike, pace) !== null &&
                    ` · ${cachedEstimate(hike, pace)?.text} walking`}
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

        {/* BOTH CONDITIONS, because the exchange needs both: day hikes ride
          it only while `account !== null && syncOn` (App.tsx, feeding
          lib/useDayHikesSync.ts), and the app's default state is signed out.
          An earlier version of this line said "signed in" alone - which is
          exactly wrong for the hiker who has an account and turned sync off
          for data, and who would have read a flat promise as backed up. */}
        {dayHikes.length === 0 && (
          <p className="day-hike-list__empty">
            Nothing saved yet. A day hike you build is kept on this phone — and, with an
            account and sync switched on, follows you to the next one.
          </p>
        )}

        {dayHikes.length > 0 && (
          <p className="day-hike-list__note">
            All of these are on this phone. With an account and sync switched on, they
            follow you to the next one.
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
