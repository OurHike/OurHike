// The Plan tab's front door (#805) - two front doors, and since #1317 the
// APP's mode picks which, not a switch of Plan's own.
//
// THE FORK EXISTED AND THEN NOTHING DOWNSTREAM LOOKED DIFFERENT. "What are
// you planning?" (#977) asks the question once, and until #1008 every
// screen after it wore the same chrome: day hikes were a section between
// "Your hikes" and "Recent trips", and a hiker mid-flow had nothing on
// screen saying which of two kinds of plan they were inside. So the mode is
// the chrome now: **Day hikes** is the forest band and speaks in legs and
// walks; **Sections** is the deep band and keeps the trail vocabulary - days,
// zeros, resupply, carries. features/SEGMENTS.md calls `Hike.type` "a label,
// not a constraint"; this makes the label load-bearing on screen without
// enforcing anything in the model.
//
// AND THEN THE FORK WAS ASKED TWICE (#1317). #1008 gave Plan a switch of its
// own - `PlanMode`, local state, a `⇄` chip - while the app already had a
// three-way mode control the hiker had already answered with
// (`chrome/ModeSwitch.tsx`). Two switches for one question, and they could
// disagree: a hiker on Long hike could be standing in the day-hike room with
// a chip offering to take them somewhere they had already asked to be.
//
// So `PlanMode` is gone and this reads `hikerMode`. The chip goes with it,
// and the mode switch is the door now - which is what keeps decision #1's
// promise that the mode "never hides or gates a feature": that control is
// rendered on Today, in Settings and in the desktop sidebar, always, all
// three segments (ModeSwitch's own rule), so the other room is never more
// than a tap away and never behind an 11-px link (#805's own failure).
//
// VOLUNTEER GETS THE DAY ROOM, and there is no third room. "Today I'm
// volunteering" is a statement about the day's work, not about a kind of
// planning, and inventing a Plan room for it would make the word a place
// rather than a description - the thing chrome/tabs.ts took Volunteer out of
// the tab bar to avoid.
//
// LONG WITH NO HIKE PICKED gets the sections room rather than an empty
// hike's. That state is meant to be transient - tapping Long hike with no
// active hike opens the pick sheet, and cancelling it puts the mode back -
// but it is reachable, and the honest answer there is everything the hiker
// has kept rather than a room about a hike they have not named.
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
import type { HikerMode } from '../lib/hikerMode'
import { splitDayHikes } from '../lib/dayHikeShelf'
import { hikeFigures, type Hike } from '../lib/hikes'
import { planDayViews } from '../lib/plan'
import { dayLongDateLabel, tripDateRange } from '../lib/planDisplay'
import type { StoredPoi } from '../lib/trailData'
import type { TrailNetworkState } from '../lib/trailGraphData'
import { canRetryTrailNetwork, trailNetworkRefusal } from '../lib/trailNetworkText'
import { groupFigures, type TripGroup } from '../lib/tripGroups'
import type { Trip } from '../lib/trips'
import { formatDistance, type UnitSystem } from '../lib/units'
import './plan.css'

/**
 * Which room the tab is showing, derived from the app's mode and whether a
 * long hike is picked - never stored, and never a second answer to a
 * question `hikerMode` already answers. See the header.
 */
export type PlanRoom = 'day' | 'sections'

export function planRoomFor(mode: HikerMode): PlanRoom {
  return mode === 'long' ? 'sections' : 'day'
}

