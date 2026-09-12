// The finished day hike (#980, frame `1l`) - the blocks with a source today.
//
// The frame is the richest in its group and this card deliberately renders
// LESS of it than it draws. What ships: the legs with their walked miles, the
// LOOP badge, the ± elevation and ≈time (#1011), the ways off, and the
// one-line credit to the orgs that keep the ground walkable - and, since
// #1008, a date field, the gap rows for a multi-segment walk, and the "Leave
// this with someone" door (frame D6, screens/LeaveWithSomeone.tsx).
//
// WHAT CAME BACK OFF, and why (#1112, maintainer's call 2026-08-27): each
// leg used to name its maintaining organization, and each way off did too.
// Three things were wrong with it at once. It repeated - one row per leg,
// usually the same org twice over. It was the least actionable part of a row
// a hiker reads to walk by: the trail's name and its length are what the
// walking is done with. And the published names are long enough to break the
// row - `oprhp_trails` is 68 characters, and #1112 is what that did to the
// layout.
//
// It is NOT an attribution obligation, and that was checked rather than
// assumed: chrome/SourcesSection.tsx renders each steward's licence and
// attribution string verbatim, which is where features/SOURCE_REGISTRY.md's
// "required at submission" text is actually discharged. This card credits by
// COUNT - "Two organizations keep this loop walkable" - which survives
// unchanged, and `orgCount` reads `leg.source` rather than a steward name, so
// the sentence never depended on the labels that left.
//
// What waits, and on what (#980 keeps the ledger): the turn list (a naming
// rule #934 left open), "Starts at · Parking" (#981's pipeline data), the
// on-route POI counts (a policy #768's rule does not cover), and the frame's
// "Chip in ›" (no org's donate wording exists anywhere in the registry or the
// stewards export to speak with, and inventing one would be this app putting
// words in a steward's mouth).
//
// THE FIGURES SAY WHAT THEY ARE, and the note under them carries TWO claims
// that are easy to mistake for one:
//
// - WHAT THE TIME MEASURES. It is moving time, at whatever pace it was
//   priced at. A hiker reading "≈3h 10m" as when they are back at the car is
//   out by however long they sat at the view. The storyboard (frame D5) names
//   this sentence as one of the two reasons that screen exists; #1008 shipped
//   the figure without it, while the trips side had carried its own all along
//   (PlanTargetSheet). #1040 made it more necessary, not less: priced at the
//   hiker's own pace, the number looks personal and still counts no stops.
// - HOW PRECISE THE CLIMB IS. A dense sum over a 10 m elevation model is not
//   the same kind of number as the miles beside it: published figures for one
//   walk disagree by more than rounding, and the pipeline's own gate reads
//   +18.8% against a maintaining club on exactly this rolling terrain. That
//   half is the maintainer's call (2026-08-25) and is kept verbatim.
//
// Neither substitutes for the other: a hiker can believe the second and still
// be an hour late because of the first. Neither is decoration.
//
// The figures prefer the LIVE resolution and fall back to the stored cache
// with a sentence saying so - never silently. lib/dayHikes.ts's provenance
// note is the rule: the cache was computed from the graph the phone held at
// save time, and a card that prints it over today's different graph without
// comment is a display outrunning its source.

import { useState } from 'react'
import { useDraftField } from '../lib/useDraftField'

