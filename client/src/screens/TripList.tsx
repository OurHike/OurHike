// Every trip a hiker has kept (#787).
//
// The screen that makes "more than one" real: before this, planning a second
// trip overwrote the first, and there was nowhere to see that a hiker had a
// history at all.
//
// DELIBERATELY SMALL. This is a switcher, not the hike surface - **#790 —
// The Plan tab gains three zooms** replaces this chrome with the hike zoom,
// where trips sit under a hike beside the gaps between them. Everything here
// is the minimum that stops plans being destroyed: see them, open one,
// rename it, delete it.
//
// Every figure comes off the plan itself rather than being stored beside it,
// the same rule the timeline follows - a trip that says "3 days" and a
// timeline that draws four would be two answers to one question.

import { useState } from 'react'
import type { ElevationProfile } from '../lib/elevationProfile'
import { planDayViews, walkedDayCount, type HikePlan } from '../lib/plan'
import { dayDateLabel } from '../lib/planDisplay'
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
  units: UnitSystem
  onOpen: (id: string) => void
  onRename: (id: string, name: string) => void
  onRemove: (id: string) => void
  /** Start a new trip - the route builder, same door as the empty state. */
  onNew: () => void
  onClose: () => void
}

/** Distance and days, off the plan. Zeros are days too - they hold a date
 *  and eat a day of food (lib/plan.ts) - so the count is every row the
 *  timeline would draw, not only the walking ones. */
function summarise(plan: HikePlan, units: UnitSystem): string {
  const views = planDayViews(plan)
  const distanceMi = views.reduce(
    (sum, day) => sum + Math.abs(day.end.mile - day.start.mile),
    0,
  )
  const days = `${views.length} ${views.length === 1 ? 'day' : 'days'}`
  return `${formatDistance(distanceMi, units)} · ${days}`
}

/** "walked", "part walked", or nothing at all. A record, never a score:
 *  no percentage, no count of what is left, nothing to fall behind. */
function walkedNote(plan: HikePlan): string | null {
  const walked = walkedDayCount(plan)
  if (walked === 0) return null
  return walked === plan.days.length ? 'walked' : 'part walked'
}

export function TripList({
  trips,
  openId,
  units,
  onOpen,
  onRename,
  onRemove,
  onNew,
  onClose,
}: TripListProps) {
  const [renaming, setRenaming] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null)

  return (
    <div className="trip-list" role="dialog" aria-label="Your trips">
      <div className="legend__head">
        <h2 className="legend__title">Your trips</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {trips.length === 0 ? (
        <p className="trip-list__empty">
          Nothing kept yet. A trip is saved the moment you lay days over a route.
        </p>
      ) : (
        <ul className="trip-list__items">
          {trips.map((trip) => {
            const note = walkedNote(trip.plan)
            const dates = planDayViews(trip.plan)
              .map((day) => day.date)
              .filter((date): date is string => date !== null)
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
                        {summarise(trip.plan, units)}
                        {dates.length > 0 && ` · from ${dayDateLabel(dates[0])}`}
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

      <button type="button" className="plan__primary" onClick={onNew}>
        Plan another trip
      </button>
    </div>
  )
}
