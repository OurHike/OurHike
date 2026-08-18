// Every trip a hiker has kept (#787).
//
// The screen that makes "more than one" real: before this, planning a second
// trip overwrote the first, and there was nowhere to see that a hiker had a
// history at all.
//
// DELIBERATELY SMALL. This is a switcher, not the hike surface: the hike
// zoom (screens/HikeZoom.tsx, #790) is where trips sit in trail order beside
// the gaps between them, and it is the screen to add to. Everything here is
// the minimum that stops plans being destroyed: see them, open one, rename
// it, delete it - plus the roll-up block below, which is how a hiker with no
// hike yet finds the button that makes one.
//
// Every figure comes off the plan itself rather than being stored beside it,
// the same rule the timeline follows - a trip that says "3 days" and a
// timeline that draws four would be two answers to one question.

import { useState } from 'react'
import type { ElevationProfile } from '../lib/elevationProfile'
import { hikeFigures, type Hike } from '../lib/hikes'
import { planDayViews, walkedDayCount } from '../lib/plan'
import { tripDateRange } from '../lib/planDisplay'
import type { StoredPoi } from '../lib/trailData'
import { groupFigures, type TripGroup } from '../lib/tripGroups'
import type { Trip } from '../lib/trips'
import { formatDistance, type UnitSystem } from '../lib/units'
import './plan.css'

export interface TripListProps {
  trips: readonly Trip[]
  openId: string | null
  /** Unused for figures today - distance and days need no profile - and
   *  taken so the row summary can gain climb or ≈time without a prop change
   *  when #790 lands. */
  elevation: ElevationProfile | null
  /** The hikes those trips are grouped into (#788). Their roll-ups are
   *  derived on render and stored nowhere. */
  hikes: readonly Hike[]
  /** The download in hand - what a hike's ends are resolved against, so a
   *  relocated shelter moves the hike rather than the miles drifting under
   *  it. */
  pois: readonly StoredPoi[]
  units: UnitSystem
  onOpen: (id: string) => void
  onRename: (id: string, name: string) => void
  onRemove: (id: string) => void
  /** Start a new trip - the route builder, same door as the empty state. */
  onNew: () => void
  /** Group every trip here into one hike - the "I already have a history"
   *  door. Absent nothing to group. */
  onGroupIntoHike: () => void
  /** The hiker's own buckets (#800). Listed here until the Plan home
   *  (#805) gives them a place of their own. */
  groups: readonly TripGroup[]
  onOpenGroup: (id: string) => void
  onNewGroup: (name: string) => void
  onClose: () => void
}

/** Distance and days, off the plan. Zeros are days too - they hold a date
 *  and eat a day of food (lib/plan.ts) - so the count is every row the
 *  timeline would draw, not only the walking ones.
 *
 *  A RECORDED stretch (#789) prints no day count: its "days" are the
 *  boundaries a hiker could remember years later, not days anybody walked
 *  as days, and "1 day" against 300 miles would be the display outrunning
 *  its source. */
function summarise(trip: Trip, units: UnitSystem): string {
  const views = planDayViews(trip.plan)
  const distanceMi = views.reduce(
    (sum, day) => sum + Math.abs(day.end.mile - day.start.mile),
    0,
  )
  if (trip.recorded === true) return formatDistance(distanceMi, units)
  const days = `${views.length} ${views.length === 1 ? 'day' : 'days'}`
  return `${formatDistance(distanceMi, units)} · ${days}`
}

/** "walked", "part walked", or nothing at all. A record, never a score:
 *  no percentage, no count of what is left, nothing to fall behind. */
function walkedNote(trip: Trip): string | null {
  // Provenance first: "recorded" says both that it is walked and that
  // nobody planned it, which "walked" alone would not.
  if (trip.recorded === true) return 'recorded'
  const walked = walkedDayCount(trip.plan)
  if (walked === 0) return null
  return walked === trip.plan.days.length ? 'walked' : 'part walked'
}