import type { BailOut, ResolvedDayHike } from '../lib/dayHikeCard'
import { distinctLegSources, type DayHike } from '../lib/dayHikes'
import type { PlanTextLegs } from '../lib/dayHikePlanText'
import {
  STOP_FAR_OFF_COURSE_FEET,
  stoppingMinutes,
  type DayHikeStop,
} from '../lib/dayHikeStops'
import { WATER_SAID_OFF_FEET, type RouteWater } from '../lib/dayHikeWater'
import { blazeLabel, blazePaintColor, NEUTRAL_BLAZE_COLOR } from '../lib/blaze'
import { dayHikeGaps } from '../lib/dayHikeShelf'
import { HIKER_MODE_LABELS } from '../lib/hikerMode'
import { dayLongDateLabel } from '../lib/planDisplay'
import { paceEstimate, type PaceProfile } from '../lib/pace'
import {
  formatDistance,
  formatElevation,
  formatShortDistance,
  MIN_STATED_FEET,
  type UnitSystem,
} from '../lib/units'
import { PoiRow } from '../chrome/PoiRow'
import { StepRail } from '../chrome/StepRail'
import { LeaveWithSomeone } from './LeaveWithSomeone'
import './plan.css'

const COUNT_WORDS = ['No', 'One', 'Two', 'Three', 'Four', 'Five']

export interface DayHikeCardProps {
  hike: DayHike
  /** The hike against this phone's live graph, or null when it has no graph
   *  or the graph can no longer place the walk - the card then leans on the
   *  stored figures and says which of the two happened. */
  resolved: ResolvedDayHike | null
  bailOuts: BailOut[]
  units: UnitSystem
  /**
   * The hiker's own pace (#880), which this card used to ignore (#1040).
   *
   * It priced its walk with `naismithMinutes` - the STANDARD rule - while the
   * A.T. builder and the plan timeline priced theirs with the hiker's own. A
   * hiker who told this app they walk at 2 mph read their day hike at 3.1,
   * and nothing on either screen said which one was which.
   */
  pace: PaceProfile
  networkAvailable: boolean
  /** review: Done pressed, nothing stored yet - Save is the primary action.
   *  saved: opened from the Plan tab, where delete lives. */
  mode: 'review' | 'saved'
  /** Whether Today leads with a walk dated today - true in day mode, where
   *  Today's order puts the walk first, and false in the other two, where a
   *  dated day hike sits with the hiker's other hikes further down
   *  (screens/Today.tsx's `order`). The just-saved line reads it, so a
   *  long-hiker is not promised a top card Today will not give. */
  leadsToday?: boolean
  /** Whether the card is docked beside the map rather than a sheet over it
   *  (desktop.css's rail, #1373 frame 16b): then it is a region, not a
   *  dialog - the rule lib/useDesktop.ts states for the persistent legend. */
  docked?: boolean
  onSave?: () => void
  onClose: () => void
  onDelete?: () => void
  /** Set or clear the hike's date (#1008). The list and the trailhead door
   *  both read it, which is what made a card with no way to write one a
   *  gap rather than a nicety. */
  onSetDate?: (date: string | null) => void
  /**
   * Start following this walk on the map (#1041, frames `D9`-`D11`).
   *
   * Saved mode only, and omitted when this phone cannot place the hike on
   * its graph: following is a live position against a ROUTE, and there is no
   * route to be on when `resolved` is null - the card is leaning on its
   * stored cache, which is a list of figures rather than ground.
   */
  onFollow?: () => void
  /**
   * Open this walk in the builder at step 2 (#1373, D1). Saved mode only,
   * and only when the graph can place the hike - like `onFollow`, for the
   * same reason: editing is re-routing, and there is no route to edit when
   * the card is leaning on its stored cache.
   */
  onEdit?: () => void
  /**
   * Whether this walk is the one being followed right now. Editing it stops
   * following, and D1's rule is that the screen says so BEFORE it happens
   * rather than the next-turn card vanishing - so with this true, the edit
   * door asks first.
   */
  following?: boolean
  /** Review only - the rail's first stop, back to "Where do you want to
   *  go?" with the route kept (#1373, R3). */
  onBackToStepOne?: () => void
  /** The name as a field (frame 5a). Omitted, the name is a heading. */
  onRename?: (name: string) => void
  /**
   * The published water points along the walk, on its own mile axis
   * (lib/dayHikeWater.ts). Empty prints NOTHING: an absent row is the honest
   * state of a thin water layer, and "no water on this route" would be a
   * claim about the ground rather than about the data.
   */
  waterOnRoute?: readonly RouteWater[]
  /** The shelters and campsites the hiker picked as stops, placed on the
   *  walk (lib/dayHikeStops.ts). */
  stops?: readonly DayHikeStop[]
  /**
   * Just saved (frame 5c): the card opens as the landing after Save, with
   * the line saying where the walk now lives. `today` is the phone's own
   * day (YYYY-MM-DD), so the line can say whether that is now or on the
   * walk's date.
   */
  justSaved?: boolean
  today?: string
}

