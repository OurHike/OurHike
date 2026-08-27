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
import { formatElevation } from '../lib/units'
import { poiColor, poiGlyphPath } from '../map/poiIcons'
import { typeLabel } from '../chrome/legendLabels'
import {
  opportunitiesUsable,
  upcomingWorkProjects,
  workProjectDates,
  type WorkProjectSummary,
} from '../lib/workProjects'
import type { PassedPlace } from './Volunteer'
import type { DayHike } from '../lib/dayHikes'
import { Button } from '../design-system/components'
import '../chrome/chrome.css'
import './today.css'

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

  // The nothing-downloaded empty state: a starting point, not an apology.
  hasDownload?: boolean
  onOpenDownloads?: () => void
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
  hasDownload = true,
  onOpenDownloads,
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
          return (
            <div key={entry.id} className="today__row">
              <span className="today__gutter">
                {entry.distanceMi.toLocaleString('en-US', {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                })}
              </span>
              <button
                type="button"
                className="today__card today__card--entry"
                onClick={() => onOpenPoi(entry.id)}
              >
                {/* The real silhouette from map/poiIcons.ts, never a redrawn
                    one - the chip's accent is the pin's own colour, mixed
                    over the card by CSS. */}
                <span
                  className="today__chip"
                  style={{ '--chip-accent': poiColor(entry.type) } as React.CSSProperties}
                  aria-hidden="true"
                >
                  <svg viewBox="0 0 1 1" focusable="false">
                    <path d={poiGlyphPath(entry.type)} fillRule="evenodd" />
                  </svg>
                </span>
                <span className="today__entry-text">
                  <span className="today__entry-name">{entry.name}</span>
                  <span className="today__entry-meta">{meta}</span>
                </span>
                {dot !== null && presentation !== null && (
                  <span className={dot}>
                    <span className="visually-hidden">{presentation.words}</span>
                  </span>
                )}
              </button>
            </div>
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
          <div key={place.id} className="today__row">
            <span className="today__gutter">
              {place.mile.toLocaleString('en-US', {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1,
              })}
            </span>
            <button
              type="button"
              className="today__card today__card--entry"
              onClick={() => onOpenPoi(place.id)}
            >
              <span
                className="today__chip"
                style={{ '--chip-accent': poiColor(place.type) } as React.CSSProperties}
                aria-hidden="true"
              >
                <svg viewBox="0 0 1 1" focusable="false">
                  <path d={poiGlyphPath(place.type)} fillRule="evenodd" />
                </svg>
              </span>
              <span className="today__entry-text">
                <span className="today__entry-name">{place.name}</span>
                <span className="today__entry-meta">{typeLabel(place.type)}</span>
              </span>
            </button>
          </div>
        ))}
      </>
    ) : null

  // The volunteer card renders in EVERY mode - that is the deal the tab's
  // removal was approved on - and leads in volunteer mode. Its meta keeps
  // Volunteer.tsx's four-way honesty: could-not-check, out-of-date, none
  // posted, or the next real workday.
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

  const hikes =
    dayHikes.length > 0 ? (
      <>
        <div className="today__rule">
          <span className="today__rule-label">Your day hikes</span>
        </div>
        {dayHikes.map((hike) => (
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
                {hike.figures.miles.toLocaleString('en-US', {
                  maximumFractionDigits: 1,
                })}{' '}
                mi
              </span>
            </span>
            <span className="today__volunteer-chevron" aria-hidden="true">
              ›
            </span>
          </button>
        ))}
      </>
    ) : null

  const download =
    !hasDownload && onOpenDownloads !== undefined ? (
      <div className="today__card today__card--download">
        <p className="today__entry-name">Take the whole trail with you</p>
        <p className="today__note">
          One download and the map works with no bars and no data plan — the way the trail
          actually is.
        </p>
        <button type="button" className="today__action" onClick={onOpenDownloads}>
          Choose a download
        </button>
      </div>
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
    alerts,
    volunteer,
    soFar,
    journal: journal ?? noJournal,
    climb,
    hikes,
  }
  const order =
    mode === 'volunteer'
      ? ['alerts', 'volunteer', 'soFar', 'journal', 'climb', 'hikes']
      : mode === 'day'
        ? ['alerts', 'hikes', 'journal', 'climb', 'soFar', 'volunteer']
        : ['alerts', 'journal', 'climb', 'soFar', 'volunteer', 'hikes']
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
        <p className="today__eyebrow">{formatTodayEyebrow(now)}</p>
        {readout.kind === 'mile' ? (
          <p className="today__readout">
            <span className="today__mile">{readout.mile}</span>
            <span className="today__mile-unit">{readout.unit}</span>
          </p>
        ) : (
          <p className="today__position-sentence">{readout.sentence}</p>
        )}
        <p className="today__greeting">{greeting}</p>
        {estimate !== null && estimate.relativeLine !== null && (
          // #851: no surface prints an adjusted time without what it was
          // adjusted from.
          <p className="today__pace-line">{estimate.relativeLine}</p>
        )}
        <ModeSwitch mode={mode} onChange={onChangeMode} variant="chrome" />
      </header>

      <div className="today__paper">
        {download}
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
              {queuedReportCount === 1
                ? '1 note waiting to send'
                : `${queuedReportCount} notes waiting to send`}
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
    </div>
  )
}
