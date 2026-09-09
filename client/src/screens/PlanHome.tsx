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

import { useState, type ReactNode } from 'react'
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
  /** The long hike the app is on, or null. Its presence is what turns the
   *  sections room into the HIKE's room (#1329, handoff §4). */
  activeHike: Hike | null
  /** Open "Which hike are you on?" - the pick sheet, as a switch. Undefined
   *  where there is nothing to switch between. */
  onSwitchHike?: () => void
  /** Give the active hike a different name (#1344). */
  onRenameHike?: (name: string) => void
  /**
   * Planning a section, in place (#1344).
   *
   * A slot rather than this screen owning the planner, for `kindSheet`'s
   * reason one level up: the two ends are chosen with the route builder's
   * own stop picker and the days are laid out by `PlanTargetSheet`, both of
   * which are the shell's to render. What this screen owns is WHERE it
   * appears - in the column, where the primary was.
   */
  sectionPlanner?: ReactNode
  /** Move a section into the active hike, or out of it (#1367). */
  onAddSectionToHike?: (tripId: string) => void
  onTakeSectionOut?: (tripId: string) => void
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
  activeHike,
  onSwitchHike,
  onRenameHike,
  sectionPlanner,
  onAddSectionToHike,
  onTakeSectionOut,
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
  // THREE HOMES, TWO ROOMS. `room` still answers "day hikes or sections",
  // and the sections room answers a second question the mode has already
  // settled: whether there is a hike to be the room ABOUT. Long with no hike
  // picked is transient by design (the pick sheet opens on the way in) and
  // reachable anyway, and the honest answer there is everything the hiker
  // has kept rather than a room about a hike they have not named - the same
  // reasoning `planRoomFor` gives for sending that state here at all.
  if (room === 'sections' && activeHike !== null) {
    return (
      <HikeRoom
        hike={activeHike}
        trips={trips}
        dayHikes={dayHikes}
        pois={pois}
        units={units}
        draftKind={draftKind}
        onSwitchHike={onSwitchHike}
        onRenameHike={onRenameHike}
        sectionPlanner={sectionPlanner}
        onAddSectionToHike={onAddSectionToHike}
        onTakeSectionOut={onTakeSectionOut}
        onOpenHike={onOpenHike}
        onOpenTrip={onOpenTrip}
        onOpenDayHike={onOpenDayHike}
        onAllTrips={onAllTrips}
        onAddDayHikeToHike={onAddDayHikeToHike}
        onNewTrip={onNewTrip}
        onResumeDraft={onResumeDraft}
      />
    )
  }

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

interface HikeRoomProps {
  hike: Hike
  trips: readonly Trip[]
  dayHikes: readonly DayHike[]
  pois: readonly StoredPoi[]
  units: UnitSystem
  draftKind: 'day' | 'trip' | null
  onSwitchHike?: () => void
  sectionPlanner?: ReactNode
  /** Give the hike a different name (#1344). `renameHike` has been in the
   *  store since #788 with nothing calling it, so every hike kept the
   *  "A new long hike" that `handleNewHike` invents at creation. */
  onRenameHike?: (name: string) => void
  onOpenHike: () => void
  onOpenTrip: (id: string) => void
  onOpenDayHike: (id: string) => void
  onAllTrips: () => void
  onAddDayHikeToHike?: () => void
  /**
   * Move a section into this hike, or out of it (#1367).
   *
   * THE PAIR, NOT ONE HALF. `assignTrip` and `unassignTrip` have both been in
   * the store since #788 and only the first was reachable, so a section could
   * join a hike and never leave one - the only escape being "Forget this
   * hike", which ungroups every section in it. A sledgehammer for a one-row
   * mistake, and the exact asymmetry `unassignTrip`'s own docstring warns
   * about.
   *
   * It is also what makes the two shelves below mean anything. "Sections in
   * this hike" and "Your other sections" described a division a hiker could
   * see and not change; with these they are two halves of one control.
   */
  onAddSectionToHike?: (tripId: string) => void
  onTakeSectionOut?: (tripId: string) => void
  onNewTrip: () => void
  onResumeDraft: () => void
}