export function DayHikeCard({
  hike,
  resolved,
  bailOuts,
  units,
  pace,
  networkAvailable,
  mode,
  onSave,
  onClose,
  onDelete,
  onSetDate,
  onFollow,
  onEdit,
  following = false,
  onBackToStepOne,
  onRename,
  waterOnRoute = [],
  stops = [],
  justSaved = false,
  leadsToday = true,
  docked = false,
  today,
}: DayHikeCardProps) {
  // Two taps to destroy a walk somebody built, for More.tsx's discard reason:
  // Delete and its neighbour look alike, and one of them has no way back.
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  // D1's ask, in the same one-surface-continuing frame delete uses.
  const [confirmingEdit, setConfirmingEdit] = useState(false)
  // "Leave this with someone" (frame D6) replaces the card in the same
  // sheet frame - one surface continuing, the bar-to-card convention.
  const [leaving, setLeaving] = useState(false)
  // The name as typed, handed over on blur or Enter (lib/useDraftField.ts).
  const name = useDraftField(hike.name, (next) => onRename?.(next))

  const legs = resolved !== null ? resolved.legs : hike.figures.legs
  const miles = resolved !== null ? resolved.miles : hike.figures.miles
  const gaps = dayHikeGaps(hike)
  const stopMinutes = stoppingMinutes(stops)
  // Grouped by stretch where the app can see the seams, flat where it
  // cannot. The live resolution routes each segment separately and keeps
  // them apart; the cache holds one flat list, so it can only be handed over
  // as a stretch when there is exactly one stretch for it to be.
  const planTextLegs: PlanTextLegs =
    resolved !== null
      ? {
          kind: 'placed',
          byStretch: resolved.segments.map((segment) => segment.route.legs),
        }
      : hike.segments.length === 1
        ? { kind: 'placed', byStretch: [hike.figures.legs] }
        : { kind: 'unplaced', flat: hike.figures.legs }

  if (leaving) {
    return (
      <div className="day-hike-card">
        <LeaveWithSomeone
          hike={hike}
          // ONE derivation for both the miles and the trail names, and its
          // provenance with it. The card on screen prefers the live
          // resolution and says so in a sentence when it cannot have one;
          // handing the plain-text card the number without the sentence
          // would be the display outrunning its source on the artifact
          // somebody decides to worry from.
          figures={{
            miles,
            legs: planTextLegs,
            fromCache: resolved === null,
            gapMiles: gaps.reduce((total, gap) => total + gap.miles, 0),
            stretches: hike.segments.length,
          }}
          units={units}
          onClose={() => setLeaving(false)}
        />
      </div>
    )
  }

  // The live resolution first, the cache behind it - the same precedence the
  // miles and the legs above already use, and it arrived later for a reason
  // worth keeping in view.
  //
  // This line used to read `resolved?.climb ?? null`, with a comment saying
  // there was nothing to fall back TO: #1011 gave the network its climb and
  // did not give it to `DayHikeFigures`, so a saved hike held miles and legs
  // and no ascent. That is fixed as of 2026-08-27 and the fallback is now
  // real - but only for hikes saved since. `climb` is optional on the stored
  // shape precisely so that a hike saved before it existed reads `undefined`
  // and lands here as null, indistinguishable on screen from a walk the graph
  // could not price, because on this card the two say the same thing: no
  // figure, no ≈time, nothing invented.
  //
  // The sentence above the figures is what keeps this honest. When `resolved`
  // is null the card already says the numbers are the ones stored at save
  // time, so a cached climb is covered by the same disclosure the cached
  // miles are - which is the condition CLAUDE.md's "never let a display
  // outrun its source" puts on printing it at all.
  const climb = resolved?.climb ?? hike.figures.climb ?? null
  // Descent goes in beside the climb (#900): `routeClimb` measured both, and
  // a hiker who set a descent penalty is asking for it to count on exactly
  // this kind of walk. `paceEstimate` returns the figure and its baseline in
  // one object, so the line below cannot print one without the other (#851).
  const estimate =
    climb === null
      ? null
      : paceEstimate(
          { distanceMi: miles, ascentFt: climb.gainFt, descentFt: climb.lossFt },
          pace,
        )

  // The orgs sentence counts organizations somebody actually named - legs the
  // export left unattributed are real trail but no org to credit, and "One
  // organization" over an unattributed walk would be an invented steward.
  // Concurrent orgs count too (#1115): a leg wearing one trail's name over
  // tread a second organization also designates still stands on that
  // organization's ground.
  const orgCount = distinctLegSources(legs).length
  const ground = hike.looped ? 'loop' : 'route'

  return (
    <div
      className="day-hike-card"
      role={docked ? 'region' : 'dialog'}
      aria-label={hike.name}
    >
      <button type="button" className="route-stops__close" onClick={onClose}>
        <span className="visually-hidden">Close the day hike</span>
        <span aria-hidden="true">×</span>
      </button>

      {/* Step 3 of three, on the review (#1373, frame 5a): the route you
          chose, read before it is saved. Step 2 is the map behind this
          card and step 1 the question before it; both stay doors with the
          route kept (R3). A SAVED card is not on the spine - it is a record
          opened from a shelf - so it carries no rail. */}
      {mode === 'review' && (
        <StepRail
          step={3}
          kind={HIKER_MODE_LABELS.day}
          onStep={(step) => {
            if (step === 2) onClose()
            else if (step === 1) onBackToStepOne?.()
          }}
        />
      )}

      {justSaved && <p className="day-hike-card__eyebrow">Saved</p>}

      <div className="day-hike-card__head">
        {onRename === undefined ? (
          <h2 className="day-hike-card__title">{hike.name}</h2>
        ) : (
          // The name as a field (frame 5a), so a walk named off its longest
          // leg - "Pine Meadow Trail" - can be called what the hiker calls
          // it. The heading role stays on the text for the dialog's name.
          <label className="day-hike-card__name">
            <span className="day-hike-card__heading">Name</span>
            <input
              type="text"
              value={name.draft}
              maxLength={80}
              onChange={(event) => name.setDraft(event.target.value)}
              onBlur={name.flush}
              onKeyDown={(event) => {
                if (event.key === 'Enter') name.flush()
              }}
            />
          </label>
        )}
        <span className="day-hike-card__when">
          {hike.date !== null ? dayLongDateLabel(hike.date) : 'no date yet'}
          {hike.looped && <span className="day-hike-card__badge">LOOP</span>}
        </span>
      </div>

      <p className="day-hike-card__figures">
        {formatDistance(miles, units)} · {legs.length}{' '}
        {legs.length === 1 ? 'leg' : 'legs'}
        {climb !== null && (
          <>
            {' · '}
            <span className="day-hike-card__climb">
              +{formatElevation(climb.gainFt, units)} / −
              {formatElevation(climb.lossFt, units)}
            </span>
          </>
        )}
        {estimate !== null && ` · ${estimate.text} walking`}
      </p>

      {/* What that time was adjusted from, when it was adjusted at all -
          absent at the standard pace, which is most hikers (#851). */}
      {estimate?.relativeLine != null && (
        <p className="day-hike-card__baseline">{estimate.relativeLine}</p>
      )}

      {estimate !== null && (
        // TWO DIFFERENT WARNINGS, and neither substitutes for the other.
        //
        // The first is what the number MEASURES: this is moving time, whatever
        // pace it was priced at, and a hiker reading "≈3h 10m" as when they are
        // back at the car is out by however long they sat at the view. The
        // storyboard (frame D5) names this sentence as one of the two reasons
        // that screen exists - "the sentence that stops ≈3h10m being read as a
        // promise" - and #1008 shipped the figure without it. The trips side
        // had carried its own all along (PlanTargetSheet: "Naismith counts
        // walking - not lunch, not water, not the forty minutes you'll spend
        // at the shelter"), which left the asymmetry the wrong way round: the
        // day-hiker is the persona planning somewhere new, least likely to
        // know what moving time excludes. #1042.
        //
        // #1040 made this MORE necessary rather than less: the figure is now
        // priced at the hiker's OWN pace, so somebody who told the app they
        // walk at 2 mph gets a number that looks personal and still counts no
        // stops at all. A tailored estimate invites more trust, not less.
        //
        // The second is how PRECISE it is - the maintainer's decision,
        // 2026-08-25, in the hiker's own words, and kept here verbatim.
        // Cumulative gain from a 10 m elevation model is not exact; published
        // guidebook figures for one walk routinely differ, and on rolling
        // ground like this the pipeline's own check reads +18.8% against a
        // maintaining club (pipeline/reference/published_gain.json).
        //
        // A hiker can believe the second and still be an hour late because of
        // the first. ONE note rather than two stacked ones, because two
        // `role="note"` paragraphs in a row read as boilerplate and get
        // skipped - which is how the sentence that matters gets lost. The
        // baseline line above is a different thing again: what the estimate
        // was adjusted FROM, not what it leaves out.
        //
        // Guarded on the ESTIMATE, not the climb: the two are the same
        // condition today (`estimate` is null exactly when `climb` is), but
        // the time is what makes this note necessary.
        <p className="day-hike-card__note" role="note">
          Moving time — it knows nothing about lunch, a swim, or half an hour at the view.
          Climb and time are estimates from the best elevation data available — expect
          other sources to differ.
        </p>
      )}

      {onSetDate !== undefined && (
        // The one field on this card, because two other surfaces read it:
        // the list splits and sorts by it, and the trailhead door says
        // "planned for today" from it. Clearing the input clears the date -
        // an undated day hike is a first-class state, not an error.
        <label className="day-hike-card__date">
          <span className="day-hike-card__heading">When</span>
          <input
            type="date"
            value={hike.date ?? ''}
            onChange={(event) =>
              onSetDate(event.target.value === '' ? null : event.target.value)
            }
          />
        </label>
      )}

      {resolved === null && (
        // Which of the two honest reasons applies changes what a hiker can do
        // about it: get the trail network onto this phone, or accept the walk
        // has drifted off the published network.
        //
        // NOT "yet" (#1049). That word promised an arrival on the same
        // evidence chrome/PlanKindSheet.tsx was promising a data sync, and on
        // production there is no graph to arrive at all (#1048). This card
        // does not need to say WHICH absence - it is about which figures you
        // are reading - so it says the fact and stops.
        <p className="day-hike-card__note" role="note">
          {networkAvailable
            ? 'This phone’s current trail map can’t place this walk, so these are the figures from the day it was saved — and ways off can’t be worked out.'
            : 'This phone has no trail network, so these are the figures from the day this hike was saved — and ways off can’t be worked out.'}
        </p>
      )}

      {/* WATER ON ROUTE (frame 5a): the published water points the walk
          passes, at the mile it reaches them. Absent rather than "none"
          when there are none - lib/dayHikeWater.ts's header is the reason,
          and it is the safety reason. Each row is the map's own pin at row
          scale (chrome/PoiRow.tsx), so the shape a hiker learns here is the
          one they look for on the ground. */}
      {waterOnRoute.length > 0 && (
        <section className="day-hike-card__section">
          <h3 className="day-hike-card__heading">Water on route</h3>
          <ul className="day-hike-card__rows">
            {waterOnRoute.map((water) => (
              <li key={`${water.poiId}:${water.alongMi}`}>
                <PoiRow
                  kind="water"
                  title={water.name}
                  meta={[
                    `${formatDistance(water.alongMi, units)} in`,
                    water.offCourseFeet >= WATER_SAID_OFF_FEET
                      ? `${formatShortDistance(water.offCourseFeet, units)} off the walk`
                      : null,
                  ]
                    .filter((part) => part !== null)
                    .join(' · ')}
                />
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* The stops the hiker chose, with the two facts they chose them on -
          the builder's row (chrome/DayHikePanel.tsx) said again where the
          walk is read whole. Each figure only where it was published:
          absent capacity is not zero, absent water is not "no water". */}
      {stops.length > 0 && (
        <section className="day-hike-card__section">
          <h3 className="day-hike-card__heading">Shelters &amp; campsites</h3>
          <ul className="day-hike-card__rows">
            {stops.map((stop) => {
              // A stop's `mile` is the walk's own axis - trail miles from
              // the first tap (lib/dayHikeStops.ts), a distance and not the
              // pipeline's marker - so it converts like any distance, and
              // is named as one here for test/unitDisplay.test.ts's guard.
              const alongMi = stop.mile
              return (
                <li key={stop.poiId}>
                  <PoiRow
                    kind={stop.type}
                    title={stop.name}
                    meta={[
                      `${formatDistance(alongMi, units)} in`,
                      stop.capacity !== undefined ? `sleeps ${stop.capacity}` : null,
                      stop.waterDistanceFt !== undefined
                        ? `water ${formatShortDistance(
                            Math.max(MIN_STATED_FEET, stop.waterDistanceFt),
                            units,
                          )}`
                        : null,
                      stop.offCourseFeet > STOP_FAR_OFF_COURSE_FEET
                        ? `${formatShortDistance(stop.offCourseFeet, units)} off the walk`
                        : null,
                    ]
                      .filter((part) => part !== null)
                      .join(' · ')}
                  />
                </li>
              )
            })}
          </ul>
          {stopMinutes !== null && (
            <p className="day-hike-card__note">
              Stops add about {stopMinutes} min, on top of the walking.
            </p>
          )}
        </section>
      )}

      {legs.length > 0 && (
        <section className="day-hike-card__section">
          <h3 className="day-hike-card__heading">Legs</h3>
          {/* Per-leg miles print again since #1002: legs are priced at the
              metres actually walked - ends scaled to the taps, re-walked
              ground counted per pass - so a leg and the total above finally
              agree about the same ground. */}
          {legs.map((leg, at) => (
            <div className="day-hike-card__row" key={`${leg.name ?? 'leg'}-${at}`}>
              {/* The blaze, as the paint and nothing else - the legend's own
                  swatch, back with a caller (#1112). Through
                  `blazePaintColor` rather than a second table, so a leg's
                  swatch and the line the map draws for that leg are the same
                  hue by construction; lib/blaze.ts holds the closed palette
                  and #782's admission bar.

                  The WORD rides underneath for a screen reader, which is the
                  freshness dots' arrangement on Today (screens/Today.tsx) and
                  is not decoration: half the network has no hue to show
                  (measured against the published graph, 2026-08-27: 48.1% of
                  edges are `Unknown`, 1.8% `None`, 1.3% `Other`), and those
                  all paint the same neutral grey. Grey is the app's own
                  sentence for "we do not know this" - the colour the map
                  paints such a line, and the corridor view spends on miles
                  with no club recorded - so the swatch agrees with the map
                  rather than inventing a fourth meaning. `blazeLabel` is
                  what tells the three neutrals apart in words: "Blaze not
                  recorded", "Unblazed", "Other blaze". */}
              <span
                className="day-hike-card__blaze"
                style={{
                  backgroundColor:
                    leg.blaze_color === null
                      ? NEUTRAL_BLAZE_COLOR
                      : blazePaintColor(leg.blaze_color),
                }}
              >
                <span className="visually-hidden">{blazeLabel(leg.blaze_color)}</span>
              </span>
              <span className="day-hike-card__row-name">
                {leg.name ?? 'Unnamed trail'}
              </span>
              <span className="day-hike-card__row-figures">
                {formatDistance(leg.miles, units)}
              </span>
            </div>
          ))}
        </section>
      )}

      {resolved !== null && (
        <section className="day-hike-card__section">
          <h3 className="day-hike-card__heading">If you need to get off</h3>
          {bailOuts.length === 0 ? (
            // The decided answer (#980): said, never omitted. The most
            // safety-relevant sentence here, and the block exists to hold it.
            <p className="day-hike-card__note">
              No marked trail leaves this {ground}. The way off is the way you came.
            </p>
          ) : (
            bailOuts.map((bailOut, at) => (
              <div className="day-hike-card__row" key={`${bailOut.miles}-${at}`}>
                {/* formatDistance, not mileMarker: this is a walked length
                    (it converts for a metric hiker), not a name on the one
                    trail with a mile axis - planDisplay.ts draws the line. */}
                <span className="day-hike-card__row-mile">
                  at {formatDistance(bailOut.miles, units)}
                </span>
                <span className="day-hike-card__row-name">
                  {bailOut.name ?? 'Unnamed trail'}
                  {bailOut.blaze_color !== null && ` (${bailOut.blaze_color})`}
                </span>
              </div>
            ))
          )}
        </section>
      )}

      {/* A stretch with no trail under it is part of the walk (#935's
          deliberate-gap answer) and prints as one - straight-line, because
          the ground actually walked across a gap is the hiker's own guess,
          which is what a gap IS. The builder writes single-segment hikes
          today, so this arrives by sync from a future client; the card is
          ready for it rather than silent about it.

          ONE ROW, COUNTING STRETCHES, rather than a row per gap naming
          "stretch 2": nothing on this card is numbered - the legs list is
          trail names, and a segment holds several legs - so a row pointing
          at a stretch the card never labels sends a hiker looking for
          something that is not there. How many stretches the walk is in IS
          on the card, in this sentence, which is what makes the total
          placeable. */}
      {gaps.length > 0 && (
        <p className="day-hike-card__gap" role="note">
          {formatDistance(
            gaps.reduce((total, gap) => total + gap.miles, 0),
            units,
          )}{' '}
          with no trail under it, straight across
          {hike.segments.length > 2
            ? `, between the ${hike.segments.length} stretches of this walk`
            : ', between the two stretches of this walk'}
          . We won&rsquo;t route you across it — that stretch is yours.
        </p>
      )}

      {orgCount > 0 && (
        <p className="day-hike-card__orgs">
          {COUNT_WORDS[orgCount] ?? String(orgCount)}{' '}
          {orgCount === 1 ? 'organization keeps' : 'organizations keep'} this {ground}{' '}
          walkable.
        </p>
      )}

      {mode === 'review' ? (
        // SAVE IS THE LAST BUTTON, NOT A STEP (D7): the foot of step 3 is
        // the way back to the route and the commit, nothing between.
        <div className="day-hike-card__foot">
          <button
            type="button"
            className="day-hike-card__back"
            onClick={onClose}
            aria-label="Back to Route, step 2"
          >
            <span aria-hidden="true">‹ </span>Route
          </button>
          <button type="button" className="plan__primary" onClick={onSave}>
            Save this day hike
          </button>
        </div>
      ) : (
        <>
          {/* Where the walk now lives (frame 5c), said once, on the card
              that opens after Save. Today leads with a walk dated today
              (screens/Today.tsx), so the sentence says WHEN rather than
              promising a place a walk with no date will not take. */}
          {justSaved && (
            <p className="day-hike-card__note" role="status">
              {hike.date === null
                ? leadsToday
                  ? 'Give it a date and it leads Today that day.'
                  : 'Give it a date and Today lists it that day.'
                : hike.date === today
                  ? leadsToday
                    ? 'This walk is now the top card on Today.'
                    : 'Today lists it with your other hikes.'
                  : leadsToday
                    ? `It leads Today on ${dayLongDateLabel(hike.date)}.`
                    : `Today lists it on ${dayLongDateLabel(hike.date)}, with your other hikes.`}
            </p>
          )}
          {/* THE DOOR ONTO THE GROUND IS THE PRIMARY (frame 5c, D4's one
              grammar: Today's card, this one and the follow card all say
              "Walk this"). It used to read "Follow this hike on the map"
              under "Leave this with someone", which the earlier frame D6
              made the card's one primary; the flow review reverses that
              order - a walk is what the card is for, and the card somebody
              else keeps is one row under it. Absent, not disabled, when the
              graph cannot place the hike - a greyed control is a promise
              the app cannot say why it is not keeping. */}
          {onFollow !== undefined && resolved !== null && (
            <button type="button" className="plan__primary" onClick={onFollow}>
              Walk this
            </button>
          )}
          {/* The only safety-shaped thing in the day flow that is not a map
              (frame D6): the plain-text card somebody at home keeps. */}
          <button
            type="button"
            className="day-hike-card__follow"
            onClick={() => setLeaving(true)}
          >
            Leave it with someone<span aria-hidden="true"> ›</span>
          </button>
          {/* The door into step 2 (#1373, D1). A saved walk used to be
              final: the only way to change a stop was to delete the hike
              and tap it out again. Absent over the stored cache, like the
              follow door - the builder needs the graph to place the taps.

              WHEN THE WALK IS BEING FOLLOWED, THE DOOR ASKS FIRST. Following
              is a claim about a route; the moment the route is being edited
              the claim is false, and a hiker who loses the next-turn card
              without being told loses their trust in it. The sentence is
              the design's, verbatim. The ground already walked is kept
              because nothing here touches it - the walked ranges and the
              journal never depended on following. */}
          {onEdit !== undefined &&
            resolved !== null &&
            (confirmingEdit ? (
              <div
                className="day-hike-card__confirm day-hike-card__confirm--stack"
                role="group"
                aria-label="Editing a hike you are walking"
              >
                <p className="day-hike-card__confirm-sentence">
                  You are walking this one. Changing the route stops following it &mdash;
                  the next-turn card goes away and the walk you have already done is kept.
                </p>
                <div className="day-hike-card__confirm">
                  <button type="button" className="day-hike-card__quiet" onClick={onEdit}>
                    Edit it
                  </button>
                  <button
                    type="button"
                    className="day-hike-card__quiet"
                    onClick={() => setConfirmingEdit(false)}
                  >
                    Keep following
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="day-hike-card__quiet"
                onClick={() => (following ? setConfirmingEdit(true) : onEdit())}
              >
                Edit the route
              </button>
            ))}
          {confirmingDelete ? (
            <div className="day-hike-card__confirm">
              <span>Delete this day hike?</span>
              <button type="button" className="day-hike-card__quiet" onClick={onDelete}>
                Delete
              </button>
              <button
                type="button"
                className="day-hike-card__quiet"
                onClick={() => setConfirmingDelete(false)}
              >
                Keep it
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="day-hike-card__quiet"
              onClick={() => setConfirmingDelete(true)}
            >
              Delete this day hike
            </button>
          )}
        </>
      )}
    </div>
  )
}
