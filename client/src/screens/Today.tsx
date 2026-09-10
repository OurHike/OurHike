// The Today screen (#1054): the redesign's home tab - a dated journal.
//
// Chronology is the hierarchy. A hiker's question is ordered by distance, so
// the screen is ordered by distance: a mile gutter down the left, one card
// per thing you will meet, in the order you will meet it. The pine chrome
// block on top carries the identity - the date, the mile, the mode - so the
// paper below it is all content.
//
// WHAT THIS SCREEN MUST STAY HONEST ABOUT, because it is the first thing a
// hiker sees every day:
//
//  - Every line degrades to silence or to a named unknown, never to a guess.
//    The status row carries the same flags the map screen admits to
//    (chrome/StatusStrip.tsx); the journal renders nothing rather than
//    ranking waypoints against a position nobody has (lib/todayJournal.ts).
//  - "AHEAD" is a claim about direction and is only printed once the
//    direction tracker has settled; before that the section says NEARBY -
//    the same honesty the ribbon's SUBJECT_LABELS keep.
//  - The greeting's time is a DURATION (≈, no descent credit), never an
//    arrival clock - lib/naismith.ts's rule, kept against the prototype's
//    own "you'll be there around 4:40" and recorded as a deviation on #1054.
//  - The closure entry carries a next step, but the step is "see it on the
//    map" - nothing in this app computes detours, so "show me the way round"
//    would be a button whose promise the data cannot keep.
//  - Nothing here counts contributions, compares days, or scores anybody
//    (OurHikeValues.md #1, screens/Volunteer.tsx's guardrail).
//
// Mode re-ranks and re-emphasises; it never hides. Every section below
// renders in every mode - what changes is the order and which card leads.

import { useMemo, type ReactNode } from 'react'
import shelterPhoto from '../design-system/assets/photos/section-shelter.jpg'
import { StatusStrip } from '../chrome/StatusStrip'
import { ModeSwitch } from '../chrome/ModeSwitch'
import { WelcomeBackCard, type WelcomeBackCardProps } from '../chrome/WelcomeBackCard'
import { ElevationRibbon, type RibbonSubject } from '../chrome/ElevationRibbon'
import type { RibbonView } from '../lib/ribbonView'
import type { HikerMode } from '../lib/hikerMode'
import type { HikeDirection } from '../chrome/Header'
import type { BackgroundProblem } from '../lib/backgroundHealth'
import type { BackgroundOverride } from '../lib/dataSaver'
import type { UnitSystem } from '../lib/userPreferences'
import type { PaceProfile } from '../lib/pace'
import { paceEstimate } from '../lib/pace'
import type { StalenessTreatment } from '../lib/stalenessDisplay'
import {
  ascentBetween,
  journalEntries,
  nextShelter,
  type JournalPoi,
} from '../lib/todayJournal'
import { formatTodayEyebrow, splitPosition, todayGreeting } from '../lib/todayText'
import { formatDistance, formatElevation } from '../lib/units'
import { localDay } from '../lib/passedToday'
import { dayLongDateLabel } from '../lib/planDisplay'
import { formatMile } from '../lib/positionLine'
import { cachedEstimate } from '../lib/dayHikeShelf'
import { typeLabel } from '../chrome/legendLabels'
import {
  opportunitiesUsable,
  upcomingWorkProjects,
  workProjectDates,
  type WorkProjectSummary,
} from '../lib/workProjects'
import type { PassedPlace } from './Volunteer'
import type { DayHike } from '../lib/dayHikes'
import type { LonLat } from '../lib/trailGraph'
import {
  shelfPicks,
  timeBucketLabel,
  type HikeFacets,
  type SuggestedHike,
} from '../lib/suggestedHikes'
import { SuggestedHikeCard } from '../chrome/SuggestedHikeCard'
import { HikeFinderIcon } from '../chrome/HikeFinderIcon'
import { Notice } from '../chrome/Notice'
import { PinnedBar } from '../chrome/PinnedBar'
import { PoiRow } from '../chrome/PoiRow'
import { FieldNoteSection, type FieldNoteContext } from '../chrome/FieldNoteSection'
import { isNoteScopedType } from '../lib/fieldNotes'
import type { NightBehind } from '../lib/nightsBehind'
import { Button } from '../design-system/components'
import '../chrome/chrome.css'
import './today.css'

const NO_SUGGESTIONS: readonly SuggestedHike[] = []

export interface TodayProps {
  now: Date
  /** The position line, already decided (lib/positionLine.ts). The big
   *  readout splits it (lib/todayText.ts) rather than recomputing it, so
   *  this header and the map plate cannot disagree about where the hiker
   *  is. */
  position: string

  // The status row: the same flags StatusStrip renders on the map screen,
  // minus the two that describe a canvas this screen does not show
  // ("Zoomed out past your download", "Alerts hidden") - a caveat about an
  // invisible viewport is a caveat nobody can act on from here. The map
  // plate still carries the full set; dropping one THERE is the regression
  // (#1054's non-negotiable), and MapScreen owns that.
  online: boolean
  hasGpsFix: boolean
  lastSyncedAt: Date | null
  conditionsAge?: string | null
  backgroundProblem?: BackgroundProblem | null
  backgroundOverride?: BackgroundOverride | null
  trailLinesMissing?: boolean

  mode: HikerMode
  onChangeMode: (mode: HikerMode) => void
  /** The pick is not settled - "Which long hike?" is open over this screen
   *  (chrome/ModeSwitch.tsx's `pending`). */
  modePending?: boolean

  /**
   * The long hike leading this screen (#1317), or null when the app is not
   * in one.
   *
   * FINISHED LINES FROM THE SHELL, like the alert sentences above and for
   * the same reason: the figures are `hikeFiguresLine`'s, computed once
   * where the store is, so this screen and the Plan tab cannot come to
   * describe the same hike differently.
   */
  longHike?: LongHikeToday | null

