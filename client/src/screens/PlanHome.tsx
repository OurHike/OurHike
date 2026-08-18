// The Plan tab's front door (#805).
//
// Before this, the tab opened straight into whichever plan was last open,
// and the way to everything else was an 11-px underlined "Your trips" in
// the header - which a maintainer walking through the built app missed
// entirely. A hiker with seven trips and two hikes had no page that said
// so.
//
// FIVE SECTIONS, IN THE ORDER SOMEBODY WANTS THEM: carry on with what is
// open, the hikes, the groups, the recent trips, and one primary action.
// The rule underneath is the one the entrance was also reworked around -
// **one primary action per screen, and it is the thing that goes down a
// level.** Everything else is a row, a chip or a link.
//
// THE COST, STATED RATHER THAN DISCOVERED: a hiker with one trip now taps
// twice to reach the timeline they used to land on. So the shell only
// shows this when there is something to choose between - see PlanScreen,
// which opens straight into a lone trip exactly as it did.
//
// The Hike / Trip / Days zooms (#790) sit INSIDE a hike or a trip. This
// home is above that ladder rather than part of it, which is why it
// carries no zoom control.

import { hikeFigures, type Hike } from '../lib/hikes'
import { planDayViews } from '../lib/plan'
import { tripDateRange } from '../lib/planDisplay'
import type { StoredPoi } from '../lib/trailData'
import { groupFigures, type TripGroup } from '../lib/tripGroups'
import type { Trip } from '../lib/trips'
import { formatDistance, type UnitSystem } from '../lib/units'
import './plan.css'

export interface PlanHomeProps {
  trips: readonly Trip[]
  hikes: readonly Hike[]
  groups: readonly TripGroup[]
  pois: readonly StoredPoi[]
  units: UnitSystem
  /** The trip the Plan tab would show, or null. */
  openTrip: Trip | null
  /** A route draft is in progress - the primary action says so rather than
   *  offering a fresh start over the top of it. */
  draftLive: boolean
  onOpenTrip: (id: string) => void
  onOpenHike: () => void
  onOpenGroup: (id: string) => void
  onAllTrips: () => void
  onNewTrip: () => void
}

/** How many trips the home lists before sending you to the full list. */
const RECENT_TRIPS = 3

export function PlanHome({
  trips,
  hikes,
  groups,
  pois,
  units,
  openTrip,
  draftLive,
  onOpenTrip,
  onOpenHike,
  onOpenGroup,
  onAllTrips,
  onNewTrip,
}: PlanHomeProps) {
  // Newest first, by the dates the trips already carry (#805). Undated
  // trips sort last rather than being hidden - they are plans somebody has
  // not decided a date for, which is a normal state and not an error.
  const recent = [...trips].sort((a, b) => {
    const aDate = firstDate(a)
    const bDate = firstDate(b)
    if (aDate === null && bDate === null) return 0
    if (aDate === null) return 1
    if (bDate === null) return -1
    return bDate.localeCompare(aDate)
  })

  return (
    <div className="plan-home">
      <header className="plan__head">
        <h1 className="plan__title">Plan</h1>
        <span className="plan__head-note">
          {trips.length} {trips.length === 1 ? 'trip' : 'trips'}
          {hikes.length > 0 &&
            ` · ${hikes.length} ${hikes.length === 1 ? 'hike' : 'hikes'}`}
        </span>
      </header>

      {openTrip !== null && (
        <section className="plan-home__section">
          <span className="plan-home__title">Carry on with</span>
          <button
            type="button"
            className="plan-home__open"
            onClick={() => onOpenTrip(openTrip.id)}
          >
            <span className="plan-home__open-name">{openTrip.name}</span>
            <span className="plan-home__meta">
              {tripDateRange(planDayViews(openTrip.plan).map((day) => day.date)) ??
                'no dates yet'}
            </span>
          </button>
        </section>
      )}

      {hikes.length > 0 && (
        <section className="plan-home__section">
          <span className="plan-home__title">Your hikes</span>
          {hikes.map((hike) => {
            const figures = hikeFigures(hike, trips, pois)
            return (
              <button
                type="button"
                className="plan-home__row"
                key={hike.id}
                onClick={onOpenHike}
              >
                <span className="plan-home__row-name">{hike.name}</span>
                {/* Miles walked and miles to go. No percentage and nothing
                    to fall behind - the same figures the hike zoom prints,
                    from the same function. */}
                <span className="plan-home__meta">
                  {formatDistance(figures.walkedMi, units)} walked ·{' '}
                  {formatDistance(figures.leftMi, units)} to go
                </span>
              </button>
            )
          })}
        </section>
      )}

      {groups.length > 0 && (
        <section className="plan-home__section">
          <span className="plan-home__title">Your groups</span>
          <div className="trip-list__group-chips">
            {groups.map((group) => (
              <button
                type="button"
                className="trip-list__group-chip"
                key={group.id}
                onClick={() => onOpenGroup(group.id)}
              >
                {group.name} · {groupFigures(group, trips).tripCount}
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="plan-home__section">
        <div className="plan-home__section-head">
          <span className="plan-home__title">Recent trips</span>
          {trips.length > RECENT_TRIPS && (
            <button type="button" className="plan-home__all" onClick={onAllTrips}>
              All {trips.length} ›
            </button>
          )}
        </div>
        {recent.slice(0, RECENT_TRIPS).map((trip) => (
          <button
            type="button"
            className="plan-home__row"
            key={trip.id}
            onClick={() => onOpenTrip(trip.id)}
          >
            <span className="plan-home__row-name">{trip.name}</span>
            <span className="plan-home__meta">
              {tripDateRange(planDayViews(trip.plan).map((day) => day.date)) ??
                'no dates yet'}
            </span>
          </button>
        ))}
        {trips.length <= RECENT_TRIPS && trips.length > 0 && (
          <button type="button" className="plan-home__all" onClick={onAllTrips}>
            Rename or delete ›
          </button>
        )}
      </section>

      <button type="button" className="plan__primary" onClick={onNewTrip}>
        {draftLive ? 'Back to your route' : 'Plan a new trip'}
      </button>
    </div>
  )
}

function firstDate(trip: Trip): string | null {
  for (const day of trip.plan.days) {
    if (day.date !== undefined) return day.date
  }
  return null
}