export function TripList({
  trips,
  openId,
  hikes,
  pois,
  units,
  onOpen,
  onRename,
  onRemove,
  onNew,
  onGroupIntoHike,
  groups,
  onOpenGroup,
  onNewGroup,
  onClose,
}: TripListProps) {
  const [renaming, setRenaming] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null)
  const [newGroup, setNewGroup] = useState<string | null>(null)

  return (
    <div className="trip-list" role="dialog" aria-label="Your trips">
      <div className="legend__head">
        <h2 className="legend__title">Your trips</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {hikes.map((hike) => {
        const figures = hikeFigures(hike, trips, pois)
        return (
          <div className="trip-list__hike" key={hike.id}>
            <div className="trip-list__hike-head">
              <span className="trip-list__hike-name">{hike.name}</span>
              <span className="trip-list__hike-type">{hike.type}</span>
            </div>
            {/* Miles and trips. No percentage, no pace, nothing to fall
                behind - SEGMENTS.md: "a personal record, not a
                performance." */}
            <span className="trip-list__hike-figures">
              {formatDistance(figures.walkedMi, units)} walked ·{' '}
              {formatDistance(figures.leftMi, units)} to go
            </span>
            <span className="trip-list__hike-figures">
              {figures.tripCount} {figures.tripCount === 1 ? 'trip' : 'trips'} ·{' '}
              {figures.daysWalked} {figures.daysWalked === 1 ? 'day' : 'days'} walked
            </span>
            {figures.uncertain && (
              <p className="trip-list__hike-note" role="note">
                One end of this hike points at a place this download doesn&rsquo;t have,
                so these figures rest on the mile it had when you set it.
              </p>
            )}
          </div>
        )
      })}

      {trips.length === 0 ? (
        <p className="trip-list__empty">
          Nothing kept yet. A trip is saved the moment you lay days over a route.
        </p>
      ) : (
        <ul className="trip-list__items">
          {trips.map((trip) => {
            const note = walkedNote(trip)
            // Every surface that names a trip prints its dates (#805). An
            // undated one says so rather than looking like a dated trip
            // with the dates missing.
            const dates = tripDateRange(planDayViews(trip.plan).map((day) => day.date))
            return (
              <li
                key={trip.id}
                className={
                  trip.id === openId
                    ? 'trip-list__item trip-list__item--open'
                    : 'trip-list__item'
                }
              >
                {renaming === trip.id ? (
                  <div className="trip-list__rename">
                    <input
                      type="text"
                      className="trip-list__rename-input"
                      autoFocus
                      value={draftName}
                      aria-label={`New name for ${trip.name}`}
                      onChange={(event) => setDraftName(event.target.value)}
                    />
                    <button
                      type="button"
                      className="trip-list__action"
                      onClick={() => {
                        // An empty name is not refused here - the store
                        // writes the route's own ends back instead, so a
                        // cleared field cannot leave an unidentifiable row.
                        onRename(trip.id, draftName)
                        setRenaming(null)
                      }}
                    >
                      Save
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      className="trip-list__open"
                      onClick={() => onOpen(trip.id)}
                    >
                      <span className="trip-list__name">{trip.name}</span>
                      <span className="trip-list__meta">
                        {summarise(trip, units)}
                        {` · ${dates ?? 'no dates yet'}`}
                      </span>
                    </button>
                    <div className="trip-list__actions">
                      {trip.id === openId && (
                        <span className="trip-list__badge">open</span>
                      )}
                      {note !== null && <span className="trip-list__badge">{note}</span>}
                      <button
                        type="button"
                        className="trip-list__action"
                        onClick={() => {
                          setRenaming(trip.id)
                          setDraftName(trip.name)
                          setConfirmingDelete(null)
                        }}
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        className="trip-list__action trip-list__action--danger"
                        onClick={() => {
                          if (confirmingDelete !== trip.id) {
                            setConfirmingDelete(trip.id)
                            return
                          }
                          setConfirmingDelete(null)
                          onRemove(trip.id)
                        }}
                      >
                        {confirmingDelete === trip.id ? 'Tap again to delete' : 'Delete'}
                      </button>
                    </div>
                  </>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {/* The hiker's own buckets, which a trip can be in several of at once
          - unlike a hike, of which it has one (#800). */}
      {(groups.length > 0 || trips.length > 0) && (
        <div className="trip-list__groups">
          <span className="trip-list__groups-title">Your groups</span>
          {groups.length === 0 && (
            <p className="trip-list__empty">
              None yet. A group is any set of trips you want kept together — every Sunday,
              with Dad, this season.
            </p>
          )}
          <div className="trip-list__group-chips">
            {groups.map((group) => {
              const figures = groupFigures(group, trips)
              return (
                <button
                  type="button"
                  className="trip-list__group-chip"
                  key={group.id}
                  onClick={() => onOpenGroup(group.id)}
                >
                  {group.name} · {figures.tripCount}
                </button>
              )
            })}
            {newGroup === null ? (
              <button
                type="button"
                className="trip-list__group-chip trip-list__group-chip--new"
                onClick={() => setNewGroup('')}
              >
                + New group
              </button>
            ) : (
              <span className="trip-list__rename">
                <input
                  type="text"
                  className="trip-list__rename-input"
                  autoFocus
                  value={newGroup}
                  placeholder="Every Sunday"
                  aria-label="Name for the new group"
                  onChange={(event) => setNewGroup(event.target.value)}
                />
                <button
                  type="button"
                  className="trip-list__action"
                  onClick={() => {
                    if (newGroup.trim() !== '') onNewGroup(newGroup.trim())
                    setNewGroup(null)
                  }}
                >
                  Save
                </button>
              </span>
            )}
          </div>
        </div>
      )}

      {hikes.length === 0 && trips.length > 0 && (
        <button type="button" className="trip-list__group" onClick={onGroupIntoHike}>
          Group these into one hike
        </button>
      )}

      <button type="button" className="plan__primary" onClick={onNew}>
        Plan another trip
      </button>
    </div>
  )
}