  /** Every searchable POI, client mile axis - the journal ranks a scoped
   *  subset (lib/todayJournal.ts). */
  pois: readonly JournalPoi[]
  /** The fix's mile on the client axis, or undefined - which empties the
   *  journal rather than ranking it from a place nobody is. */
  currentMile?: number
  direction?: HikeDirection
  /** The same presentation the lanes and the pins read
   *  (lib/stalenessDisplay.ts) - one policy, restyled here, never a fourth
   *  copy of the tiers. */
  stalenessFor?: (
    poiId: string,
    poiType: string,
  ) => { treatment: StalenessTreatment; words: string } | null
  /** Opens the entry's card on the map - the same behaviour a search result
   *  and a passed-place row have (#527): a journal row is a second way to
   *  name a place, not a second kind of screen. */
  onOpenPoi: (id: string) => void

  // The three alert sentences, exactly as the map screen renders them -
  // finished lines from the shell, never recomputed here.
  closureAhead?: string | null
  warningsAhead?: string | null
  advisoryAhead?: string | null
  onShowOnMap: () => void

  /** The one ribbon the shell drew (lib/ribbonView.ts) - the climb card
   *  embeds it whole rather than repainting a fourth elevation look. */
  elevation?: RibbonView
  units?: UnitSystem
  pace: PaceProfile

  // The volunteer card. Data and semantics are screens/Volunteer.tsx's -
  // including the rule that "could not check" must never read as "no club
  // has asked", and the 48-hour ceiling that replaces rather than hedges.
  opportunities: readonly WorkProjectSummary[] | null
  opportunitiesAsOf: Date | null
  onOpenVolunteer: () => void

  /** Today's walked-past places (lib/passedToday.ts) - names and miles, tap
   *  to open. Never a count, never a scold. */
  passedPlaces: readonly PassedPlace[]
  queuedReportCount: number

  onStartReport: () => void

  /** Thanking a maintainer, which is no longer buried inside the problem
   *  picker (#1133). A thanks is a comment about a specific place
   *  (features/SAYING_THANKS.md), not a kind of problem. */
  onSayThanks: () => void

  /** Saved day hikes, surfaced first in day mode - a starting point rather
   *  than an empty column. Cached figures only (lib/dayHikes.ts documents
   *  the provenance); opening one re-resolves the real route. */
  dayHikes: readonly DayHike[]
  onOpenDayHike: (id: string) => void
  /**
   * A walk this phone was following and never finished, from a day before
   * today (#1373, frame 6d; lib/openWalk.ts). The morning asks - "Finished
   * it" logs the walk for that day, "Not this time" forgets - and never
   * closes it unasked. Null or absent prints nothing.
   */
  openWalk?: { hike: DayHike; day: string } | null
  onFinishOpenWalk?: (id: string, day: string) => void
  onDropOpenWalk?: () => void

  // The nothing-downloaded empty state: a starting point, not an apology.
  hasDownload?: boolean
  onOpenDownloads?: () => void

  /** Routes somebody published (lib/suggestedHikes.ts, #1284), for the
   *  shelf. Empty collapses the whole section - a hiker with no suggestions
   *  costs no gap, and no rule with nothing under it. */
  suggestedHikes?: readonly SuggestedHike[]
  /**
   * Where "near" is measured from, so the shelf can pick the nearest
   * starts: the fix, or - since #1373 - the place the hiker said they hike
   * (lib/defaultPlace.ts) when there is no fix. RANKING ONLY. Nothing here
   * prints a distance or claims the hiker is standing there, which is why
   * a stored place may stand in for a fix on this prop and on no other.
   * Null makes no claim at all: the shelf takes the first published.
   */
  near?: LonLat | null
  /** Pushes the Find screen - with facets already applied when a chip on
   *  this screen asked for them ("Under 2 hours"). The row and the chips
   *  render only when there is somewhere for them to go. */
  onFindHike?: (facets?: Partial<HikeFacets>) => void
  /**
   * The pinned bar's other door (#1373, F2): the planning spine. The bar
   * renders only with both doors - a Today outside the shell has neither,
   * and a bar with one dead half is the control D10 forbids.
   */
  onPlanHike?: () => void
  /** The long-hike set-up, for the "you have no hike yet" state's one door:
   *  pick the trail on the map. */
  onStartLongHike?: () => void
  /** Start walking a saved day hike - the follow door (frame 2c's "Walk
   *  this"), the same one the card offers. */
  onWalkDayHike?: (id: string) => void
  /**
   * The one-tap answers for the hiker's own stops (#1373, frames 2c and
   * 2d): the same context the waypoint card's conditions section files
   * through, so a "Dry" tapped here and a "Dry" tapped on the card are the
   * same note. `stopFacts` resolves a stop's waypoint on this phone; a stop
   * whose waypoint is gone draws nothing rather than a row with nothing to
   * tap. Both optional as a pair - absent, no section.
   */
  noteContext?: FieldNoteContext
  stopFacts?: (poiId: string) => StopFacts | null
  /** The hiking sheet's size at the chosen level, already formatted
   *  (lib/formatBytes.ts), for the download notice - null while the
   *  manifest has not said what it weighs. */
  downloadSize?: string | null
  /** The kept place's name (lib/defaultPlace.ts), when the shelf is ranked
   *  from it rather than from a fix, for the setup sentence. */
  placeName?: string | null
  /** Opens a suggested route's detail. Omitted - as it is until wireframe
   *  `1g` is designed - the cards render as things to read rather than as
   *  buttons that go nowhere (chrome/SuggestedHikeCard.tsx). */
  onOpenSuggestedHike?: (id: string) => void
}

