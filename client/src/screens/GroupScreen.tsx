// One of the hiker's own buckets (#800).
//
// WHAT IS DELIBERATELY ABSENT, and the absence is the design: no ribbon, no
// gaps, no percentage, no "14 Sundays in a row". A group has no two ends,
// so it has nothing to draw a ribbon against and nothing to be a fraction
// of - and the screen says that out loud rather than drawing an empty one.
// A bucket of weekly day hikes is exactly where a streak would arrive
// uninvited (OurHikeValues.md #1), which is why the anti-gamification test
// covers this file too.
//
// Miles, days, trips and the span of dates. That is everything a set with
// no geography honestly knows about itself.

import { useState } from 'react'
import { dayDateLabel } from '../lib/planDisplay'
import { planDayViews, walkedDayCount } from '../lib/plan'
import { groupFigures, groupTrips, type TripGroup } from '../lib/tripGroups'
import type { Trip } from '../lib/trips'
import { formatDistance, type UnitSystem } from '../lib/units'
import './plan.css'

export interface GroupScreenProps {
  group: TripGroup
  /** Every kept trip - the group picks its own out, and the rest are what
   *  "add a trip" offers. */
  trips: readonly Trip[]
  units: UnitSystem
  onOpenTrip: (id: string) => void
  onAddTrip: (tripId: string) => void
  onRemoveTrip: (tripId: string) => void
  onRename: (name: string) => void
  onRemove: () => void
  onClose: () => void
}

export function GroupScreen({
  group,
  trips,
  units,
  onOpenTrip,
  onAddTrip,
  onRemoveTrip,
  onRename,
  onRemove,
  onClose,
}: GroupScreenProps) {
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState(group.name)
  const [adding, setAdding] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const mine = groupTrips(group, trips)
  const figures = groupFigures(group, trips)
  const available = trips.filter((trip) => !group.tripIds.includes(trip.id))

  return (
    <div className="group-screen" role="dialog" aria-label={`Group: ${group.name}`}>
      <div className="legend__head">
        <button type="button" className="whats-left__back" onClick={onClose}>
          <span aria-hidden="true">←</span>
          <span className="visually-hidden">Back</span>
        </button>
        {renaming ? (
          <div className="trip-list__rename">
            <input
              type="text"
              className="trip-list__rename-input"
              autoFocus
              value={draftName}
              aria-label={`New name for ${group.name}`}
              onChange={(event) => setDraftName(event.target.value)}
            />
            <button
              type="button"
              className="trip-list__action"
              onClick={() => {
                onRename(draftName)
                setRenaming(false)
              }}
            >
              Save
            </button>
          </div>
        ) : (
          <h2 className="legend__title">{group.name}</h2>
        )}
      </div>

      {/* Trips, miles and days. Nothing here is a fraction of anything -
          there is nothing to be a fraction OF. */}
      <p className="group-screen__figures">
        {figures.tripCount} {figures.tripCount === 1 ? 'trip' : 'trips'} ·{' '}
        {formatDistance(figures.walkedMi, units)} of trail · {figures.daysWalked}{' '}
        {figures.daysWalked === 1 ? 'day' : 'days'} walked
      </p>
      {figures.from !== null && (
        <p className="group-screen__dates">
          {figures.from === figures.to
            ? dayDateLabel(figures.from)
            : `${dayDateLabel(figures.from)} – ${dayDateLabel(figures.to as string)}`}
        </p>
      )}

      {mine.length === 0 ? (
        <p className="trip-list__empty">
          Nothing in here yet. Add a trip and it stays in whatever other groups it is
          already in.
        </p>
      ) : (
        <ul className="trip-list__items">
          {mine.map((trip) => {
            const dates = planDayViews(trip.plan)
              .map((day) => day.date)
              .filter((date): date is string => date !== null)
            const walked = walkedDayCount(trip.plan) > 0
            return (
              <li className="trip-list__item" key={trip.id}>
                <button
                  type="button"
                  className="trip-list__open"
                  onClick={() => onOpenTrip(trip.id)}
                >
                  <span className="trip-list__name">{trip.name}</span>
                  <span className="trip-list__meta">
                    {dates.length > 0 ? dayDateLabel(dates[0]) : 'no dates yet'}
                    {walked && ' · walked'}
                  </span>
                </button>
                <div className="trip-list__actions">
                  <button
                    type="button"
                    className="trip-list__action"
                    onClick={() => onRemoveTrip(trip.id)}
                  >
                    Take out
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {/* The honest limit of a set with no ends, said rather than left for
          somebody to notice as a missing feature. */}
      <p className="group-screen__note" role="note">
        No ribbon and no gaps here: a group has no two ends, so there is nothing to draw
        them against. That is a hike&rsquo;s job.
      </p>

      {adding ? (
        <div className="group-screen__picker">
          {available.length === 0 ? (
            <p className="trip-list__empty">Every trip you have is already in here.</p>
          ) : (
            available.map((trip) => (
              <button
                type="button"
                className="group-screen__pick"
                key={trip.id}
                onClick={() => {
                  onAddTrip(trip.id)
                  setAdding(false)
                }}
              >
                {trip.name}
              </button>
            ))
          )}
          <button
            type="button"
            className="trip-list__action"
            onClick={() => setAdding(false)}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button type="button" className="plan__primary" onClick={() => setAdding(true)}>
          Add a trip
        </button>
      )}

      <div className="plan__foot">
        <button
          type="button"
          className="plan__foot-action"
          onClick={() => {
            setDraftName(group.name)
            setRenaming(true)
          }}
        >
          Rename
        </button>
        <button
          type="button"
          className="plan__foot-action plan__foot-action--danger"
          onClick={() => {
            if (!confirmingDelete) {
              setConfirmingDelete(true)
              return
            }
            setConfirmingDelete(false)
            onRemove()
          }}
        >
          {/* Deleting a bucket must never delete the walking that was in
              it - the same rule removeHike follows. */}
          {confirmingDelete ? 'Tap again — the trips stay' : 'Delete this group'}
        </button>
      </div>
    </div>
  )
}