/**
 * PLAN, IN THE LONG-HIKE STATE (handoff §4, built by #1329).
 *
 * #1317 bound this tab to `hikerMode` and stopped there: picking Long hike
 * moved a hiker into the sections room, which is the same generic "Your
 * hikes / Recent sections" list it was before, and says nothing about the
 * hike they are on. A maintainer's report of that was "when I save a long
 * hike, it is not displaying anywhere" - and it was two defects wearing one
 * sentence. The other was a contrast bug on Today (desktop.css); this is the
 * missing room.
 *
 * WHAT THE ROOM IS FOR: a hiker on a long hike opening Plan is not browsing
 * a library, they are looking at one hike. So the band carries its NAME, the
 * shelves are its own sections and the day hikes on its trail, and the
 * figures are the two this app is allowed to print.
 *
 * TWO FIGURES AND A TWO-BAND BAR, and no third band. `features/SEGMENTS.md`
 * has a derived-gap idea; the handoff overrides it here in as many words -
 * "Gaps are never computed. No gap rows, no gap arithmetic, no dashed gap
 * band" - and the bar below is walked and to-go, nothing else. The
 * anti-gamification rule (OurHikeValues.md #1) is the same rule seen from
 * the other side: a percentage, a streak, an "on track" or another hiker's
 * hike would all be this bar wearing a number, and Plan's guard test covers
 * this surface.
 */