export interface PlanHomeProps {
  room: PlanRoom
  /** Open the "add a day hike to this hike" sheet (#1317). Undefined when
   *  the app is not in a long hike. */
  onAddDayHikeToHike?: () => void
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
  /** Why there is no junction graph, for the sentence that replaces the
   *  button (#1049). */
  network: TrailNetworkState
  onRetryNetwork?: () => void
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
  room,
  onAddDayHikeToHike,
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
  network,
  onRetryNetwork,
}: PlanHomeProps) {
  return room === 'day' ? (
    <DayHikesHome
      dayHikes={dayHikes}
      sectionCount={trips.length}
      onAllTrips={onAllTrips}
      units={units}
      draftKind={draftKind}
      onOpenDayHike={onOpenDayHike}
      onAllDayHikes={onAllDayHikes}
      onNewDayHike={onNewDayHike}
      onResumeDraft={onResumeDraft}
      network={network}
      onRetryNetwork={onRetryNetwork}
    />
  ) : (
    <TripsHome
      onAddDayHikeToHike={onAddDayHikeToHike}
      trips={trips}
      hikes={hikes}
      groups={groups}
      pois={pois}
      units={units}
      openTrip={openTrip}
      draftKind={draftKind}
      onOpenTrip={onOpenTrip}
      onOpenHike={onOpenHike}
      onOpenGroup={onOpenGroup}
      onAllTrips={onAllTrips}
      onNewTrip={onNewTrip}
      onResumeDraft={onResumeDraft}
    />
  )
}

/**
 * The band both homes wear: the eyebrow and the room's own word.
 *
 * NO SWITCH CHIP since #1317. It used to name the other room and was the
 * only way there; the app's mode control is that door now, and a chip beside
 * it would be a second answer to a question the hiker has already given -
 * see the header. The `plan-band--trips` class is kept as the deep band's
 * name because the shipped CSS is keyed on it; only the word a hiker reads
 * changed.
 */
function ModeBand({ room }: { room: PlanRoom }) {
  return (
    <header
      className={
        room === 'day' ? 'plan-band plan-band--day' : 'plan-band plan-band--trips'
      }
    >
      <div className="plan-band__words">
        <span className="plan-band__eyebrow">you&rsquo;re planning</span>
        <h1 className="plan-band__word">{room === 'day' ? 'Day hikes' : 'Sections'}</h1>
      </div>
    </header>
  )
}

interface DayHikesHomeProps {
  dayHikes: readonly DayHike[]
  /** How many multi-day sections the hiker has kept, for the door below.
   *  The count only - this room does not list them. */
  sectionCount: number
  units: UnitSystem
  draftKind: 'day' | 'trip' | null
  onOpenDayHike: (id: string) => void
  onAllDayHikes: () => void
  onAllTrips: () => void
  onNewDayHike: (() => void) | null
  onResumeDraft: () => void
  /** Why there is no junction graph, when there is none - so the refusal
   *  below says which absence it is rather than one sentence for five
   *  (#1049). `onNewDayHike` still decides WHETHER to refuse; this decides
   *  what the refusal says. */
  network: TrailNetworkState
  onRetryNetwork?: () => void
}