/** The section rule's word for the entries, sized to what is known - "ahead"
 *  is a direction claim (see lib/todayJournal.ts). */
function entriesHeading(direction: HikeDirection | undefined): string {
  return direction === undefined ? 'NEARBY' : 'AHEAD'
}

/** The freshness dot's modifier, from the shared treatment - the same three
 *  visible states the lanes wear, no fourth invented (WIREFRAMES.md §11). */
function dotClass(treatment: StalenessTreatment): string | null {
  if (treatment.ring === 'green') return 'today__dot today__dot--fresh'
  if (treatment.ring === 'grey-dotted') return 'today__dot today__dot--stale'
  if (treatment.ring === 'faint-invite') return 'today__dot today__dot--no-word'
  return null
}

/**
 * What the Today screen says about the long hike leading it (#1317).
 *
 * The card's lines arrive finished. This screen renders a hike's day; it
 * does not work out which day that is, what is planned on it, or how far
 * the next resupply is - those come from the store, once, where the store
 * is.
 */
export interface LongHikeToday {
  name: string
  /**
   * Change which hike this is, or undefined where there is nothing to change
   * to (#1344).
   *
   * The name is the control, rather than a control BESIDE the name. A hiker
   * reading "Springer → Katahdin" on their morning screen and wanting a
   * different hike is asking about that exact word, and a second element
   * next to it would be a second thing to find. Undefined renders the name
   * as text - never as a button that does nothing, which is LineSheet's rule.
   */
  onSwitch?: (() => void) | undefined
  /** `412 mi walked · 1,786 mi to go`. Never anything else. */
  figures: string
  /** Which day of the hike today is, or null when the hike has no dated
   *  start to count from - and then the eyebrow simply says the date, which
   *  is true, rather than a day number nothing supports. */
  dayNumber: number | null
  /**
   * Where the hiker is, when the answer is "not on this hike" - `paused 11
   * days · last at mi 1,407.2`, or null.
   *
   * Under the position line rather than replacing the mile, because the mile
   * is still true: the phone knows where it is, it is simply not on the
   * corridor this hike follows, and overwriting a known position with a
   * sentence would lose a fact to say a different one.
   */
  awayLine: string | null
  /** The offer to pick the hike back up, or null. Rendered above everything
   *  else in the column, because a hiker who has been away is not looking
   *  for today's leg - they are looking for what happened. */
  resume: WelcomeBackCardProps | null
  /** Today's leg, or null when there is no plan for today - a hike with no
   *  dated days is the ordinary case, not a broken one. */
  day: {
    title: string
    /** `11.2 mi planned · +1,840 ft`. */
    planned: string
    /** `Resupply: Pearisburg, 31.6 mi on`, or null. */
    resupply: string | null
    /**
     * This is the last of it.
     *
     * The one screen that changes tone, and it changes it DOWN: an 18px
     * title and one sentence, with no countdown, no progress bar and no
     * confetti. A hiker walking the last few miles of a two-year walk is
     * not owed a number ticking to zero.
     */
    last: boolean
    onOpen: () => void
    onTakeZero: () => void
    onSeeOnMap: () => void
  } | null
  /** The last nights' sites (lib/nightsBehind.ts), for "On-trail
   *  conditions · last 3 days" (#1373, frame 2d). Absent renders nothing. */
  nights?: readonly NightBehind[]
}

/** What a stop's answers need that the stop record does not carry: the
 *  waypoint as this phone holds it (lib/trailData.ts), and its mile. */
export interface StopFacts {
  type: string
  lat: number
  lon: number
  mile?: number
  unverified?: boolean
}

