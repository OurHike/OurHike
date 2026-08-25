// The Plan tab's front door (#805) - now two front doors, one per mode
// (#1008).
//
// THE FORK EXISTED AND THEN NOTHING DOWNSTREAM LOOKED DIFFERENT. "What are
// you planning?" (#977) asks the question once, and until #1008 every
// screen after it wore the same chrome: day hikes were a section between
// "Your hikes" and "Recent trips", and a hiker mid-flow had nothing on
// screen saying which of two kinds of plan they were inside. So the mode is
// the chrome now: **Day hikes** is the forest band and speaks in legs and
// walks; **Trips** is the deep band and keeps the trail vocabulary - days,
// zeros, resupply, carries. features/SEGMENTS.md calls `Hike.type` "a label,
// not a constraint"; this makes the label load-bearing on screen without
// enforcing anything in the model.
//
// EACH HOME KEEPS THE RULE THE OLD ONE WAS BUILT AROUND: one primary action
// per screen, and it is the thing that goes down a level. What changed is
// that the action now does what its mode says - "Plan a day hike" opens the
// day-hike builder, "Plan a new trip" opens the route builder - rather than
// both opening the fork to ask a question the band has already answered.
// The fork itself is kept exactly as built and stays the entrance where the
// question is real: the empty state, where no mode exists yet
// (chrome/PlanKindSheet.tsx).
//
// WHAT THE DAY HOME DOES NOT SHOW, AND WHY: the storyboard's "starter hikes
// near you" waits for data that does not exist - no club-laid route dataset
// is anywhere in this repository, and a shelf with a label and no answer on
// it is the failure #805 removed. Its "carry on with" card waits for a
// state that means it: the store's `openId` says "card open now", not "last
// worked on", and a carry-on row built from it would duplicate the card
// floating over this same screen.

import type { DayHike } from '../lib/dayHikes'
import { splitDayHikes } from '../lib/dayHikeShelf'
import { hikeFigures, type Hike } from '../lib/hikes'
import { planDayViews } from '../lib/plan'
import { dayLongDateLabel, tripDateRange } from '../lib/planDisplay'
import type { StoredPoi } from '../lib/trailData'
import { groupFigures, type TripGroup } from '../lib/tripGroups'
import type { Trip } from '../lib/trips'
import { formatDistance, type UnitSystem } from '../lib/units'
import './plan.css'

/** Which of the two kinds of planning the tab is showing. */
export type PlanMode = 'day' | 'trips'

export interface PlanHomeProps {
  mode: PlanMode
  onSwitchMode: (mode: PlanMode) => void
  trips: readonly Trip[]
  hikes: readonly Hike[]
  /** The saved day hikes (#980) - listed from their cached figures, which is
   *  the store's own stated purpose for keeping them. */
  dayHikes: readonly DayHike[]
  groups: readonly TripGroup[]
  pois: readonly StoredPoi[]
  units: UnitSystem
  /** The trip the Plan tab would show, or null. */
  openTrip: Trip | null
  /**
   * Which builder holds a live draft, or null.
   *
   * A room offers "Back to your route" only for its OWN draft. One shared
   * boolean put a button into the multi-day route builder under a band
   * reading "you're planning / Day hikes" - the mode confusion this split
   * exists to end, with the room's own action missing besides.
   */
  draftKind: 'day' | 'trip' | null
  onOpenTrip: (id: string) => void
  onOpenHike: () => void
  onOpenDayHike: (id: string) => void
  onOpenGroup: (id: string) => void
  onAllTrips: () => void
  onAllDayHikes: () => void
  /** Open the day-hike builder, or null when this phone has no junction
   *  graph - null renders the sentence, never a dead button. */
  onNewDayHike: (() => void) | null
  /** Open the route builder. */
  onNewTrip: () => void
  /** Back to whichever builder holds the live draft (the shell knows which,
   *  chrome/PlanKindSheet's opener rule). */
  onResumeDraft: () => void
}

/** How many entries a home lists before sending you to the full list. */
const RECENT_TRIPS = 3
const RECENT_DAY_HIKES = 3

export function PlanHome({
  mode,
  onSwitchMode,
  trips,
  hikes,
  dayHikes,
  groups,
  pois,
  units,
  openTrip,
  draftKind,
  onOpenTrip,
  onOpenHike,
  onOpenDayHike,
  onOpenGroup,
  onAllTrips,
  onAllDayHikes,
  onNewDayHike,
  onNewTrip,
  onResumeDraft,
}: PlanHomeProps) {
  return mode === 'day' ? (
    <DayHikesHome
      dayHikes={dayHikes}
      units={units}
      draftKind={draftKind}
      onSwitchMode={onSwitchMode}
      onOpenDayHike={onOpenDayHike}
      onAllDayHikes={onAllDayHikes}
      onNewDayHike={onNewDayHike}
      onResumeDraft={onResumeDraft}
    />
  ) : (
    <TripsHome
      trips={trips}
      hikes={hikes}
      groups={groups}
      pois={pois}
      units={units}
      openTrip={openTrip}
      draftKind={draftKind}
      onSwitchMode={onSwitchMode}
      onOpenTrip={onOpenTrip}
      onOpenHike={onOpenHike}
      onOpenGroup={onOpenGroup}
      onAllTrips={onAllTrips}
      onNewTrip={onNewTrip}
      onResumeDraft={onResumeDraft}
    />
  )
}

/** The band both homes wear: the eyebrow, the mode word, and the way to the
 *  other room. The switch chip names its destination, not this screen -
 *  that is what makes it a door rather than a title. */