function DayHikesHome({
  dayHikes,
  sectionCount,
  units,
  draftKind,
  onOpenDayHike,
  onAllDayHikes,
  onAllTrips,
  onNewDayHike,
  onResumeDraft,
  network,
  onRetryNetwork,
}: DayHikesHomeProps) {
  const shelf = splitDayHikes(dayHikes)
  const recent = [...shelf.toWalk, ...shelf.walked]

  return (
    <div className="plan-home plan-home--day">
      <ModeBand room="day" />

      {/*
        THE ONE DOOR OUT OF THIS ROOM, and it is a list rather than a mode.

        #1317 bound the room to `hikerMode` and deleted Plan's own `⇄` chip,
        which was the only way a hiker in the day room reached their
        multi-day sections - `screens/TripList.tsx` is rendered by the other
        room and nothing else opens it. Binding the room without this row
        would make the mode GATE a feature, which decision #1 of that
        handoff forbids in the same breath as it asks for the binding.

        So: a plain door to the list, shown only when there is something
        behind it, and deliberately NOT a second mode switch. Tapping it
        opens the sections a hiker has kept; it does not claim they are on a
        long hike, which is the claim the old chip made by moving the room.
      */}
      {sectionCount > 0 && (
        <section className="plan-home__section">
          <div className="plan-home__section-head">
            <span className="plan-home__title">Sections you&rsquo;ve kept</span>
            <button type="button" className="plan-home__all" onClick={onAllTrips}>
              All {sectionCount} ›
            </button>
          </div>
        </section>
      )}

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
        // Both conditions carry the sentence: the exchange runs only with an
        // account AND sync on, and signed out is the app's default. See the
        // longer note in DayHikeList.tsx, which prints the same promise.
        <p className="plan-home__quiet-note">
          No day hikes saved yet. One you build is kept on this phone — and, with an
          account and sync switched on, follows you to the next one.
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
        <>
          {/* The cost, said before it is paid. This room's primary reaches
              `sweepForBuilder`, which discards a half-built route outright -
              the right behaviour for a door somebody deliberately opened
              (#997 settled that), and a bad thing to learn afterwards from
              an empty builder. Reaching this at all takes a chip tap across
              rooms: a live route puts the Plan tab in the trips room. */}
          {draftKind === 'trip' && (
            <p className="plan-home__refused" role="note">
              There&rsquo;s an unfinished route on the map. Starting a day hike drops it.
            </p>
          )}
          <button type="button" className="plan__primary" onClick={onNewDayHike}>
            Plan a day hike
          </button>
        </>
      ) : network.kind !== 'ready' ? (
        // PlanKindSheet's sentence, from the same place rather than copied
        // beside it (#1049): both read lib/trailNetworkText.ts, so the two
        // cannot drift and neither can go back to promising a data sync that
        // is not coming. A sentence, never a dead button (LineSheet's rule).
        //
        // Guarded on the network rather than inferred from `onNewDayHike`
        // being null, though today its call site nulls it for exactly this
        // reason. An invariant a screen ASSUMES is one that breaks the day
        // somebody adds a second reason to withhold the door - and the
        // failure would be this sentence, about the network, over a phone
        // whose network is fine.
        <>
          <p className="plan-home__refused" role="note">
            {trailNetworkRefusal(network)}
          </p>
          {/* The one absence a hiker can act on. */}
          {canRetryTrailNetwork(network) && onRetryNetwork !== undefined && (
            <button type="button" className="plan-kind__retry" onClick={onRetryNetwork}>
              Try again
            </button>
          )}
        </>
      ) : null}
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
  onOpenTrip: (id: string) => void
  onOpenHike: () => void
  onOpenGroup: (id: string) => void
  onAllTrips: () => void
  onNewTrip: () => void
  onResumeDraft: () => void
  /** Open the "add a day hike to this hike" sheet (#1317), or undefined when
   *  the app is not in a long hike - and then the row is absent rather than
   *  present and dead. */
  onAddDayHikeToHike?: () => void
}

function TripsHome({
  trips,
  hikes,
  groups,
  pois,
  units,
  openTrip,
  draftKind,
  onOpenTrip,
  onOpenHike,
  onOpenGroup,
  onAllTrips,
  onNewTrip,
  onResumeDraft,
  onAddDayHikeToHike,
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
      <ModeBand room="sections" />

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
            <span className="plan-home__title">Recent sections</span>
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
          No sections yet. A section follows one trail and breaks into days, zeros and
          resupply.
        </p>
      )}

      {/* A day hike on this trail counts toward the hike like any section
          does (#1317). Dashed like `route-stops__add`, because it adds a row
          to a list rather than going down a level - which is what separates
          it from the primary action below. */}
      {onAddDayHikeToHike !== undefined && (
        <button type="button" className="route-stops__add" onClick={onAddDayHikeToHike}>
          <span>Add a day hike to this hike</span>
          <span aria-hidden="true">+</span>
        </button>
      )}

      {/* The mirror of the day room's, and the same cost: `openDayHike`
          closes the route builder, which cancels the draft in it. */}
      {draftKind === 'day' && (
        <p className="plan-home__refused" role="note">
          There&rsquo;s an unfinished day hike on the map. Starting a trip drops it.
        </p>
      )}
      <button
        type="button"
        className="plan__primary"
        // Symmetrically: only a live TRIP draft is a route this room can
        // send somebody back to.
        onClick={draftKind === 'trip' ? onResumeDraft : onNewTrip}
      >
        {draftKind === 'trip' ? 'Back to your route' : 'Plan a new section'}
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