function HikeRoom({
  hike,
  trips,
  dayHikes,
  pois,
  units,
  draftKind,
  onSwitchHike,
  onRenameHike,
  sectionPlanner,
  onAddSectionToHike,
  onTakeSectionOut,
  onOpenHike,
  onOpenTrip,
  onOpenDayHike,
  onAllTrips,
  onAddDayHikeToHike,
  onNewTrip,
  onResumeDraft,
}: HikeRoomProps) {
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState('')
  const figures = hikeFigures(hike, trips, pois)
  const sections = trips.filter((trip) => hike.tripIds.includes(trip.id))
  /**
   * The sections that are NOT in this hike, on their own shelf.
   *
   * The handoff draws one list here and assumes the other is empty. It is
   * not, and cannot be yet: nothing in the app puts a PLANNED section into a
   * hike. `assignTrip` exists and has exactly one caller - the "add a day
   * hike to this hike" sheet - so a hiker who takes this room's own primary
   * action, lays out the next section and comes back finds it nowhere.
   * Which is the report this whole issue started from, one level down.
   *
   * The fix is NOT to attach it automatically on the way out of the route
   * builder. `unassignTrip` has no caller at all, so an automatic join would
   * be a one-way door: the only way back out would be "Forget this hike",
   * which ungroups every section in it. Better a shelf that shows a hiker
   * their own trip than a claim about it they cannot take back.
   *
   * The missing pair - a row that adds a section to the hike, and one that
   * takes it out - is named in #1329's body rather than built here.
   */
  const loose = trips.filter((trip) => !hike.tripIds.includes(trip.id))

  return (
    <div className="plan-home plan-home--trips">
      <header className="plan-band plan-band--trips">
        <div className="plan-band__words">
          <span className="plan-band__eyebrow">you&rsquo;re planning</span>
          {/* The HIKE'S name, not the room's word. It is the one thing on
              this screen that says which of somebody's hikes they are
              looking at, and #1317 left it off every Plan surface. */}
          <h1 className="plan-band__word">{hike.name}</h1>
        </div>
        {/* THE SWITCH THE HANDOFF DREW, POINTED SOMEWHERE ELSE, and the
            deviation is deliberate rather than a mis-transcription. §4 gives
            this button "The hike ›" and opens the hike's own detail - which
            is real and already built (`HikeZoom`, #790), and is what "Carry
            on with" below opens, one row down and with the hike's name on
            it rather than an 11px chip.
            
            What had no door at all was moving BETWEEN hikes. `activeHikeId`
            could be set exactly once, by the pick sheet, and the pick sheet
            only opened where no hike was active - so a hiker with two hikes
            was stuck on whichever they picked first. That is the gap this
            button fills, and it opens the same sheet rather than a second
            list of the same hikes. */}
        {onSwitchHike !== undefined && (
          <button type="button" className="plan-band__switch" onClick={onSwitchHike}>
            Switch hike ›
          </button>
        )}
      </header>

      <section className="plan-home__section">
        <div className="plan-home__section-head">
          <span className="plan-home__title">Carry on with</span>
          {/* HERE RATHER THAN IN THE BAND, which already carries the switch:
              two controls either side of an `h1` is a header a thumb cannot
              hit reliably, and renaming is a rarer act than switching. This
              is `TripList`'s rename idiom at the hike's grain - the same
              swap-the-row-for-a-field shape, so the two do not read as two
              different features. */}
          {onRenameHike !== undefined && (
            <button
              type="button"
              className="plan-home__all"
              onClick={() => {
                setDraftName(hike.name)
                setRenaming(true)
              }}
            >
              Rename ›
            </button>
          )}
        </div>
        {renaming && onRenameHike !== undefined ? (
          <div className="trip-list__rename">
            <input
              type="text"
              className="trip-list__rename-input"
              autoFocus
              value={draftName}
              aria-label={`New name for ${hike.name}`}
              onChange={(event) => setDraftName(event.target.value)}
            />
            <button
              type="button"
              className="trip-list__action"
              onClick={() => {
                // An empty name is not refused here, exactly as `renameTrip`'s
                // field does not refuse one: `renameHike` keeps the old name
                // rather than storing a blank, so a cleared field cannot
                // leave a hike nobody can identify.
                onRenameHike(draftName)
                setRenaming(false)
              }}
            >
              Save
            </button>
          </div>
        ) : (
          <button type="button" className="plan-home__open" onClick={onOpenHike}>
            <span className="plan-home__open-name">{hike.name}</span>
            <span className="plan-home__meta">
              {hikeStateLine(hike, sections.length)}
            </span>
          </button>
        )}
      </section>

      <section className="plan-home__section">
        <span className="plan-home__title">This hike, end to end</span>
        <div className="plan-home__row plan-home__row--figures">
          <span className="plan-home__meta">
            {formatDistance(figures.walkedMi, units)} walked ·{' '}
            {formatDistance(figures.leftMi, units)} to go
          </span>
          {/* TWO BANDS, and it is a picture of those two figures rather
              than a second claim. Drawn only where the hike HAS an end to
              end: a hike whose points nobody could resolve has no total, and
              a full-width grey bar under two zeroes would be an illustration
              of an absence. `aria-hidden` because the line above it already
              says everything this says, in words. */}
          {figures.totalMi > 0 && (
            <span className="plan-home__bar" aria-hidden="true">
              <span
                className="plan-home__bar-walked"
                style={{ flex: figures.walkedMi }}
              />
              <span className="plan-home__bar-left" style={{ flex: figures.leftMi }} />
            </span>
          )}
          {figures.uncertain && (
            // #788's rule, said where the figure is: a point that could not
            // be re-resolved against this phone's POIs is a mile the total
            // may be wrong about, and an unqualified total would be the
            // display outrunning its source.
            <span className="plan-home__meta">
              One of this hike&rsquo;s points isn&rsquo;t on this phone&rsquo;s map yet,
              so the total is what the miles say rather than the places.
            </span>
          )}
        </div>
      </section>

      {sections.length > 0 && (
        <section className="plan-home__section">
          <div className="plan-home__section-head">
            <span className="plan-home__title">Sections in this hike</span>
            <button type="button" className="plan-home__all" onClick={onAllTrips}>
              All {trips.length} ›
            </button>
          </div>
          {sections.map((trip) => (
            <SectionRow
              key={trip.id}
              trip={trip}
              onOpen={() => onOpenTrip(trip.id)}
              move={
                onTakeSectionOut === undefined
                  ? null
                  : {
                      label: 'Take out',
                      // Says what survives, because the neighbouring word for
                      // removing things from a hike is "Forget this hike",
                      // which is a much bigger act. Nothing about the section
                      // itself changes - #788's rule, on the button.
                      hint: `Take ${trip.name} out of this hike — the section stays in Plan`,
                      onMove: () => onTakeSectionOut(trip.id),
                    }
              }
            />
          ))}
        </section>
      )}

      {sections.length === 0 && (
        <p className="plan-home__quiet-note">
          No sections on this hike yet. Plan one below, or add a day hike you have already
          walked on this trail.
        </p>
      )}

      {loose.length > 0 && (
        <section className="plan-home__section">
          <div className="plan-home__section-head">
            <span className="plan-home__title">Your other sections</span>
            <button type="button" className="plan-home__all" onClick={onAllTrips}>
              All {trips.length} ›
            </button>
          </div>
          {loose.slice(0, RECENT_TRIPS).map((trip) => (
            <SectionRow
              key={trip.id}
              trip={trip}
              onOpen={() => onOpenTrip(trip.id)}
              move={
                onAddSectionToHike === undefined
                  ? null
                  : {
                      label: 'Add',
                      hint: `Add ${trip.name} to this hike`,
                      onMove: () => onAddSectionToHike(trip.id),
                    }
              }
            />
          ))}
        </section>
      )}

      {dayHikes.length > 0 && (
        <section className="plan-home__section">
          <div className="plan-home__title">Day hikes on this trail</div>
          {[...splitDayHikes(dayHikes).walked, ...splitDayHikes(dayHikes).toWalk]
            .slice(0, RECENT_DAY_HIKES)
            .map((dayHike) => (
              <button
                type="button"
                className="plan-home__row"
                key={dayHike.id}
                onClick={() => onOpenDayHike(dayHike.id)}
              >
                <span className="plan-home__row-name">{dayHike.name}</span>
                <span className="plan-home__meta">
                  {formatDistance(dayHike.figures.miles, units)} ·{' '}
                  {dayHike.date !== null ? dayLongDateLabel(dayHike.date) : 'no date yet'}
                </span>
              </button>
            ))}
        </section>
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

      {/* THE PLANNER TAKES THE PRIMARY'S PLACE rather than opening over it.
          One thing at a time in one column: a button that opened a panel and
          then sat under it would be a second way to do what the panel is
          already doing. */}
      {sectionPlanner !== undefined ? (
        sectionPlanner
      ) : (
        <>
          {draftKind === 'day' && (
            <p className="plan-home__refused" role="note">
              There&rsquo;s an unfinished day hike on the map. Starting a section drops
              it.
            </p>
          )}
          <button
            type="button"
            className="plan__primary"
            onClick={draftKind === 'trip' ? onResumeDraft : onNewTrip}
          >
            {/* "A section" rather than "the next section": a hiker can plan
                one anywhere on the hike, and #1344's ask was the plainer
                word. */}
            {draftKind === 'trip' ? 'Back to your route' : 'Plan a section'}
          </button>
        </>
      )}
    </div>
  )
}

/**
 * One section on the hike room's two shelves (#1367).
 *
 * A CONTAINER RATHER THAN A BUTTON, which is the whole reason this exists.
 * The rows were `<button>`s, and a row that can also be moved needs a second
 * control - a button inside a button is not markup a browser will render.
 * `TripList`'s `.trip-list__item` has had this shape since it grew a Rename,
 * so this is that shape at the section's grain rather than a new idea.
 *
 * `move` is null where the shell offers no move: on a room with no hike to
 * move into or out of, the row is exactly what it was. Never a control that
 * does nothing (LineSheet's rule).
 */
function SectionRow({
  trip,
  onOpen,
  move,
}: {
  trip: Trip
  onOpen: () => void
  move: { label: string; hint: string; onMove: () => void } | null
}) {
  return (
    <div className="plan-home__row plan-home__row--movable">
      <button type="button" className="plan-home__row-open" onClick={onOpen}>
        <span className="plan-home__row-name">{trip.name}</span>
        <span className="plan-home__meta">
          {[
            tripDateRange(planDayViews(trip.plan).map((day) => day.date)) ??
              'no dates yet',
            // The provenance line the handoff asks for, at the grain the
            // model actually holds: `recorded` is a real field (#789) and
            // says the walking was remembered rather than logged. "walking
            // now · day 6 of 14" is not - nothing stores which section is
            // under way - so it is left unsaid rather than guessed at.
            trip.recorded === true ? 'recorded from memory' : null,
          ]
            .filter((part) => part !== null)
            .join(' · ')}
        </span>
      </button>
      {move !== null && (
        <button
          type="button"
          className="plan-home__row-move"
          // The visible word is two syllables because the row is narrow; the
          // accessible name is the whole sentence, including what survives.
          aria-label={move.hint}
          onClick={move.onMove}
        >
          {move.label}
        </button>
      )}
    </div>
  )
}

/**
 * `walking · 4 sections`, `paused at mi 1,407.2`, `finished`.
 *
 * The hike's own state in the words the rest of the app uses for it, and
 * NOT the handoff's `day 6 of 14 · 3-16 Sep`: nothing in the model stores
 * which day of a hike today is, so that line would be arithmetic on dates a
 * hike is not required to carry. A hike with no dated points is normal
 * rather than incomplete (decision #10), and a made-up day number on the one
 * row whose job is to say which hike this is would be the display outrunning
 * its source.
 */
function hikeStateLine(hike: Hike, sectionCount: number): string {
  if (hike.status === 'paused' && hike.pausedAtMile !== undefined) {
    return `paused at mi ${hike.pausedAtMile.toLocaleString('en-US', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })}`
  }
  const sections = `${sectionCount} ${sectionCount === 1 ? 'section' : 'sections'}`
  return hike.status === 'finished'
    ? `finished · ${sections}`
    : `${hike.status} · ${sections}`
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
