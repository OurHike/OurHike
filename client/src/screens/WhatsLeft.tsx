// What's left (#791) - the screen a section hiker or flip-flopper arrives
// with every spring: what do I still owe, and where do I start next?
//
// FLIP-FLOPPERS ARE THE DESIGN, NOT AN EDGE CASE. Every gap offers BOTH
// ends as start candidates, side by side, and the direction falls out of
// which one is picked. Nothing here calls a piece "next", numbers the
// cards, or draws them as steps: trail order is one sort offered beside
// "nearest me" and "fits my days", not the truth about what anybody should
// walk.
//
// THE SIZING IS THE HIKER'S OWN LOG, OR NOTHING. features/PERSONALIZED_PACE
// .md's rules hold: a range rather than a number, on device, and withheld
// entirely until there is enough history rather than borrowing Naismith's
// moving-time estimate and calling it "yours". The two instruments are
// different things and are never swapped for one another - see
// lib/dayReach.ts's header.
//
// What it must not become: no percentage complete, nothing overdue, no
// streaks, and no "you should do this next". The app answers a question the
// hiker asked by setting a number of days. It does not issue a plan for
// their remaining years.

import { useMemo, useState } from 'react'
import { dayReach, reachOver, tripReach, walkedDayMiles } from '../lib/dayReach'
import { hikeFigures, type Hike, type PlaceRef } from '../lib/hikes'
import { stopLabel } from '../lib/planDisplay'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'
import { formatDistance, formatDistanceRange, type UnitSystem } from '../lib/units'
import { sortGaps, whatsLeft, MIN_GAP_MI, type Gap, type GapSort } from '../lib/whatsLeft'
import './plan.css'

export interface WhatsLeftProps {
  hike: Hike
  trips: readonly Trip[]
  pois: readonly StoredPoi[]
  units: UnitSystem
  /** Where the hiker is on the pipeline's mile axis. Without it "nearest
   *  me" is not offered - a sort that cannot be computed honestly is not
   *  quietly replaced by one that can. */
  gpsMile: number | null
  /** Start a route at one end of a gap, walking toward the other. */
  onPlanFrom: (start: PlaceRef, toward: PlaceRef) => void
  onClose: () => void
}

/** The opening answer to "how many days have you got". A week off is the
 *  section hiker's own unit, and it is one tap from anything else. */
const DEFAULT_DAYS = 5
const MAX_DAYS = 30