export function Today({
  now,
  position,
  online,
  hasGpsFix,
  lastSyncedAt,
  conditionsAge = null,
  backgroundProblem = null,
  backgroundOverride = null,
  trailLinesMissing = false,
  mode,
  onChangeMode,
  modePending = false,
  longHike = null,
  pois,
  currentMile,
  direction,
  stalenessFor,
  onOpenPoi,
  closureAhead = null,
  warningsAhead = null,
  advisoryAhead = null,
  onShowOnMap,
  elevation,
  units = 'imperial',
  pace,
  opportunities,
  opportunitiesAsOf,
  onOpenVolunteer,
  passedPlaces,
  queuedReportCount,
  onStartReport,
  onSayThanks,
  dayHikes,
  onOpenDayHike,
  openWalk = null,
  onFinishOpenWalk,
  onDropOpenWalk,
  hasDownload = true,
  onOpenDownloads,
  suggestedHikes = NO_SUGGESTIONS,
  near = null,
  onFindHike,
  onOpenSuggestedHike,
  onPlanHike,
  onStartLongHike,
  onWalkDayHike,
  noteContext,
  stopFacts,
  downloadSize = null,
  placeName = null,
}: TodayProps) {
  // Memoized because this screen re-renders for reasons that have nothing to do
  // with it (#1090). It is the home screen now, so it is mounted while the GPS
  // clock, the 60-second clock and the hourly conditions check each re-render
  // the shell above it - and `journalEntries` filters, maps and sorts all 2,837
  // POIs on the phone to put at most seven rows on screen. Keyed on everything
  // it reads, so a hiker who is actually walking still gets a rebuilt list on
  // the fix that moves their mile: this buys back the renders where nothing it
  // depends on moved, and nothing else.
  const entries = useMemo(
    () => journalEntries(pois, currentMile, direction),
    [pois, currentMile, direction],
  )
  const readout = splitPosition(position)

  // The greeting's estimate: only when the ribbon is the fix window (its
  // samples share the journal's client mile axis - lib/ribbonView.ts), the
  // destination is inside what was measured, and the direction is settled.
  // Anything less and the sentence carries the distance alone: a time that
  // priced unmeasured climbs at zero would understate the walk, which is the
  // direction "round toward caution" forbids.
  const destination = direction === undefined ? undefined : nextShelter(entries)
  const ascent =
    destination !== undefined &&
    currentMile !== undefined &&
    elevation !== undefined &&
    elevation.source === 'ahead'
      ? ascentBetween(elevation.samples, currentMile, destination.mile)
      : null
  const estimate =
    destination !== undefined && ascent !== null
      ? paceEstimate({ distanceMi: destination.distanceMi, ascentFt: ascent }, pace)
      : null
  const greeting = todayGreeting({
    now,
    ...(destination === undefined
      ? {}
      : {
          destination: { name: destination.name, distanceMi: destination.distanceMi },
        }),
    ...(estimate === null ? {} : { estimate: estimate.text }),
  })

  const alerts =
    closureAhead !== null || warningsAhead !== null || advisoryAhead !== null ? (
      <div className="today__alerts">
        {[
          { line: closureAhead, kind: 'closure' },
          { line: warningsAhead, kind: 'warning' },
          // Last and quietest, the map screen's own ordering (#485): the
          // advisory is the only one not about the next few miles.
          { line: advisoryAhead, kind: 'advisory' },
        ]
          .filter((alert): alert is { line: string; kind: string } => alert.line !== null)
          .map((alert) => (
            <div key={alert.kind} className={`today__card today__card--${alert.kind}`}>
              <p className="today__alert-line">{alert.line}</p>
              {/* The next step, and the honest one: the closure band is
                  drawn on the map (lib/closureStyle.ts), and that is where
                  the shape of the problem is. */}
              <button type="button" className="today__action" onClick={onShowOnMap}>
                See it on the map
              </button>
            </div>
          ))}
      </div>
    ) : null

  const journal =
    entries.length > 0 ? (
      <>
        <div className="today__rule">
          <span className="today__rule-label">{entriesHeading(direction)}</span>
        </div>
        {entries.map((entry) => {
          const presentation = stalenessFor?.(entry.id, entry.type) ?? null
          // The words ride only where the pixels do (WIREFRAMES.md §11): a
          // visibly-dotted entry says why; a neutral one stays quiet rather
          // than reading "Never confirmed" down the whole column.
          const dot = presentation === null ? null : dotClass(presentation.treatment)
          const meta =
            dot === null || presentation === null
              ? typeLabel(entry.type)
              : `${typeLabel(entry.type)} · ${presentation.words}`
          // ONE WAYPOINT ROW, EVERYWHERE (#1373, the shared PoiRow): the
          // journal prints the distance through lib/units.ts like every
          // other figure (rule R6) - it used to format miles by hand here.
          return (
            <PoiRow
              key={entry.id}
              kind={entry.type}
              title={entry.name}
              meta={`${formatDistance(entry.distanceMi, units)} · ${meta}`}
              onOpen={() => onOpenPoi(entry.id)}
            />
          )
        })}
      </>
    ) : null

  const climb =
    elevation?.upcomingClimb !== undefined ? (
      <div className="today__card today__card--climb">
        <div className="today__climb-head">
          <span className="today__rule-label">The climb ahead</span>
          <span className="today__climb-figure">
            +{formatElevation(elevation.upcomingClimb.ascentFt, units)}
          </span>
        </div>
        {/* The ribbon itself, not a fourth elevation look: same paints, same
            callout, same honesty about where the rule may be drawn. */}
        <ElevationRibbon
          {...elevation}
          subject={elevation.source as RibbonSubject}
          units={units}
        />
      </div>
    ) : null

  const soFar =
    passedPlaces.length > 0 ? (
      <>
        <div className="today__rule">
          <span className="today__rule-label">Today so far</span>
        </div>
        {passedPlaces.map((place) => (
          <PoiRow
            key={place.id}
            kind={place.type}
            title={place.name}
            // A mile marker on the trail's own axis - the position line's
            // spelling, not a distance to convert.
            meta={`mi ${formatMile(place.mile)} · ${typeLabel(place.type)}`}
            onOpen={() => onOpenPoi(place.id)}
          />
        ))}
      </>
    ) : null

  const upcoming =
    opportunities !== null &&
    opportunitiesAsOf !== null &&
    opportunitiesUsable(opportunitiesAsOf, now)
      ? upcomingWorkProjects(opportunities, now)
      : null
  const volunteerMeta =
    opportunities === null
      ? "The workday list needs signal to load, and hasn't yet."
      : opportunitiesAsOf === null || !opportunitiesUsable(opportunitiesAsOf, now)
        ? 'The workday list is out of date — check with the club before traveling.'
        : upcoming !== null && upcoming.length > 0
          ? `${upcoming[0].title} · ${upcoming[0].club_name} · ${workProjectDates(upcoming[0])}`
          : 'No workdays are posted here yet. Clubs add them as they schedule crews.'
  const volunteer = (
    <button
      type="button"
      className={
        mode === 'volunteer'
          ? 'today__card today__card--volunteer today__card--volunteer-lead'
          : 'today__card today__card--volunteer'
      }
      onClick={onOpenVolunteer}
    >
      {/* A shelter, as the card's thumb (#1054, maintainer's pick
          2026-08-26). Wikimedia Commons: "Shelter along the Appalachian
          Trail" by Carol M. Highsmith (LCCN 2011630549), public domain -
          named here as provenance, not obligation. Decorative to a screen
          reader; the words beside it carry the card. */}
      <span className="today__volunteer-photo" aria-hidden="true">
        <img src={shelterPhoto} alt="" />
      </span>
      <span className="today__volunteer-text">
        <span className="today__volunteer-eyebrow">Volunteer</span>
        <span className="today__volunteer-title">
          {mode === 'volunteer' ? 'Your day on the trail crew' : 'The trail crew'}
        </span>
        <span className="today__volunteer-meta">{volunteerMeta}</span>
      </span>
      <span className="today__volunteer-chevron" aria-hidden="true">
        ›
      </span>
    </button>
  )

  /**
   * "Today on your hike" - the card that leads the column in long-hike mode.
   *
   * THE THUMBNAIL IS A DOOR, NOT A PICTURE, and that is a deliberate
   * shortfall rather than the design. The handoff asks for the map's own
   * canvas framed to the day's two ends, and is explicit that it must not be
   * "a second drawing of the trail" - so rather than draw one, this is a
   * labelled region that opens the Map tab framed the same way. A hiker gets
   * the framing they were promised, one tap later, and nothing on screen
   * claims to be a map that is not one.
   *
   * @unvalidated as a substitute. What would settle it is the map canvas
   * being mountable in a second, small viewport at once - nothing in
   * chrome/MapScreen.tsx does that today, and a second MapLibre instance on
   * the home screen is a memory cost nobody has measured on a phone.
   */
  const hikeDayCard =
    longHike?.day == null ? null : (
      <section className="today__card today__card--hike" aria-label="Today on your hike">
        <p className="today__rule-label">
          {longHike.day.last ? 'The last of it' : 'Today on your hike'}
        </p>
        <h2
          className={
            longHike.day.last
              ? 'today__hike-title today__hike-title--last'
              : 'today__hike-title'
          }
        >
          {longHike.day.title}
        </h2>
        {longHike.day.last ? (
          <p className="today__hike-line">
            The sign at the top is the end of the hike you started. Nothing here counts
            down for you.
          </p>
        ) : (
          <>
            <p className="today__hike-line">{longHike.day.planned}</p>
            {longHike.day.resupply !== null && (
              <p className="today__hike-line">{longHike.day.resupply}</p>
            )}
          </>
        )}
        <button
          type="button"
          className="today__hike-map"
          onClick={longHike.day.onSeeOnMap}
        >
          See this day on the map
        </button>
        <div className="today__actions">
          <button type="button" className="today__action" onClick={longHike.day.onOpen}>
            Open the day
          </button>
          <button
            type="button"
            className="today__action"
            onClick={longHike.day.onTakeZero}
          >
            Take a zero
          </button>
        </div>
      </section>
    )

  // TODAY'S WALK (#1373, frame 2c): the planned day hike dated today is the
  // loaded state - the subject of the screen rather than a row in a list.
  // Its figures print exactly as the card prints them (rule R6: one
  // rounding rule, one source - lib/units.ts and lib/pace.ts through the
  // cached climb, and no time at all where no climb was measured), and
  // its two doors are the card's: open it, or start walking it.
  const today = localDay(now)
  const todaysWalk = dayHikes.find((hike) => hike.date === today) ?? null
  const walkEstimate = todaysWalk === null ? null : cachedEstimate(todaysWalk, pace)
  const walkCard =
    todaysWalk === null ? null : (
      <section className="today__card today__card--hike" aria-label="Today’s walk">
        <p className="today__rule-label">Today · day hike</p>
        <h2 className="today__hike-title">{todaysWalk.name}</h2>
        <p className="today__hike-line">
          {formatDistance(todaysWalk.figures.miles, units)}
          {todaysWalk.figures.climb != null &&
            ` · +${formatElevation(todaysWalk.figures.climb.gainFt, units)} / −${formatElevation(todaysWalk.figures.climb.lossFt, units)}`}
          {walkEstimate !== null && ` · ${walkEstimate.text} walking`}
          {todaysWalk.figures.climb == null && ' · no climb measured, so no time'}
        </p>
        {walkEstimate?.relativeLine != null && (
          <p className="today__pace-line">{walkEstimate.relativeLine}</p>
        )}
        <div className="today__actions">
          <button
            type="button"
            className="today__action"
            onClick={() => onOpenDayHike(todaysWalk.id)}
          >
            Open the walk
          </button>
          {onWalkDayHike !== undefined && (
            <button
              type="button"
              className="today__action"
              onClick={() => onWalkDayHike(todaysWalk.id)}
            >
              Walk this
            </button>
          )}
        </div>
      </section>
    )
  const otherHikes = dayHikes.filter((hike) => hike !== todaysWalk)

  // ON-TRAIL CONDITIONS (#1373, frames 2c and 2d): "the stops a hiker said
  // they would make - three nights back on a long hike and this walk's own
  // stops on a day hike, never everything they passed." Each is the
  // waypoint card's own peek (chrome/FieldNoteSection.tsx), filed through
  // the same context, so the answer costs one tap here instead of a trip
  // through the map. Never counts, never dims: the peek's rules are its
  // own. A stop this phone can no longer place draws nothing.
  const conditionRows = (
    rows: readonly { key: string; label: string; poiId: string; name: string }[],
  ) =>
    rows
      .map((row) => {
        const facts = stopFacts?.(row.poiId) ?? null
        if (facts === null || noteContext === undefined || !isNoteScopedType(facts.type))
          return null
        return (
          <div key={row.key} className="today__condition">
            <PoiRow
              kind={facts.type}
              title={row.name}
              meta={
                facts.mile === undefined
                  ? row.label
                  : `${row.label} · mi ${formatMile(facts.mile)}`
              }
              {...(facts.unverified ? { confidence: 'low' as const } : {})}
            />
            <FieldNoteSection
              variant="peek"
              poiId={row.poiId}
              poiType={facts.type}
              lat={facts.lat}
              lon={facts.lon}
              {...(facts.mile === undefined ? {} : { mile: facts.mile })}
              unverified={facts.unverified ?? false}
              context={noteContext}
            />
          </div>
        )
      })
      .filter((row) => row !== null)
  const conditionSet =
    mode === 'day' && todaysWalk !== null && (todaysWalk.stops?.length ?? 0) > 0
      ? {
          note: 'your stops today',
          rows: conditionRows(
            (todaysWalk.stops ?? []).map((stop) => ({
              key: stop.poiId,
              label: 'your stop',
              poiId: stop.poiId,
              name: stop.name,
            })),
          ),
        }
      : mode === 'long' && longHike?.nights !== undefined && longHike.nights.length > 0
        ? {
            // The frame's own words: the nights are the sites, the days
            // are the period they cover.
            note: `last ${longHike.nights.length} ${longHike.nights.length === 1 ? 'day' : 'days'}`,
            rows: conditionRows(
              longHike.nights.map((night) => ({
                key: `${night.label}-${night.poiId}`,
                label: night.label,
                poiId: night.poiId,
                name: night.name,
              })),
            ),
          }
        : null
  const conditions =
    conditionSet === null || conditionSet.rows.length === 0 ? null : (
      <>
        <div className="today__rule">
          <span className="today__rule-label">On-trail conditions</span>
          <span className="today__rule-note">{conditionSet.note}</span>
        </div>
        {conditionSet.rows}
      </>
    )

  const hikes =
    otherHikes.length > 0 ? (
      <>
        <div className="today__rule">
          <span className="today__rule-label">Your day hikes</span>
        </div>
        {otherHikes.map((hike) => (
          <button
            key={hike.id}
            type="button"
            className="today__card today__card--entry"
            onClick={() => onOpenDayHike(hike.id)}
          >
            <span className="today__entry-text">
              <span className="today__entry-name">{hike.name}</span>
              {/* Cached figures, and provenance-bound (lib/dayHikes.ts):
                  printed for the list, re-derived the moment the hike
                  opens. */}
              <span className="today__entry-meta">
                {formatDistance(hike.figures.miles, units)}
              </span>
            </span>
            <span className="today__volunteer-chevron" aria-hidden="true">
              ›
            </span>
          </button>
        ))}
      </>
    ) : null

  // The shelf's picks, memoized with the journal's argument: this screen
  // re-renders on every fix and every clock tick, and the picks change only
  // when the routes or the fix do.
  const picks = useMemo(() => shelfPicks(suggestedHikes, near), [suggestedHikes, near])
  const morePublished = suggestedHikes.length - picks.length

  // SUGGESTED HIKES (#1284): routes somebody published, near the hiker, and
  // the way to the rest of them. The app surfaces them and names who wrote
  // each; it never rates, ranks or scores a route itself, and the note under
  // the row says whose they are. Renders in every mode - it leads in day
  // mode and sits last in long and volunteer, where the hiker's own walk is
  // the subject - and not at all when there is nothing to suggest.
  const suggested =
    suggestedHikes.length > 0 ? (
      <>
        <div className="today__rule">
          {/* "Near you" only when something is ranking them - a fix, or
              the kept place - and "Suggested" otherwise, which is the
              honest heading over a list in published order. */}
          <span className="today__rule-label">
            {near === null ? 'Suggested hikes' : 'Hikes near you'}
          </span>
        </div>
        <div className="today__suggested-rail">
          {picks.map((hike) => (
            <SuggestedHikeCard
              key={hike.id}
              hike={hike}
              variant="shelf"
              units={units}
              pace={pace}
              {...(onOpenSuggestedHike === undefined
                ? {}
                : { onOpen: onOpenSuggestedHike })}
            />
          ))}
        </div>
        {onFindHike !== undefined && (
          <button type="button" className="today__find" onClick={() => onFindHike()}>
            <HikeFinderIcon name="search" className="today__find-icon" />
            <span className="today__find-label">Find a hike</span>
            {/* How many the shelf did not show - a count of routes, never
                of anybody. Absent when the shelf holds them all. */}
            {morePublished > 0 && (
              <span className="today__find-count">{morePublished} more ›</span>
            )}
          </button>
        )}
        {/* "Have less time?" (#1373, frame 2a): the finder's own facets,
            in its own words (lib/suggestedHikes.ts's labels), opened with
            the filter already applied. Day mode only - the other two modes
            are not looking for a walk to fit an afternoon. No "Loops": the
            finder has no shape facet, and a chip that opened it unfiltered
            would promise one. */}
        {onFindHike !== undefined && mode === 'day' && (
          <div className="today__have-less" role="group" aria-label="Have less time?">
            <span className="today__have-less-label">Have less time?</span>
            <button
              type="button"
              className="today__have-less-chip"
              onClick={() => onFindHike({ time: 'under2' })}
            >
              {timeBucketLabel('under2')}
            </button>
            <button
              type="button"
              className="today__have-less-chip"
              onClick={() => onFindHike({ time: '2to4' })}
            >
              {timeBucketLabel('2to4')}
            </button>
            <button
              type="button"
              className="today__have-less-chip"
              onClick={() => onFindHike({ difficulty: ['easy'] })}
            >
              Easy only
            </button>
          </div>
        )}
        <p className="today__note">
          Routes from community contributions. Check before traveling.
        </p>
      </>
    ) : null

  // THE DOWNLOAD, AS A NOTICE (#1373, F2): "download appears whenever it
  // is needed and nowhere else" - the design's Notice in its warn tone, at
  // the head of the column, where a card that read as one more entry stood.
  // What it says stays true of a whole-corridor package: the size is the
  // manifest's for the chosen level, and with none it says only what still
  // works without the sheet.
  const download =
    !hasDownload && onOpenDownloads !== undefined ? (
      <Notice
        tone="warn"
        title="The topo sheet is not on this phone"
        body={
          downloadSize === null
            ? 'Trails and waypoints work without it.'
            : `${downloadSize}. Trails and waypoints work without it.`
        }
        action={{ label: 'Download', onClick: onOpenDownloads }}
      />
    ) : null

  // THE SETUP HEAD (#1373, F2): "until a hike is loaded, Today is a
  // different screen - a setup screen, not an empty list. Its contents come
  // from the mode." The head leads the column and says what to do next;
  // the bar at the foot is where to do it. Everything the column already
  // carried stays under the head - the alerts, the journal from a fix, the
  // crew card - because a screen that dropped the closure ahead on the
  // grounds that nothing was planned would be the worse failure.
  const setup =
    mode === 'day' && todaysWalk === null ? (
      <section className="today__setup" aria-labelledby="today-setup-title">
        <h2 id="today-setup-title" className="today__setup-title">
          Nothing planned today
        </h2>
        <p className="today__setup-line">
          {suggestedHikes.length === 0
            ? 'A builder for a route of your own — and published walks, once this phone holds any.'
            : placeName !== null
              ? `Published walks, nearest ${placeName} first, and a builder if none of them is yours.`
              : near !== null
                ? 'Published walks, nearest you first, and a builder if none of them is yours.'
                : 'Published walks to pick from, and a builder if none of them is yours.'}
        </p>
      </section>
    ) : mode === 'long' && longHike == null ? (
      <section className="today__setup" aria-labelledby="today-setup-title">
        <h2 id="today-setup-title" className="today__setup-title">
          You have no hike yet
        </h2>
        <p className="today__setup-line">
          A long hike is one trail, broken into days. Pick the trail and OurHike will hold
          the rest.
        </p>
        {/* The frame lists the long trails on the map here; the shell holds
            no list of named lines off the map yet, so the one door is the
            map itself, where the lines are (screens/HikeSetup.tsx). */}
        {onStartLongHike !== undefined && (
          <button type="button" className="today__action" onClick={onStartLongHike}>
            Pick a trail on the map ›
          </button>
        )}
        <p className="today__note">
          Not on a long hike after all? Switch to Day hike above — nothing here is lost.
        </p>
      </section>
    ) : null

  // Frame 2e's last line: the bar is the same on the crew's day.
  const walkingToo =
    mode === 'volunteer' && onFindHike !== undefined && onPlanHike !== undefined ? (
      <p className="today__note">
        Walking today as well? Find and Plan are where they always are.
      </p>
    ) : null

  const noJournal =
    entries.length === 0 ? (
      <p className="today__note">
        {currentMile === undefined
          ? 'The journal fills in from your position — nothing here claims to know where you are yet.'
          : 'Nothing of the journal’s kinds is on this stretch of trail.'}
      </p>
    ) : null

  // Mode re-ranks; nothing disappears. The arrays read top-to-bottom, and
  // each slot is keyed by what it is so React reconciles a re-rank as a move
  // rather than a teardown.
  const named: Record<string, ReactNode> = {
    setup,
    download,
    walk: walkCard,
    conditions,
    walkingToo,
    alerts,
    volunteer,
    soFar,
    journal: journal ?? noJournal,
    climb,
    hikes,
    suggested,
    // Null in every other mode, which is what keeps one ordered record
    // rather than three lists with a hole in two of them (#1317).
    hikeDay: hikeDayCard,
    resume: longHike?.resume == null ? null : <WelcomeBackCard {...longHike.resume} />,
  }
  const order =
    mode === 'volunteer'
      ? [
          'setup',
          'download',
          'alerts',
          'volunteer',
          'soFar',
          'journal',
          'climb',
          'hikes',
          'suggested',
          'walkingToo',
        ]
      : mode === 'day'
        ? [
            'setup',
            'walk',
            'download',
            'alerts',
            'suggested',
            'hikes',
            'journal',
            'conditions',
            'climb',
            'soFar',
            'volunteer',
          ]
        : // The hike's own day LEADS, above the alerts - and the alerts
          // still render, one slot down. Nothing disappears; what changes is
          // what a hiker's eye lands on first (#1317, lib/hikerMode.ts).
          [
            'setup',
            'download',
            // Above the day's own leg: a hiker who has been away for a
            // fortnight is not looking for today's miles, they are looking
            // for what happened while they were gone.
            'resume',
            'hikeDay',
            'alerts',
            'journal',
            'conditions',
            'climb',
            'soFar',
            'volunteer',
            'hikes',
            'suggested',
          ]
  const sections = order.map((key) => (
    <div key={key} className="today__section">
      {named[key]}
    </div>
  ))

  return (
    <div className="today">
      <header className="today__chrome">
        <StatusStrip
          time={now}
          online={online}
          hasGpsFix={hasGpsFix}
          lastSyncedAt={lastSyncedAt}
          conditionsAge={conditionsAge}
          backgroundProblem={backgroundProblem}
          backgroundOverride={backgroundOverride}
          trailLinesMissing={trailLinesMissing}
        />
        <p className="today__eyebrow">
          {[
            formatTodayEyebrow(now),
            // "TUE 8 SEP · DAY 6". The day of the hike rather than a date
            // twice: which day of the walk this is is the thing a hiker on a
            // long hike is orienting by, and the calendar date is already
            // there beside it.
            longHike?.dayNumber == null ? null : `DAY ${longHike.dayNumber}`,
          ]
            .filter((part) => part !== null)
            .join(' · ')}
        </p>
        {readout.kind === 'mile' ? (
          <p className="today__readout">
            <span className="today__mile">{readout.mile}</span>
            <span className="today__mile-unit">{readout.unit}</span>
          </p>
        ) : (
          <p className="today__position-sentence">{readout.sentence}</p>
        )}
        <p className="today__greeting">{greeting}</p>
        {longHike?.awayLine != null && (
          <p className="today__away-line">{longHike.awayLine}</p>
        )}
        {longHike != null && (
          <>
            {longHike.onSwitch === undefined ? (
              <p className="today__hike-name">{longHike.name}</p>
            ) : (
              <button
                type="button"
                className="today__hike-name today__hike-name--switch"
                onClick={longHike.onSwitch}
              >
                {longHike.name}
                {/* The affordance, not the name. Read aloud it would be
                    "Springer → Katahdin ▾", which is a mark rather than a
                    word, so the button says what it does instead. */}
                <span aria-hidden="true"> ▾</span>
                <span className="visually-hidden">
                  {' '}
                  — change which hike you&rsquo;re on
                </span>
              </button>
            )}
            {/* `miles walked · miles to go`, and nothing else - no
                percentage, no "on track", no comparison with anybody. The
                Plan tab's standing guard covers this surface too. */}
            <p className="today__hike-figures">{longHike.figures}</p>
          </>
        )}
        {estimate !== null && estimate.relativeLine !== null && (
          // #851: no surface prints an adjusted time without what it was
          // adjusted from.
          <p className="today__pace-line">{estimate.relativeLine}</p>
        )}
        <ModeSwitch
          mode={mode}
          onChange={onChangeMode}
          variant="chrome"
          pending={modePending}
        />
      </header>

      <div className="today__paper">
        {/* THE WALK LEFT OPEN (#1373, frame 6d): following ended with the
            session and nobody said how the walk ended, so the morning asks
            - once, at the head of the column, with both answers and no
            default. Nothing here moves on its own: a walk nobody finished
            is a question, not a record (WelcomeBackCard's rule, kept). The
            design's "stopped counting at 6:12pm near…" is not printed: the
            phone keeps no such record, on purpose. */}
        {openWalk !== null &&
          onFinishOpenWalk !== undefined &&
          onDropOpenWalk !== undefined && (
            <section
              className="today__card today__card--hike"
              aria-label="A walk is still open"
            >
              <p className="today__rule-label">
                {dayLongDateLabel(openWalk.day)} · day hike
              </p>
              <h2 className="today__hike-title">
                {openWalk.day === localDay(new Date(now.getTime() - 86_400_000))
                  ? 'Yesterday’s walk is still open'
                  : 'A walk is still open'}
              </h2>
              <p className="today__hike-line">
                {openWalk.hike.name} ·{' '}
                {formatDistance(openWalk.hike.figures.miles, units)}
              </p>
              <p className="today__setup-line">
                You were walking it and nothing said how it ended. Say so, or leave it —
                nothing changes on its own.
              </p>
              <div className="today__actions">
                <button
                  type="button"
                  className="today__action"
                  onClick={() => onFinishOpenWalk(openWalk.hike.id, openWalk.day)}
                >
                  Finished it
                </button>
                <button type="button" className="today__action" onClick={onDropOpenWalk}>
                  Not this time
                </button>
              </div>
            </section>
          )}
        {sections}
        {/* TWO BUTTONS, EQUAL WIDTH AND EQUAL WEIGHT (#1133).

            This was one primary button reading "Note something for the crew",
            and saying thanks was the seventh row inside the problem picker,
            under a list of hazards. Both halves were wrong. Reporting a
            problem and thanking a maintainer are two sides of one
            relationship with the crew - the volunteer card sits directly
            above this row - and burying one of them under the other was
            costing it.

            Equal WEIGHT is the part worth defending. An outline "Say thanks"
            beside a filled "Report a problem" would say, in the only language
            a button has, that thanking is the afterthought. So both are solid
            fills, at the same size, in the app's two brand colours.

            Both of those fills were failing contrast until #1132 - the
            secondary variant read a base palette token that cannot follow a
            theme, and both hardcoded a label colour that does not flip. This
            row is why that got measured. */}
        <div className="today__crew">
          <Button
            variant="secondary"
            size="s"
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={onStartReport}
          >
            Report a problem
          </Button>
          <Button
            variant="primary"
            size="s"
            style={{ flex: 1, justifyContent: 'center' }}
            onClick={onSayThanks}
          >
            Say thanks
          </Button>
        </div>

        {/* WAITING, AND NOW SOMEWHERE TO GO. This line already existed - it
            hid at zero and pluralised - but it sat up in "Today so far", a
            section about places, and it was not tappable. It is about the
            outbox, so it belongs under the buttons that fill the outbox, and
            it opens the screen that actually holds those reports.

            `onOpenVolunteer` rather than a new prop: More's volunteer page is
            where a queued report is already surfaced and retried, so a second
            destination would be a second answer to "where are my reports". */}
        {queuedReportCount > 0 && (
          <button
            type="button"
            className="today__outbox"
            data-testid="today-outbox"
            onClick={onOpenVolunteer}
          >
            <span className="today__outbox-dot" aria-hidden="true" />
            <span>
              {/* The same sentence More prints (#1373, C16): the count is the
                  whole outbox - notes, reports, photos, hours, closures - so
                  no one noun was true of it. */}
              {queuedReportCount === 1
                ? '1 waiting to send'
                : `${queuedReportCount} waiting to send`}
            </span>
            <span className="today__outbox-chevron" aria-hidden="true">
              ›
            </span>
          </button>
        )}

        {/* Said on the home screen because it is the promise the whole app
            is built around. */}
        <p className="today__footer">Everything here works with no signal.</p>
      </div>

      {/* THE PINNED BAR (#1373, rule R4 and frames 2a-2e): Find and Plan on
          every state of this screen, forever. Under the paper rather than
          in it, so it stays put while the column scrolls, with the tab bar
          under it. Emphasis goes to Plan while nothing is loaded - that is
          the next step - and to neither once something is. */}
      {onFindHike !== undefined && onPlanHike !== undefined && (
        <PinnedBar
          onFind={() => onFindHike()}
          onPlan={onPlanHike}
          emphasis={setup === null ? 'none' : 'plan'}
        />
      )}
    </div>
  )
}