function ModeBand({
  mode,
  onSwitchMode,
}: {
  mode: PlanMode
  onSwitchMode: (mode: PlanMode) => void
}) {
  const other: PlanMode = mode === 'day' ? 'trips' : 'day'
  return (
    <header className={`plan-band plan-band--${mode}`}>
      <div className="plan-band__words">
        <span className="plan-band__eyebrow">you&rsquo;re planning</span>
        <h1 className="plan-band__word">{mode === 'day' ? 'Day hikes' : 'Trips'}</h1>
      </div>
      <button
        type="button"
        className="plan-band__switch"
        onClick={() => onSwitchMode(other)}
      >
        {other === 'day' ? 'Day hikes' : 'Trips'} <span aria-hidden="true">⇄</span>
      </button>
    </header>
  )
}

interface DayHikesHomeProps {
  dayHikes: readonly DayHike[]
  units: UnitSystem
  draftKind: 'day' | 'trip' | null
  onSwitchMode: (mode: PlanMode) => void
  onOpenDayHike: (id: string) => void
  onAllDayHikes: () => void
  onNewDayHike: (() => void) | null
  onResumeDraft: () => void
}

function DayHikesHome({
  dayHikes,
  units,
  draftKind,
  onSwitchMode,
  onOpenDayHike,
  onAllDayHikes,
  onNewDayHike,
  onResumeDraft,
}: DayHikesHomeProps) {
  const shelf = splitDayHikes(dayHikes)
  const recent = [...shelf.toWalk, ...shelf.walked]

  return (
    <div className="plan-home plan-home--day">
      <ModeBand mode="day" onSwitchMode={onSwitchMode} />

      {dayHikes.length > 0 && (
        <section className="plan-home__section">
          <div className="plan-home__section-head">
            <span className="plan-home__title">Your day hikes</span>
            <button type="button" className="plan-home__all" onClick={onAllDayHikes}>
              All {dayHikes.length} ›
            </button>
          </div>
          {recent.slice(0, RECENT_DAY_HIKES).map((dayHike) => (
            <button
              type="button"
              className="plan-home__row"
              key={dayHike.id}
              onClick={() => onOpenDayHike(dayHike.id)}
            >
              <span className="plan-home__row-name">{dayHike.name}</span>
              {/* The cached figures, which exist for exactly this row: a list
                  must not load the routing graph to say "3.4 mi". The card a
                  tap opens re-derives against the live graph and says so when
                  it cannot. */}
              <span className="plan-home__meta">
                {formatDistance(dayHike.figures.miles, units)} ·{' '}
                {dayHike.date !== null ? dayLongDateLabel(dayHike.date) : 'no date yet'}
              </span>
            </button>
          ))}
        </section>
      )}

      {dayHikes.length === 0 && (
        // "Signed in" carries the sentence: the exchange runs only with an
        // account and sync on, and signed out is the app's default.
        <p className="plan-home__quiet-note">
          No day hikes saved yet. One you build is kept on this phone — and, signed in,
          follows your account to the next one.
        </p>
      )}

      {/* Only a DAY draft brings a hiker back here. A live trip route is the
          other room's business: offering "Back to your route" under a band
          reading "Day hikes" would drop somebody into the multi-day builder
          from the day room, and leave this room with no action of its own. */}
      {draftKind === 'day' ? (
        <button type="button" className="plan__primary" onClick={onResumeDraft}>
          Back to your route
        </button>
      ) : onNewDayHike !== null ? (
        <button type="button" className="plan__primary" onClick={onNewDayHike}>
          Plan a day hike
        </button>
      ) : (
        // PlanKindSheet's sentence, verbatim - the same claim about the same
        // missing artifact, and a test pins the two copies together so one
        // cannot be reworded without the other. A sentence, never a dead
        // button (LineSheet's rule).
        <p className="plan-home__refused" role="note">
          This phone hasn&rsquo;t got the trail network yet, so there&rsquo;s nothing to
          build a day hike on. It arrives with the next data sync.
        </p>
      )}
    </div>
  )
}

interface TripsHomeProps {
  trips: readonly Trip[]
  hikes: readonly Hike[]
  groups: readonly TripGroup[]
  pois: readonly StoredPoi[]
  units: UnitSystem
  openTrip: Trip | null
  draftKind: 'day' | 'trip' | null
  onSwitchMode: (mode: PlanMode) => void
  onOpenTrip: (id: string) => void
  onOpenHike: () => void
  onOpenGroup: (id: string) => void
  onAllTrips: () => void
  onNewTrip: () => void
  onResumeDraft: () => void
}

function TripsHome({
  trips,
  hikes,
  groups,
  pois,
  units,
  openTrip,
  draftKind,
  onSwitchMode,
  onOpenTrip,
  onOpenHike,
  onOpenGroup,
  onAllTrips,
  onNewTrip,
  onResumeDraft,
}: TripsHomeProps) {
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
    <div className="plan-home plan-home--trips">
      <ModeBand mode="trips" onSwitchMode={onSwitchMode} />

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

      {trips.length > 0 && (
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
      )}

      {trips.length === 0 && hikes.length === 0 && (
        <p className="plan-home__quiet-note">
          No trips yet. A trip follows one trail and breaks into days, zeros and resupply.
        </p>
      )}

      <button
        type="button"
        className="plan__primary"
        // Symmetrically: only a live TRIP draft is a route this room can
        // send somebody back to.
        onClick={draftKind === 'trip' ? onResumeDraft : onNewTrip}
      >
        {draftKind === 'trip' ? 'Back to your route' : 'Plan a new trip'}
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
