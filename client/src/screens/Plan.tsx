// The Plan tab (#756): the multi-day plan as a timeline of terrain rows -
// wireframe 1b, the treatment marked CHOSEN, at phone width.
//
// The one physical encoding: ROW HEIGHT = WALKING HOURS
// (lib/planDisplay.ts), so a hard day is bigger on the screen and a
// section's shape can be felt by scrolling it. Each walking row carries its
// own slice of the published elevation profile, drawn with the elevation
// ribbon's geometry - and, like the ribbon, normalised to its own window:
// the silhouette is shape, the printed figures are the numbers.
//
// WHAT IS DELIBERATELY NOT HERE, because this surface is where it would
// arrive uninvited (V2_PLAN.md group T's standing trap): no progress bar,
// no "behind schedule", no comparison of any day against the plan, no
// score. A walked day greys into a record rather than scoring against its
// target; "was 17.1 mi" after a cascade is a fact about the plan, never a
// verdict on the hiker. A zero says "no walking" - terrain, not judgement.
//
// A SCREEN, NOT A DIALOG - it replaces the map when its tab is active, so
// there is nothing behind it to dim (HikePicker.tsx's convention). The
// sheets it hosts (a tapped day's actions, call-it-a-day, the cascade, the
// target sheet the shell passes in) dock to the screen's own bottom edge.

import { useMemo, useState, type ReactNode } from 'react'
import {
  callableEnd,
  callItADay,
  cascadeChoices,
  nearestStop,
  type CalledEnd,
} from '../lib/cascade'
import { ribbonSamples, type ElevationProfile } from '../lib/elevationProfile'
import type { Hike, HikePiece, PlaceRef } from '../lib/hikes'
import type { TripGroup } from '../lib/tripGroups'
import { formatNaismithMinutes } from '../lib/naismith'
import {
  currentDayIndex,
  foodCarries,
  LONG_CARRY_DAYS,
  planDayViews,
  planSections,
  planDirection,
  setDayNote,
  walkedDayCount,
  type HikePlan,
  type PlanDayView,
  type PlanSection,
} from '../lib/plan'
import {
  dayDateLabel,
  dayRowHeight,
  MIN_ROW_PX,
  stopLabel,
  tripRowHeight,
} from '../lib/planDisplay'
import { legFigures, type LegFigures } from '../lib/route'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'
import { STANDARD_PACE, paceEstimate, type PaceProfile } from '../lib/pace'
import { DaySummary } from './DaySummary'
import { HikeZoom } from './HikeZoom'
import { PlanHome } from './PlanHome'
import { WhatsLeft } from './WhatsLeft'
import './plan.css'

/**
 * The Plan tab's three depths (#790), which are features/SEGMENTS.md's tree
 * with a control on it: a Hike holds trips, a trip holds sections, a
 * section holds days.
 *
 * The middle one is not invented here - HIKE_PLANNING.md already derives a
 * section from where resupply happens, and SEGMENTS.md already names "by
 * resupply stretch" as the optional middle tier a thru-hiker adds when the
 * day list gets too long to hold. This is that tier, shown rather than
 * stored.
 */
export type PlanZoom = 'hike' | 'trip' | 'days'

const ZOOM_LABEL: Record<PlanZoom, string> = {
  hike: 'Hike',
  trip: 'Trip',
  days: 'Days',
}

export interface PlanScreenProps {
  plan: HikePlan | null
  /** The published profile, for row heights and terrain slices. Null - an
   *  old download - drops the terrain and the hour-proportional heights
   *  rather than faking either. */
  elevation: ElevationProfile | null
  /** Every stored POI - the cascade's candidate stops, and how a called
   *  day's end gets a name. */
  pois: readonly StoredPoi[]
  /** Where the hiker is on the pipeline's mile axis, or null without a fix
   *  - "call it a day where you are" is only offered when this is known. */
  gpsMile: number | null
  units: UnitSystem
  /** The hiker's own pace (#880). Every figure this screen prints - day
   *  lengths, the walking-hours target - is measured with it, so a plan and
   *  the sheets it opens never disagree about the same day. */
  pace?: PaceProfile
  /** A route draft is in progress on the map - the empty state's button
   *  reads as a way back to it rather than a fresh start, because opening
   *  the builder reopens the draft where it stood. */
  draftLive: boolean
  /** Open the route builder on the map - the empty state's one action. */
  onStartOnMap: () => void
  /** Reopen the target sheet over this plan's route. */
  onChangeTarget: () => void
  onInsertZeroAfter: (dayIndex: number) => void
  onRemoveDay: (dayIndex: number) => void
  onTogglePinned: (dayIndex: number) => void
  /** Flip resupply on the stop day `dayIndex` ends at. */
  onToggleEndResupply: (dayIndex: number) => void
  /** The cascade hands back a whole re-planned plan rather than an edit. */
  onReplacePlan: (plan: HikePlan) => void
  onDeletePlan: () => void
  /** The open trip's name, or null when nothing is open (#787). */
  tripName: string | null
  /** Its id, so the hike zoom can mark which of its rows is the one open
   *  underneath. */
  openTripId: string | null
  /** How many trips are kept. The switcher is offered whenever a hiker has
   *  anything to switch between - and from the empty state too, so a plan
   *  deleted by accident is one tap from being reopened rather than gone. */
  tripCount: number
  onOpenTrips: () => void
  /** The target sheet, when the shell has it open over this screen. */
  targetSheet?: ReactNode
  /** The trip switcher, when the shell has it open over this screen. */
  tripList?: ReactNode
  /** The hike the open trip belongs to, or null (#790). Null is the common
   *  case and not a degraded one: a hiker planning one trip has no hike to
   *  zoom out to, and the control does not offer them one. */
  hike: Hike | null
  /** Every kept trip - the hike zoom's rows. */
  trips: readonly Trip[]
  onOpenTrip: (id: string) => void
  /** Every hike and group, for the home (#805). */
  hikes: readonly Hike[]
  groups: readonly TripGroup[]
  onOpenGroup: (id: string) => void
  /** Start a route from the beginning of a stretch nobody has walked. */
  onPlanGap: (gap: Extract<HikePiece, { kind: 'gap' }>) => void
  /** Start a route at one end of a gap, walking toward the other (#791).
   *  Which end is the start is the hiker's pick; the direction follows. */
  onPlanFrom: (start: PlaceRef, toward: PlaceRef) => void
}