export function WhatsLeft({
  hike,
  trips,
  pois,
  units,
  gpsMile,
  onPlanFrom,
  onClose,
}: WhatsLeftProps) {
  const [sort, setSort] = useState<GapSort>('trail')
  const [days, setDays] = useState(DEFAULT_DAYS)

  const left = useMemo(() => whatsLeft(hike, trips, pois), [hike, trips, pois])
  const figures = hikeFigures(hike, trips, pois)
  const reach = useMemo(() => dayReach(trips), [trips])
  const perTrip = useMemo(() => tripReach(trips), [trips])
  const walkedDays = useMemo(() => walkedDayMiles(trips).length, [trips])

  const bite = reach === null ? null : reachOver(reach, days)
  const sorted = sortGaps(left.gaps, sort, {
    gpsMile,
    reachMi: bite === null ? null : bite.highMi,
  })

  // A sort nobody can compute is not offered, rather than offered and
  // silently doing something else.
  const sorts: { key: GapSort; label: string }[] = [
    { key: 'trail', label: 'Trail order' },
    ...(gpsMile === null ? [] : [{ key: 'near' as GapSort, label: 'Nearest me' }]),
    ...(bite === null ? [] : [{ key: 'fits' as GapSort, label: 'Fits my days' }]),
  ]

  return (
    <div className="whats-left">
      <div className="legend__head">
        <button type="button" className="whats-left__back" onClick={onClose}>
          <span aria-hidden="true">←</span>
          <span className="visually-hidden">Back to the hike</span>
        </button>
        <h2 className="legend__title">What&rsquo;s left</h2>
      </div>

      <p className="whats-left__total">
        {formatDistance(figures.leftMi, units)} in {left.gaps.length}{' '}
        {left.gaps.length === 1 ? 'piece' : 'pieces'}
      </p>

      {sorts.length > 1 && (
        <div className="whats-left__sorts" role="group" aria-label="Order these by">
          {sorts.map((option) => (
            <button
              key={option.key}
              type="button"
              className={
                option.key === sort
                  ? 'whats-left__sort whats-left__sort--on'
                  : 'whats-left__sort'
              }
              aria-pressed={option.key === sort}
              onClick={() => setSort(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}

      <div className="whats-left__days">
        <span className="whats-left__days-label">I have</span>
        <span className="whats-left__stepper">
          <button
            type="button"
            className="whats-left__step"
            aria-label="One day fewer"
            disabled={days <= 1}
            onClick={() => setDays((current) => Math.max(1, current - 1))}
          >
            −
          </button>
          <span className="whats-left__days-count">
            {days} {days === 1 ? 'day' : 'days'}
          </span>
          <button
            type="button"
            className="whats-left__step"
            aria-label="One day more"
            disabled={days >= MAX_DAYS}
            onClick={() => setDays((current) => Math.min(MAX_DAYS, current + 1))}
          >
            +
          </button>
        </span>
      </div>

      {bite === null ? (
        <p className="whats-left__no-pace" role="note">
          {walkedDays === 0
            ? 'Nothing walked yet, so there’s no pace of yours to reckon with. Sizes here are miles only — a made-up average would be worse than none.'
            : `Only ${walkedDays} ${walkedDays === 1 ? 'day' : 'days'} walked so far, which isn’t enough to say what a day of yours covers. Sizes here are miles only until there are a few more.`}
        </p>
      ) : (
        <p className="whats-left__pace">
          ≈ {formatDistanceRange(bite.lowMi, bite.highMi, units)}, from your own{' '}
          {reach?.samples} days walked — your own spread, not a target, and
          {days === 1 ? ' a day' : ' days'} of walking rather than days away.
        </p>
      )}

      {sorted.length === 0 ? (
        <p className="whats-left__empty">
          Nothing left in this hike but {slivers(left.slivers, units)}.
        </p>
      ) : (
        <ul className="whats-left__gaps">
          {sorted.map((gap) => (
            <li key={gap.id}>
              <GapCard
                gap={gap}
                units={units}
                days={days}
                bite={bite}
                tripsWorth={
                  perTrip === null
                    ? null
                    : tripsFor(gap.lengthMi, perTrip.lowMi, perTrip.highMi)
                }
                onPlanFrom={onPlanFrom}
              />
            </li>
          ))}
        </ul>
      )}

      {left.slivers.count > 0 && sorted.length > 0 && (
        <p className="whats-left__slivers" role="note">
          {upperFirst(slivers(left.slivers, units))} — under{' '}
          {formatDistance(MIN_GAP_MI, units)} each, so they get no card. They are still
          trail nobody has walked.
        </p>
      )}
    </div>
  )
}

/** "3 stretches adding up to 0.4 mi" - the remainder the cards drop, said
 *  out loud rather than hidden, which is what #791 asked for. */
function slivers(
  { count, miles }: { count: number; miles: number },
  units: UnitSystem,
): string {
  return `${count} short ${count === 1 ? 'stretch' : 'stretches'} adding up to ${formatDistance(miles, units)}`
}

function upperFirst(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** How many trips this hiker's own size a stretch would take. A count of
 *  trips NEEDED, so both ends round up: five and a bit trips is six trips. */
function tripsFor(lengthMi: number, lowMi: number, highMi: number): string | null {
  if (lowMi <= 0 || highMi <= 0) return null
  const fewest = Math.ceil(lengthMi / highMi)
  const most = Math.ceil(lengthMi / lowMi)
  if (fewest === most) {
    return `≈ ${fewest} ${fewest === 1 ? 'trip' : 'trips'} your size`
  }
  return `≈ ${fewest}–${most} trips your size`
}

function GapCard({
  gap,
  units,
  days,
  bite,
  tripsWorth,
  onPlanFrom,
}: {
  gap: Gap
  units: UnitSystem
  days: number
  bite: { lowMi: number; highMi: number } | null
  tripsWorth: string | null
  onPlanFrom: (start: PlaceRef, toward: PlaceRef) => void
}) {
  return (
    <div className="whats-left__card">
      <div className="whats-left__card-head">
        <span className="whats-left__card-name">
          {placeLabel(gap.low)} → {placeLabel(gap.high)}
        </span>
        <span className="whats-left__card-figure">
          {formatDistance(gap.lengthMi, units)}
        </span>
      </div>
      {tripsWorth !== null && <span className="whats-left__card-note">{tripsWorth}</span>}

      <p className="whats-left__from">
        {bite === null
          ? 'Start from either end:'
          : `A ${days}-day bite from either end — ${bitePhrase(gap, bite, units)}:`}
      </p>
      {/* BOTH ends, side by side and in that order only because the list has
          to have one. Which is the start is the hiker's choice, and the
          direction is whatever falls out of it. */}
      <button
        type="button"
        className="whats-left__start"
        onClick={() => onPlanFrom(gap.low, gap.high)}
      >
        <span className="whats-left__start-name">North from {placeLabel(gap.low)}</span>
        <span className="whats-left__start-go" aria-hidden="true">
          Plan ›
        </span>
      </button>
      <button
        type="button"
        className="whats-left__start"
        onClick={() => onPlanFrom(gap.high, gap.low)}
      >
        <span className="whats-left__start-name">South from {placeLabel(gap.high)}</span>
        <span className="whats-left__start-go" aria-hidden="true">
          Plan ›
        </span>
      </button>
    </div>
  )
}

/** What a hiker's days would take out of this piece - and, where the piece
 *  is smaller than that, the fact that it is the whole thing. Two phrasings
 *  rather than one, because "all of it" and "some of it" are different
 *  answers and printing a number for both would blur them. */
function bitePhrase(
  gap: Gap,
  bite: { lowMi: number; highMi: number },
  units: UnitSystem,
): string {
  if (gap.lengthMi <= bite.lowMi) return 'the whole stretch, with room'
  if (gap.lengthMi <= bite.highMi) return 'possibly all of it'
  return `≈ ${formatDistanceRange(bite.lowMi, bite.highMi, units)} of it`
}

function placeLabel(ref: PlaceRef): string {
  return stopLabel({
    mile: ref.mile,
    ...(ref.name === undefined ? {} : { name: ref.name }),
  })
}