export function PlanScreen({
  plan,
  elevation,
  pois,
  gpsMile,
  units,
  pace = STANDARD_PACE,
  draftLive,
  onStartOnMap,
  onChangeTarget,
  onInsertZeroAfter,
  onRemoveDay,
  onTogglePinned,
  onToggleEndResupply,
  onReplacePlan,
  onDeletePlan,
  tripName,
  openTripId,
  tripCount,
  onOpenTrips,
  targetSheet,
  tripList,
  hike,
  trips,
  onOpenTrip,
  hikes,
  groups,
  onOpenGroup,
  onPlanGap,
  onPlanFrom,
}: PlanScreenProps) {
  const [selectedDay, setSelectedDay] = useState<number | null>(null)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  /** The day a "call it a day" sheet is open for, and then the day whose
   *  cascade choice is pending. Two states because the second only exists
   *  when the recorded end moved something. */
  const [calling, setCalling] = useState<number | null>(null)
  const [cascading, setCascading] = useState(false)
  /** The walked day whose summary is open (#966), or null. Its own state
   *  rather than a mode on `selectedDay`, because the two are opened by
   *  different rows and one of them is a record with no actions on it. */
  const [summaryDay, setSummaryDay] = useState<number | null>(null)
  /** The day whose summary opens once the cascade choice is made. The card
   *  belongs at the END of calling a day, and when a cascade is offered the
   *  end is one sheet later. */
  const [summaryAfterCascade, setSummaryAfterCascade] = useState<number | null>(null)
  const [zoomWanted, setZoomWanted] = useState<PlanZoom>('days')
  const [whatsLeftOpen, setWhatsLeftOpen] = useState(false)
  /**
   * The tab opens on its home when there is something to choose between
   * (#805) - and straight into the plan when there is not, because a hiker
   * with one trip should not tap twice to reach the timeline they used to
   * land on.
   */
  const [atHome, setAtHome] = useState(trips.length > 1 || hikes.length > 0)

  const views = useMemo(() => (plan === null ? [] : planDayViews(plan)), [plan])
  const sections = useMemo(() => planSections(views), [views])

  // One figures pass for every walking day - heights, terrain and labels all
  // read from it, so they cannot disagree about what a day costs.
  const figures = useMemo(() => {
    const byIndex = new Map<number, LegFigures>()
    if (elevation === null) return byIndex
    for (const day of views) {
      if (!day.zero) {
        byIndex.set(day.index, legFigures(elevation, day.start.mile, day.end.mile, pace))
      }
    }
    return byIndex
  }, [views, elevation])

  // What the cascade can honestly offer. A walking-hours target on a
  // download with no profile cannot price a shift, so it is not offered -
  // the target sheet's own refusal, applied here too. Above the empty-state
  // return because a hook must run on every render.
  const plannerContext = useMemo(() => {
    if (plan === null) return { options: {}, target: null as number | null }
    if (!('walkingHours' in plan.target)) {
      return { options: {}, target: plan.target.miles as number | null }
    }
    if (elevation === null) return { options: {}, target: null as number | null }
    return {
      options: {
        effort: (from: { mile: number }, to: { mile: number }) =>
          legFigures(elevation, from.mile, to.mile, pace).minutes / 60,
      },
      target: plan.target.walkingHours as number | null,
    }
  }, [plan, elevation])

  if (atHome && (trips.length > 1 || hikes.length > 0)) {
    return (
      <div className="plan">
        <PlanHome
          trips={trips}
          hikes={hikes}
          groups={groups}
          pois={pois}
          units={units}
          openTrip={trips.find((trip) => trip.id === openTripId) ?? null}
          draftLive={draftLive}
          onOpenTrip={(id) => {
            onOpenTrip(id)
            setZoomWanted('days')
            setAtHome(false)
          }}
          onOpenHike={() => {
            setZoomWanted('hike')
            setAtHome(false)
          }}
          onOpenGroup={onOpenGroup}
          onAllTrips={onOpenTrips}
          onNewTrip={onStartOnMap}
        />
        {targetSheet}
        {tripList}
      </div>
    )
  }

  // Which depths this hiker actually has. A zoom is offered only when it
  // shows something the one below it does not - no hike means no Hike
  // button, and a plan with one section has nothing for the Trip zoom to
  // say that the Days zoom does not. The alternative is a control with dead
  // segments on it, which the route builder's own entrance was reworked to
  // get rid of.
  const available: PlanZoom[] = [
    ...(hike === null ? [] : (['hike'] as PlanZoom[])),
    ...(sections.length > 1 ? (['trip'] as PlanZoom[]) : []),
    ...(plan === null || views.length === 0 ? [] : (['days'] as PlanZoom[])),
  ]
  const zoom: PlanZoom = available.includes(zoomWanted)
    ? zoomWanted
    : (available[0] ?? 'days')

  // The bar carries the way back to the home as well as the zooms, so a
  // hiker with several trips and only one depth still has one (#805).
  const canGoHome = trips.length > 1 || hikes.length > 0
  const zoomBar =
    available.length > 1 || canGoHome ? (
      <div className="plan__zoombar">
        {canGoHome && (
          <button type="button" className="plan__crumb" onClick={() => setAtHome(true)}>
            <span className="plan__crumb-up">&lsaquo; All your plans</span>
          </button>
        )}
        {hike !== null && zoom !== 'hike' && (
          <button
            type="button"
            className="plan__crumb"
            onClick={() => setZoomWanted('hike')}
          >
            <span className="plan__crumb-up">&lsaquo; {hike.name}</span>
          </button>
        )}
        {available.length > 1 && (
          <div className="plan__zooms" role="group" aria-label="Zoom">
            {available.map((level) => (
              <button
                key={level}
                type="button"
                className={level === zoom ? 'plan__zoom plan__zoom--on' : 'plan__zoom'}
                aria-pressed={level === zoom}
                onClick={() => setZoomWanted(level)}
              >
                {ZOOM_LABEL[level]}
              </button>
            ))}
          </div>
        )}
      </div>
    ) : null

  // The hike, whether or not a trip is open under it. A hiker who deleted
  // the plan they had open still has years of walked trail and a set of
  // gaps, and sending them to "No plan yet" would be the screen forgetting
  // what it knows.
  if (zoom === 'hike' && hike !== null) {
    return (
      <div className="plan">
        <header className="plan__head">
          <h1 className="plan__title">{hike.name}</h1>
          <span className="plan__head-note">{hike.type}</span>
          <button type="button" className="plan__trips" onClick={onOpenTrips}>
            {tripCount > 1 ? `All ${tripCount} trips` : 'Your trips'}
          </button>
        </header>
        {zoomBar}
        {whatsLeftOpen ? (
          <WhatsLeft
            hike={hike}
            trips={trips}
            pois={pois}
            units={units}
            gpsMile={gpsMile}
            onPlanFrom={onPlanFrom}
            onClose={() => setWhatsLeftOpen(false)}
          />
        ) : (
          <>
            <HikeZoom
              hike={hike}
              trips={trips}
              pois={pois}
              units={units}
              gpsMile={gpsMile}
              openTripId={openTripId}
              onOpenTrip={(id) => {
                onOpenTrip(id)
                setZoomWanted('days')
              }}
              onPlanGap={onPlanGap}
              onWhatsLeft={() => setWhatsLeftOpen(true)}
            />
            <button type="button" className="plan__primary" onClick={onStartOnMap}>
              {draftLive ? 'Back to your route' : 'Plan another trip'}
            </button>
          </>
        )}
        {targetSheet}
        {tripList}
      </div>
    )
  }

  if (plan === null || views.length === 0) {
    return (
      <div className="plan">
        <header className="plan__head">
          <h1 className="plan__title">Plan</h1>
          {tripCount > 0 ? (
            <button type="button" className="plan__trips" onClick={onOpenTrips}>
              {tripCount} kept
            </button>
          ) : (
            <span className="plan__head-note">nothing saved</span>
          )}
        </header>

        <div className="plan__empty">
          {/* Three blazes, decoration only - the app's own voice lives in
              the words beside them. */}
          <div className="plan__blazes" aria-hidden="true">
            <span className="plan__blaze plan__blaze--white" />
            <span className="plan__blaze plan__blaze--orange" />
            <span className="plan__blaze plan__blaze--blue" />
          </div>
          <p className="plan__empty-voice">
            No plan yet. You could just walk north and find out.
          </p>
          <p className="plan__empty-note">
            Or say where from and how far, and it&rsquo;ll find the stretch and break it
            into days.
          </p>
          <button type="button" className="plan__primary" onClick={onStartOnMap}>
            {draftLive ? 'Back to your route' : 'Start on the map'}
          </button>
        </div>
        {targetSheet}
        {tripList}
      </div>
    )
  }

  const direction = planDirection(plan)
  const selected = selectedDay === null ? null : (views[selectedDay] ?? null)
  const current = currentDayIndex(plan)
  const anythingWalked = walkedDayCount(plan) > 0

  return (
    <div className="plan">
      <header className="plan__head">
        <h1 className="plan__title">
          {/* The trip's own name once it has one - a hiker who renamed it
              "Grayson week" should read that back, not have it silently
              replaced by the ends it was named from. */}
          {tripName ??
            `${stopLabel(views[0].start)} → ${stopLabel(views[views.length - 1].end)}`}
        </h1>
        <span className="plan__head-note">
          {direction === null ? '' : `${direction} · `}
          {views.length} days
          {finishLabel(views) === null ? '' : ` · finish ≈ ${finishLabel(views)}`}
        </span>
        <button type="button" className="plan__trips" onClick={onOpenTrips}>
          {tripCount > 1 ? `All ${tripCount} trips` : 'Your trips'}
        </button>
      </header>

      {zoomBar}

      {zoom === 'trip' && (
        // This trip's sections - where supplies come from, which is the tier
        // SEGMENTS.md names and HIKE_PLANNING.md already derives. Same
        // encoding again: a section row is as tall as its days.
        <ol className="plan__sections">
          {sections.map((section, sectionIndex) => (
            <li key={section.days[0].id}>
              <button
                type="button"
                className="plan__section-row"
                style={{ height: `${tripRowHeight(section.days.length)}px` }}
                onClick={() => setZoomWanted('days')}
              >
                <span className="plan__section-title-row">
                  <span className="plan__section-title">
                    {stopLabel(section.days[0].start)} →{' '}
                    {stopLabel(section.days[section.days.length - 1].end)}
                  </span>
                  <span className="plan__section-count">
                    SEC {sectionIndex + 1}/{sections.length}
                  </span>
                </span>
                <span className="plan__section-stats">
                  <span>{formatDistance(section.distanceMi, units, 'whole')}</span>
                  <span>
                    {section.days.length} {section.days.length === 1 ? 'day' : 'days'}
                  </span>
                  {section.days[section.days.length - 1].end.resupply && (
                    <span className="plan__section-food">
                      {section.foodDays} days food
                    </span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}

      {zoom === 'days' && elevation !== null && (
        <p className="plan__legend">
          <span className="plan__legend-swatch" aria-hidden="true" />
          row height = walking hours
        </p>
      )}

      {zoom === 'days' &&
        sections.map((section, sectionIndex) => (
          <section className="plan__section" key={section.days[0].id}>
            <header className="plan__section-head">
              <div className="plan__section-title-row">
                <h2 className="plan__section-title">
                  {stopLabel(section.days[0].start)} →{' '}
                  {stopLabel(section.days[section.days.length - 1].end)}
                </h2>
                {sections.length > 1 && (
                  <span className="plan__section-count">
                    SEC {sectionIndex + 1}/{sections.length}
                  </span>
                )}
              </div>
              <p className="plan__section-stats">
                <span>{formatDistance(section.distanceMi, units, 'whole')}</span>
                <span>{section.days.length} days</span>
                {sectionAscent(section, figures) !== null && (
                  <span>
                    {formatElevation(sectionAscent(section, figures) as number, units)} ↑
                  </span>
                )}
                {section.days[section.days.length - 1].end.resupply && (
                  <span className="plan__section-food">{section.foodDays} days food</span>
                )}
              </p>
            </header>

            <ol className="plan__days">
              {section.days.map((day) => (
                <li key={day.id}>
                  <DayRow
                    day={day}
                    figures={figures.get(day.index)}
                    carryOut={
                      day.end.resupply
                        ? (sections[sectionIndex + 1]?.foodDays ?? null)
                        : null
                    }
                    units={units}
                    elevation={elevation}
                    onSelect={() =>
                      // A walked day has no actions on it and never gains
                      // any - it opens its own record instead (#966).
                      day.walked ? setSummaryDay(day.index) : setSelectedDay(day.index)
                    }
                  />
                </li>
              ))}
            </ol>
          </section>
        ))}

      {/* Days of food are days in every unit system, so this block takes no
          units - the one figure on the Plan tab that does not convert. */}
      {zoom !== 'hike' && <FoodBlock sections={sections} />}

      <div className="plan__foot">
        {/* Re-targeting replaces the whole plan, so it retires the moment
            anything is walked - the past is a record a wholesale re-lay
            would overwrite, and re-planning what remains is the cascade's. */}
        {!anythingWalked && (
          <button type="button" className="plan__foot-action" onClick={onChangeTarget}>
            {targetLabel(plan, units)}
          </button>
        )}
        <button
          type="button"
          className="plan__foot-action plan__foot-action--danger"
          onClick={() => {
            if (!confirmingDelete) {
              setConfirmingDelete(true)
              return
            }
            setConfirmingDelete(false)
            onDeletePlan()
          }}
        >
          {confirmingDelete ? 'Tap again to delete the plan' : 'Delete plan'}
        </button>
      </div>

      {selected !== null && !cascading && calling === null && (
        <DayActions
          day={selected}
          isCurrent={selected.index === current}
          onCallItADay={() => {
            setCalling(selected.index)
            setSelectedDay(null)
          }}
          onInsertZeroAfter={() => {
            onInsertZeroAfter(selected.index)
            setSelectedDay(null)
          }}
          onRemoveDay={() => {
            onRemoveDay(selected.index)
            setSelectedDay(null)
          }}
          onTogglePinned={() => {
            onTogglePinned(selected.index)
            setSelectedDay(null)
          }}
          onToggleEndResupply={() => {
            onToggleEndResupply(selected.index)
            setSelectedDay(null)
          }}
          onClose={() => setSelectedDay(null)}
        />
      )}

      {calling !== null && views[calling] !== undefined && (
        <CallItADaySheet
          plan={plan}
          day={views[calling]}
          pois={pois}
          gpsMile={gpsMile}
          elevation={elevation}
          units={units}
          pace={pace}
          onCall={(end) => {
            const called = callItADay(plan, calling, end)
            setCalling(null)
            if (called === plan) return
            onReplacePlan(called)
            // The choice sheet only exists when the recorded end moved
            // something - ending exactly at the planned stop changes no
            // later day, and asking would be the "recalculate?" prompt the
            // design forbids.
            if (end.mile !== plan.stops[calling + 1].mile) {
              setCascading(true)
              setSummaryAfterCascade(calling)
            } else {
              setSummaryDay(calling)
            }
          }}
          onClose={() => setCalling(null)}
        />
      )}

      {cascading && (
        <CascadeSheet
          plan={plan}
          pois={pois}
          target={plannerContext.target}
          options={plannerContext.options}
          units={units}
          onChoose={(next) => {
            if (next !== null) onReplacePlan(next)
            setCascading(false)
            setSummaryDay(summaryAfterCascade)
            setSummaryAfterCascade(null)
          }}
        />
      )}
      {summaryDay !== null && views[summaryDay] !== undefined && (
        <DaySummary
          day={views[summaryDay]}
          figures={figures.get(summaryDay)}
          pois={pois}
          units={units}
          nextDayWalked={views[summaryDay + 1]?.walked === true}
          onNextDay={() => setSummaryDay(summaryDay + 1)}
          onKeepNote={(note) => {
            const kept = setDayNote(plan, summaryDay, note)
            if (kept !== plan) onReplacePlan(kept)
            setSummaryDay(null)
          }}
          onClose={() => setSummaryDay(null)}
        />
      )}

      {targetSheet}
      {tripList}
    </div>
  )
}

/**
 * What each stretch costs in days of food (#799).
 *
 * The figures come off `planSections()` - the same derivation the timeline
 * and the trip zoom read - so the food block and the rows cannot disagree
 * about a carry. Nothing here suggests where to resupply: picking towns for
 * somebody is a much larger feature, and the resupply data is not good
 * enough for it yet.
 *
 * THE CASE THAT WAS SILENT BEFORE: a plan with no resupply anywhere never
 * printed the word food at all, which reads as "no food needed" rather than
 * "all nine days are on your back".
 */
function FoodBlock({ sections }: { sections: PlanSection[] }) {
  const carries = foodCarries(sections)
  if (carries.length === 0) return null

  const longest = carries.reduce((worst, carry) =>
    carry.days > worst.days ? carry : worst,
  )
  const nowhereToBuy = carries.length === 1 && !carries[0].restockAtEnd

  return (
    <section className="plan__food">
      <h2 className="plan__food-title">Food</h2>
      <ul className="plan__food-carries">
        {carries.map((carry) => (
          <li className="plan__food-carry" key={`${carry.from.mile}-${carry.to.mile}`}>
            <span className="plan__food-where">
              {stopLabel(carry.from)} → {stopLabel(carry.to)}
            </span>
            <span className="plan__food-days">
              {carry.days} {carry.days === 1 ? 'day' : 'days'}
              {carry.restockAtEnd ? '' : ' · nothing bought at the end'}
            </span>
          </li>
        ))}
      </ul>
      {nowhereToBuy ? (
        <p className="plan__food-note" role="note">
          No resupply on this plan — all {carries[0].days}{' '}
          {carries[0].days === 1 ? 'day' : 'days'} come out of your pack. Marking a stop
          as a resupply on the timeline splits the carry.
        </p>
      ) : (
        longest.days >= LONG_CARRY_DAYS && (
          <p className="plan__food-note" role="note">
            The longest carry is {longest.days} days, out of {stopLabel(longest.from)} —
            that is the heaviest your pack gets.
          </p>
        )
      )}
      {/* Zeros are in these counts. HIKE_PLANNING.md left it open;
          lib/plan.ts decided it in one place, erring toward carrying enough
          rather than short - and saying so is the difference between a
          number and a number you can argue with. */}
      <p className="plan__food-note plan__food-note--quiet">
        Zeros and rest days count — they eat a day of food like any other.
      </p>
    </section>
  )
}

/** The last day's date as "30 Aug", or null on an undated plan. */
function finishLabel(views: PlanDayView[]): string | null {
  const last = views[views.length - 1]?.date
  if (last === null || last === undefined) return null
  const date = new Date(`${last}T00:00:00Z`)
  const month = date.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' })
  return `${date.getUTCDate()} ${month}`
}

function sectionAscent(
  section: PlanSection,
  figures: Map<number, LegFigures>,
): number | null {
  let total = 0
  for (const day of section.days) {
    if (day.zero) continue
    const f = figures.get(day.index)
    if (f === undefined) return null
    total += f.ascentFt
  }
  return total
}

function targetLabel(plan: HikePlan, units: UnitSystem): string {
  if ('walkingHours' in plan.target) {
    return `Target: ${plan.target.walkingHours}h walking`
  }
  return `Target: ${formatDistance(plan.target.miles, units, 'trimmed')} per day`
}

interface DayRowProps {
  day: PlanDayView
  figures: LegFigures | undefined
  /** Days of food out of this row's resupply stop, or null when the row is
   *  not a resupply (or the plan ends here). */
  carryOut: number | null
  units: UnitSystem
  elevation: ElevationProfile | null
  onSelect: () => void
}

function DayRow({ day, figures, carryOut, units, elevation, onSelect }: DayRowProps) {
  const resupply = day.end.resupply

  // A walked day is a record, not a plan - grey and immutable, and there
  // are still no actions to take on the past. It became a button anyway
  // (#966): READING a day is not acting on it, and the day somebody just
  // finished is the one row on this timeline they are most likely to want
  // to open. What opens is the summary, which edits nothing about the day
  // except the line the hiker writes themselves.
  if (day.walked) {
    return (
      <div className="plan__row">
        <RowGutter day={day} />
        <button type="button" className="plan__day plan__day--walked" onClick={onSelect}>
          <span className="plan__day-top">
            <span className="plan__day-title">
              {stopLabel(day.start)} → {stopLabel(day.end)}
            </span>
            <span className="plan__day-figure">
              {formatDistance(Math.abs(day.end.mile - day.start.mile), units)}
            </span>
          </span>
          <span className="plan__day-carry plan__day-carry--walked">
            walked · not a plan any more
          </span>
          {/* The hiker's own line, back on the timeline where they will
              scroll past it months later - which is the whole reason the
              card asked them to write one. */}
          {day.note !== null && <span className="plan__day-note">{day.note}</span>}
        </button>
      </div>
    )
  }

  if (day.zero) {
    return (
      <div className="plan__row">
        <RowGutter day={day} />
        <button type="button" className="plan__day plan__day--zero" onClick={onSelect}>
          <span>Zero · {stopLabel(day.start)}</span>
          {/* Terrain, not judgement - and "rest" only where the hiker's own
              rhythm put it, never as the app's opinion of the day (#798). */}
          <span className="plan__day-figure">
            {day.rest ? 'your rest day' : 'no walking'}
          </span>
        </button>
      </div>
    )
  }

  const height = figures === undefined ? MIN_ROW_PX : dayRowHeight(figures.minutes)

  return (
    <div className="plan__row">
      <RowGutter day={day} />
      <button
        type="button"
        className={resupply ? 'plan__day plan__day--resupply' : 'plan__day'}
        style={{ height: `${height}px` }}
        onClick={onSelect}
      >
        {!resupply && elevation !== null && (
          <DayTerrain
            elevation={elevation}
            fromMile={day.start.mile}
            toMile={day.end.mile}
          />
        )}
        <span className="plan__day-top">
          <span className="plan__day-title">
            {stopLabel(day.start)} → {stopLabel(day.end)}
            {day.pinned && (
              <span className="plan__day-pin" role="img" aria-label="pinned">
                📌
              </span>
            )}
          </span>
          <span className="plan__day-figure">
            {formatDistance(Math.abs(day.end.mile - day.start.mile), units)}
          </span>
        </span>
        {resupply && carryOut !== null && (
          <span className="plan__day-carry">
            resupply · carry {carryOut} {carryOut === 1 ? 'day' : 'days'} out
          </span>
        )}
        {resupply && carryOut === null && (
          <span className="plan__day-carry">resupply</span>
        )}
        <span className="plan__day-bottom">
          {figures !== undefined && (
            <span className="plan__day-figure">
              {formatNaismithMinutes(figures.minutes)} ·{' '}
              {formatElevation(figures.ascentFt, units)} ↑
            </span>
          )}
          {day.wasDistanceMi !== null && (
            // What the cascade changed - a fact about the plan, not a
            // verdict on the hiker.
            <span className="plan__day-was">
              was {formatDistance(day.wasDistanceMi, units)}
            </span>
          )}
          {day.rest && <span className="plan__day-auto">nearo · your rest day</span>}
          {day.generated && <span className="plan__day-auto">auto</span>}
        </span>
      </button>
    </div>
  )
}

function RowGutter({ day }: { day: PlanDayView }) {
  return (
    <span className="plan__gutter">
      {day.date !== null && <span>{dayDateLabel(day.date)}</span>}
      {day.dayNumber !== null && <span>DAY {day.dayNumber}</span>}
    </span>
  )
}

const TERRAIN_W = 100
const TERRAIN_H = 40

/**
 * One day's slice of the profile, in the elevation ribbon's own geometry -
 * stretched viewBox, per-window vertical normalisation, gaps interpolated
 * in the picture only. X runs in the DIRECTION OF TRAVEL, so a southbound
 * day reads left-to-right the way it will be walked.
 */
function DayTerrain({
  elevation,
  fromMile,
  toMile,
}: {
  elevation: ElevationProfile
  fromMile: number
  toMile: number
}) {
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)
  const samples = ribbonSamples(elevation, { startMile: low, endMile: high })
  if (samples.length < 2) return null

  const southbound = toMile < fromMile
  const span = high - low
  const xFor = (mile: number) => {
    const pct = span === 0 ? 0 : ((mile - low) / span) * TERRAIN_W
    return southbound ? TERRAIN_W - pct : pct
  }

  const elevations = samples.map((s) => s.elevationFt)
  const minFt = Math.min(...elevations)
  const maxFt = Math.max(...elevations)
  const range = maxFt - minFt
  const yFor = (ft: number) =>
    range === 0 ? TERRAIN_H / 2 : TERRAIN_H - ((ft - minFt) / range) * (TERRAIN_H * 0.82)

  const ordered = southbound ? [...samples].reverse() : samples
  const line = ordered
    .map(
      (s, i) =>
        `${i === 0 ? 'M' : 'L'}${xFor(s.mile).toFixed(2)},${yFor(s.elevationFt).toFixed(2)}`,
    )
    .join(' ')
  const area = `${line} L${TERRAIN_W},${TERRAIN_H} L0,${TERRAIN_H} Z`

  return (
    <svg
      className="plan__terrain"
      viewBox={`0 0 ${TERRAIN_W} ${TERRAIN_H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={area} className="plan__terrain-area" />
      <path d={line} className="plan__terrain-line" fill="none" />
    </svg>
  )
}

interface DayActionsProps {
  day: PlanDayView
  /** Whether this is the day being walked next - the only day that can be
   *  called (#758). */
  isCurrent: boolean
  onCallItADay: () => void
  onInsertZeroAfter: () => void
  onRemoveDay: () => void
  onTogglePinned: () => void
  onToggleEndResupply: () => void
  onClose: () => void
}

/** The tapped day's actions. A sheet rather than a screen because the
 *  timeline behind it is the context for every choice on it - which day,
 *  between which neighbours. */
function DayActions({
  day,
  isCurrent,
  onCallItADay,
  onInsertZeroAfter,
  onRemoveDay,
  onTogglePinned,
  onToggleEndResupply,
  onClose,
}: DayActionsProps) {
  const where = day.zero
    ? `Zero at ${stopLabel(day.start)}`
    : `${stopLabel(day.start)} → ${stopLabel(day.end)}`

  return (
    <div className="plan__actions" role="dialog" aria-label="Day actions">
      <p className="plan__actions-title">{where}</p>
      {isCurrent && !day.zero && (
        <button type="button" className="plan__action" onClick={onCallItADay}>
          Call it a day&hellip;
        </button>
      )}
      <button type="button" className="plan__action" onClick={onInsertZeroAfter}>
        Add a zero day after this
      </button>
      {!day.zero && (
        <button type="button" className="plan__action" onClick={onToggleEndResupply}>
          {day.end.resupply
            ? `No resupply at ${stopLabel(day.end)}`
            : `Resupply at ${stopLabel(day.end)}`}
        </button>
      )}
      <button type="button" className="plan__action" onClick={onTogglePinned}>
        {day.pinned ? 'Unpin this day' : 'Pin this day — it does not move'}
      </button>
      <button type="button" className="plan__action" onClick={onRemoveDay}>
        {day.zero ? 'Remove this zero' : 'Remove this day'}
      </button>
      <button
        type="button"
        className="plan__action plan__action--quiet"
        onClick={onClose}
      >
        Cancel
      </button>
    </div>
  )
}

interface CallItADaySheetProps {
  plan: HikePlan
  day: PlanDayView
  pois: readonly StoredPoi[]
  gpsMile: number | null
  elevation: ElevationProfile | null
  units: UnitSystem
  /** The hiker's own pace (#880), so this sheet's figure agrees with the day
   *  it is closing rather than quoting a generic walker's. */
  pace?: PaceProfile
  onCall: (end: CalledEnd) => void
  onClose: () => void
}

/**
 * "Call it Day 24?" - the record half of the cascade (#758, wireframe 2b
 * frame 1), without the background inference: the hiker opens it from the
 * current day's actions, and it never pushes - the wrong-way alert stays
 * the only notification OurHike sends.
 *
 * Two honest ends are offered: the planned stop, and where the hiker
 * actually is when a fix exists - named by the nearest real stop when one
 * is close enough to say so. A position past the boundary after this one
 * cannot be recorded (lib/cascade.ts's callableEnd): that is a whole
 * overtaken day, a structural edit the cascade does not attempt, and the
 * sheet says so instead of offering a dead tap.
 */
function CallItADaySheet({
  plan,
  day,
  pois,
  gpsMile,
  elevation,
  units,
  pace = STANDARD_PACE,
  onCall,
  onClose,
}: CallItADaySheetProps) {
  const plannedEnd: CalledEnd = {
    mile: day.end.mile,
    ...(day.end.name === undefined ? {} : { name: day.end.name }),
    ...(day.end.poiId === undefined ? {} : { poiId: day.end.poiId }),
  }

  const here: CalledEnd | null =
    gpsMile === null ? null : (nearestStop(pois, gpsMile) ?? { mile: gpsMile })
  const hereCallable = here !== null && callableEnd(plan, day.index, here.mile)

  const describe = (end: CalledEnd) => {
    const distanceMi = Math.abs(end.mile - day.start.mile)
    if (elevation === null) return formatDistance(distanceMi, units)
    const figures = legFigures(elevation, day.start.mile, end.mile, pace)
    // paceEstimate rather than formatting these minutes by hand. They are
    // pace-adjusted, so this line owes its baseline (#851) - and formatting
    // them directly is the one bypass test/paceBaseline.test.ts exists to
    // catch, which is how this call site was found.
    const estimate = paceEstimate(
      { distanceMi: figures.distanceMi, ascentFt: figures.ascentFt },
      pace,
    )
    const shown = `${formatDistance(distanceMi, units)} · ${estimate.text}`
    return estimate.relativeLine === null ? shown : `${shown} (${estimate.relativeLine})`
  }

  const endLabel = (end: CalledEnd) => end.name ?? stopLabel({ mile: end.mile })

  return (
    <div className="plan__actions" role="dialog" aria-label="Call it a day">
      <p className="plan__actions-title">
        {day.dayNumber === null ? 'Call it a day?' : `Call it Day ${day.dayNumber}?`}
      </p>
      <button type="button" className="plan__action" onClick={() => onCall(plannedEnd)}>
        At {endLabel(plannedEnd)}, as planned — I&rsquo;ll write down{' '}
        {describe(plannedEnd)}
      </button>
      {here !== null && hereCallable && here.mile !== plannedEnd.mile && (
        <button type="button" className="plan__action" onClick={() => onCall(here)}>
          Where you are — {endLabel(here)} · I&rsquo;ll write down {describe(here)}
        </button>
      )}
      {here !== null && !hereCallable && (
        <p className="plan__actions-note" role="note">
          Your position is past tomorrow&rsquo;s stop, which this can&rsquo;t record yet —
          call the day at the planned stop and re-plan from there.
        </p>
      )}
      <button
        type="button"
        className="plan__action plan__action--quiet"
        onClick={onClose}
      >
        Not yet
      </button>
    </div>
  )
}

interface CascadeSheetProps {
  plan: HikePlan
  pois: readonly StoredPoi[]
  /** The plan's own target in effort units, or null when it cannot be
   *  priced honestly (hours target, no profile) - shift is not offered
   *  then. */
  target: number | null
  options: Parameters<typeof cascadeChoices>[3]
  units: UnitSystem
  /** The chosen plan, or null for "leave it". */
  onChoose: (next: HikePlan | null) => void
}

/**
 * Three outcomes, not one question (#758, wireframe 2b frame 2): every
 * consequence below is computed from the actual re-planned result, so the
 * sheet can never promise a finish the generator did not produce. Nowhere
 * here does "ahead" or "behind" appear - the day changed, and the plan can
 * follow or not; that is the whole framing.
 */
function CascadeSheet({
  plan,
  pois,
  target,
  options,
  units,
  onChoose,
}: CascadeSheetProps) {
  const choices = useMemo(
    () => cascadeChoices(plan, pois, target, options),
    [plan, pois, target, options],
  )

  const finish = finishLabel(planDayViews(plan))

  return (
    <div className="plan__actions" role="dialog" aria-label="The rest of the plan">
      <p className="plan__actions-title">
        Today changed. The days after it can follow, or not — your call.
      </p>

      {choices.absorb !== null && (
        <button
          type="button"
          className="plan__action"
          onClick={() => onChoose(choices.absorb!.plan)}
        >
          <span className="plan__choice-name">Absorb</span>
          <span className="plan__choice-line">
            {finish === null ? 'Same number of days' : `Finish ≈ ${finish}, unchanged`} ·
            the next {choices.absorb.days}{' '}
            {choices.absorb.days === 1 ? 'day averages' : 'days average'}{' '}
            {formatDistance(choices.absorb.averageMi, units)}
          </span>
        </button>
      )}

      {choices.shift !== null && (
        <button
          type="button"
          className="plan__action"
          onClick={() => onChoose(choices.shift!.plan)}
        >
          <span className="plan__choice-name">Shift</span>
          <span className="plan__choice-line">
            Same day sizes ·{' '}
            {choices.shift.finishDate === null
              ? deltaLabel(choices.shift.deltaDays)
              : `finish ≈ ${finishLabel(planDayViews(choices.shift.plan))}`}
          </span>
        </button>
      )}

      <button type="button" className="plan__action" onClick={() => onChoose(null)}>
        <span className="plan__choice-name">Leave it</span>
        <span className="plan__choice-line">
          {choices.leaveTomorrowMi === null
            ? 'Nothing after today'
            : choices.leaveTomorrowMi === 0
              ? 'Nothing changes · tomorrow is a zero'
              : `Nothing changes · tomorrow: ${formatDistance(choices.leaveTomorrowMi, units)}`}
        </span>
      </button>

      {choices.pinnedAhead > 0 && (
        <p className="plan__actions-note" role="note">
          <span aria-hidden="true">📌</span> {choices.pinnedAhead}{' '}
          {choices.pinnedAhead === 1 ? 'pinned day lies' : 'pinned days lie'} ahead —
          nothing re-plans through a pin, and shifting a pinned date is off the table.
        </p>
      )}
    </div>
  )
}

function deltaLabel(deltaDays: number): string {
  if (deltaDays === 0) return 'same number of days'
  if (deltaDays > 0) return `${deltaDays} ${deltaDays === 1 ? 'day' : 'days'} more`
  return `${-deltaDays} ${deltaDays === -1 ? 'day' : 'days'} fewer`
}
