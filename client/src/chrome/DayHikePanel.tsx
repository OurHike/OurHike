// The day-hike builder's panel: the rail on a desktop, the top panel on a
// phone (#1194, the Claude Design handoff for frame `1j`).
//
// WHAT THIS IS FOR, IN ONE SENTENCE: the map was too small, and everything
// that is not the map moved out of the way.
//
// Before this, the builder was `chrome/DayHikePickBar.tsx` alone - a sheet
// anchored to the bottom of the canvas at `max-height: 60%`. On the one
// screen whose whole job is pointing at trails, a hiker mid-build could be
// looking at 40% map. Above 900px it was worse and read as an omission: every
// other wide surface in this app got its room (the plan bench, the planning
// station, the persistent legend) and the builder still wore the phone's
// bottom sheet on a 27" display.
//
// THE BAR DID NOT MOVE, AND THAT IS THE MAINTAINER'S CALL
//
// The handoff puts the whole panel at the TOP of a phone with one floating
// "Save hike" CTA at the bottom. The instruction taken instead was: the
// INFORMATION goes to the top and the BUTTONS stay at the bottom. That is
// also what this repository already believed - src/desktop.css says it
// outright, that "the bar's position at the bottom of a phone is a thumb-reach
// decision" - and a builder used one-handed on a trail is exactly the case
// that decision was made for.
//
// So `DayHikePickBar` keeps the actions, keeps Cancel, and keeps its place at
// the foot of the canvas. This panel is additive: it is everything the bar
// was not showing. The bar's own suite passes untouched across this change,
// which is the contract chrome/routeBuilderPanel.tsx names for a move like
// this one - a test needing an edit would have been evidence the split
// changed something.
//
// CANCEL: THE HANDOFF HAS NONE, ON EITHER BREAKPOINT
//
// Desktop offers "Reset", which clears the route and leaves the hiker in the
// builder; the phone frame offers nothing at all. There is no way out. The
// shipped bar has had a Cancel since #978 and it stays exactly where it was -
// this was raised on the design before a line of it was built, and is
// recorded here because a redesign quietly dropping an exit is the kind of
// regression that reads as a bug in the app rather than a gap in the mock.
//
// WHY THERE IS NO ELEVATION PROFILE HERE YET, AND THE CLAIM THAT WAS WRONG
//
// This file shipped saying the samples do not exist, and the line a hiker
// read said so too - "these trails publish how much they climb, not the shape
// of it". Both were false on the day they were written.
//
// What happened: #1194 read pipeline/export_network_elevation.py's header,
// which says dense samples are "worth publishing only if a chart is ever
// drawn for a network route, and then as a fourth artifact fetched when that
// chart opens", and stopped there. That sentence describes a decision taken
// BEFORE the artifact existed. It has been built since -
// pipeline/export_network_profile.py publishes trail_graph_profile.json, a
// dense sample array per edge at 25 m, index-aligned with the other three;
// App.tsx already fetches it into `graphProfile`; lib/walkProfile.ts already
// turns a walk into ribbon samples on the walk's own mile axis. All of it
// landed in #1119, closing #1045, before #1194 was written. A followed day
// hike draws it today.
//
// So the honest sentence is about THIS SCREEN and nothing else: the builder
// draws no profile yet because nobody has wired one here. What is genuinely
// missing is narrow - `walkProfile` takes `WalkStep[]`, and lib/dayHikeWalk.ts
// builds those from a saved `ResolvedDayHike` rather than from a draft being
// tapped out. That is #1210.
//
// THE LESSON, because it cost a false claim in front of hikers: a module
// header states what was true when it was written. "The data does not exist"
// is a claim about the bucket, and it wants checking against the bucket
// rather than against a comment.

import { useId } from 'react'

import { blazePaintColor } from '../lib/blaze'
import type { DraftStatus, DayHikeDraft } from '../lib/dayHikeDraft'
import { routeRows, turnMarks, type RouteRow } from '../lib/dayHikeRows'
import {
  STOP_FAR_OFF_COURSE_FEET,
  stoppingMinutes,
  type DayHikeStop,
} from '../lib/dayHikeStops'
import {
  LABEL_LAYERS,
  labelLayerShown,
  tierBadge,
  type HiddenLabelLayers,
  type LabelLayerKey,
} from '../lib/mapLabelLayers'
import type { PaceEstimate } from '../lib/pace'
import {
  formatDistance,
  formatElevation,
  formatShortDistance,
  MIN_STATED_FEET,
} from '../lib/units'
import type { UnitSystem } from '../lib/units'
import '../screens/plan.css'

export interface DayHikePanelProps {
  draft: DayHikeDraft
  status: DraftStatus
  stops: readonly DayHikeStop[]
  units: UnitSystem
  /** The routed walk's time with its baseline, or null when unpriceable. */
  walking: PaceEstimate | null
  hiddenLabels: HiddenLabelLayers
  onToggleLabel: (key: LabelLayerKey) => void
  onRemoveStop: (poiId: string) => void
  onRemoveTurn: (ordinal: number) => void
  /** Phone only: whether the detail body is open. Always open on a desktop. */
  detailsOpen: boolean
  onToggleDetails: () => void
}

/**
 * The route's name, from its ends.
 *
 * The handoff generates "Reeves -> Route 106" from the first word of the
 * start node and the first two of the end. This app has no node labels to
 * take those from - a tap lands on an EDGE at a fraction (#928), not on a
 * named place - so the honest title is the trails the walk uses, which is
 * what the finished card already leads with.
 *
 * One trail names itself; two or more say so by count. Never a guess at a
 * destination: lib/lineDetail.ts refuses to name a spur's destination it
 * cannot resolve, and inventing "Reeves -> somewhere" here would be the same
 * invention one screen earlier.
 */
function routeTitle(status: DraftStatus): string {
  if (status.kind !== 'routed' || status.legs.length === 0) return 'A new day hike'
  const named = status.legs.map((leg) => leg.name).filter((name) => name !== null)
  if (named.length === 0) return 'A new day hike'
  if (named.length === 1) return named[0] as string
  const first = named[0] as string
  const last = named[named.length - 1] as string
  if (first === last) return first
  return `${first} to ${last}`
}

/** "3 legs · 1 shelter · 2 campsites", with zero clauses omitted. */
function routeSummary(status: DraftStatus, stops: readonly DayHikeStop[]): string {
  const parts: string[] = []
  if (status.kind === 'routed') {
    parts.push(`${status.legs.length} ${status.legs.length === 1 ? 'leg' : 'legs'}`)
  }
  const shelters = stops.filter((stop) => stop.type === 'shelter').length
  const campsites = stops.filter((stop) => stop.type === 'campsite').length
  if (shelters > 0) parts.push(`${shelters} ${shelters === 1 ? 'shelter' : 'shelters'}`)
  if (campsites > 0) {
    parts.push(`${campsites} ${campsites === 1 ? 'campsite' : 'campsites'}`)
  }
  return parts.length > 0 ? parts.join(' · ') : 'Nothing picked yet'
}

export function DayHikePanel({
  draft,
  status,
  stops,
  units,
  walking,
  hiddenLabels,
  onToggleLabel,
  onRemoveStop,
  onRemoveTurn,
  detailsOpen,
  onToggleDetails,
}: DayHikePanelProps) {
  const bodyId = useId()
  const routed = status.kind === 'routed' ? status : null
  const rows = routed === null ? [] : routeRows(routed.legs, stops)
  const turns = turnMarks(draft)
  const stopping = stoppingMinutes(stops)

  return (
    <section className="day-hike-panel" aria-label="Your route">
      <div className="day-hike-panel__head">
        <div className="day-hike-panel__title-block">
          <p className="day-hike-panel__eyebrow">Your route</p>
          <h2 className="day-hike-panel__title">{routeTitle(status)}</h2>
          <p className="day-hike-panel__summary">{routeSummary(status, stops)}</p>
        </div>
        {/* Phone only - src/desktop.css hides it, where the rail is always
            open and a control that cannot change anything is noise. */}
        <button
          type="button"
          className="day-hike-panel__details-toggle"
          aria-expanded={detailsOpen}
          aria-controls={bodyId}
          onClick={onToggleDetails}
        >
          {detailsOpen ? 'Hide' : 'Details'}
        </button>
      </div>

      <dl className="day-hike-panel__stats">
        <div className="day-hike-panel__stat">
          <dt>Distance</dt>
          <dd>{routed === null ? '—' : formatDistance(routed.miles, units)}</dd>
        </div>
        {/* The emphasised metric, per the handoff - climb is what makes a
            day-hike time honest, and it is the figure a flat mileage hides. */}
        <div className="day-hike-panel__stat day-hike-panel__stat--climb">
          <dt>Climb</dt>
          <dd>
            {routed?.climb == null
              ? 'Unknown'
              : formatElevation(routed.climb.gainFt, units)}
          </dd>
        </div>
        <div className="day-hike-panel__stat">
          <dt>Walking</dt>
          {/* The bar's own rule, not a second one: lib/pace.ts has already
              applied naismith.ts's `≈` and five-minute step, and no surface
              re-rounds it. A walk this phone cannot price prints nothing
              rather than a zero. */}
          <dd>{walking === null ? '—' : walking.text}</dd>
        </div>
      </dl>

      <div className="day-hike-panel__body" id={bodyId} hidden={!detailsOpen}>
        {/* NOTHING TO SAY BEFORE THERE IS A WALK. With no route yet the stats
            row above already reads "— / Unknown / —", and repeating that as a
            paragraph is three lines of chrome on the screen whose complaint
            was that the chrome had taken the map. The block returns the
            moment a first leg routes. */}
        {routed !== null && (
          <div className="day-hike-panel__climb">
            <p className="day-hike-panel__section-head">Climb</p>
            {routed?.climb == null ? (
              <p className="day-hike-panel__unknown">
                This phone can&rsquo;t price the climb on this walk &mdash; either the
                elevation download hasn&rsquo;t landed, or one of these trails has never
                been measured.
              </p>
            ) : (
              <>
                <p className="day-hike-panel__climb-figures">
                  <span className="day-hike-panel__climb-up">
                    &uarr; {formatElevation(routed.climb.gainFt, units)}
                  </span>
                  <span className="day-hike-panel__climb-down">
                    &darr; {formatElevation(routed.climb.lossFt, units)}
                  </span>
                </p>
                {/* The handoff's rail draws an elevation silhouette here, and
                  this says why one is not drawn YET - a fact about this
                  screen, which is all it may honestly claim. It used to say
                  the shape was not published, which was false the day it was
                  written: see this file's header, and #1210 for the wiring
                  that is genuinely missing. */}
                <p className="day-hike-panel__note">No profile drawn here yet.</p>
              </>
            )}
            {stopping !== null && (
              <p className="day-hike-panel__note">
                Stops add about {stopping} min, on top of the walking.
              </p>
            )}
          </div>
        )}

        <div className="day-hike-panel__rows">
          <p className="day-hike-panel__section-head">
            Route order &middot; tap the map to add
          </p>
          {rows.length === 0 ? (
            <p className="day-hike-panel__empty">
              Nothing yet. Tap a trail on the map to start walking it, then tap a shelter
              or campsite to add a stop.
            </p>
          ) : (
            <ol className="day-hike-panel__list">
              {rows.map((row) => (
                <RouteRowItem
                  key={row.key}
                  row={row}
                  units={units}
                  onRemoveStop={onRemoveStop}
                />
              ))}
            </ol>
          )}
        </div>

        {/* The turns, apart from the ordered list and deliberately so -
            lib/dayHikeRows.ts explains that a tap in the middle of a leg has
            no honest mile, and a row with no mile in a mile-ordered list is a
            row in the wrong place. Numbered to match the marks on the map. */}
        {turns.length > 0 && (
          <div className="day-hike-panel__turns">
            <p className="day-hike-panel__section-head">Your taps</p>
            <ul className="day-hike-panel__turn-list">
              {turns.map((turn) => (
                <li key={turn.ordinal}>
                  <button
                    type="button"
                    className="day-hike-panel__turn"
                    onClick={() => onRemoveTurn(turn.ordinal)}
                  >
                    <span aria-hidden="true">{turn.label}</span>
                    <span className="day-hike-panel__sr">
                      Remove tap {turn.label}
                      {turn.endsStretch ? ', which ends a stretch' : ''}
                    </span>
                    <span className="day-hike-panel__turn-x" aria-hidden="true">
                      &times;
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* OUTSIDE the collapsible body on purpose: the label row is how a
          hiker finds what to tap next, so it has to be reachable while the
          details are closed and the map is at its tallest. That is the one
          place this panel departs from the handoff's phone frame, which puts
          the chips below the collapsed body and above the map - the same
          position, arrived at from the other direction. */}
      <div className="day-hike-panel__labels">
        <p className="day-hike-panel__section-head">Map labels</p>
        <div className="day-hike-panel__label-grid">
          {LABEL_LAYERS.map((spec) => {
            const shown = labelLayerShown(hiddenLabels, spec.key)
            return (
              <button
                key={spec.key}
                type="button"
                className="day-hike-panel__label-toggle"
                aria-pressed={shown}
                onClick={() => onToggleLabel(spec.key)}
              >
                <span className="day-hike-panel__label-name">{spec.label}</span>
                <span className="day-hike-panel__label-tier" aria-hidden="true">
                  {tierBadge(spec.tier)}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}

function RouteRowItem({
  row,
  units,
  onRemoveStop,
}: {
  row: RouteRow
  units: UnitSystem
  onRemoveStop: (poiId: string) => void
}) {
  if (row.kind === 'gap') {
    return (
      <li className="day-hike-panel__row day-hike-panel__row--gap">
        <span className="day-hike-panel__row-detail">
          {formatDistance(row.miles, units, 'fine')} with no trail under it
        </span>
      </li>
    )
  }

  if (row.kind === 'stop') {
    const far = row.stop.offCourseFeet > STOP_FAR_OFF_COURSE_FEET
    return (
      <li className="day-hike-panel__row day-hike-panel__row--stop">
        <span className="day-hike-panel__row-index" aria-hidden="true">
          &middot;
        </span>
        <span className="day-hike-panel__row-name">{row.stop.name}</span>
        <span className="day-hike-panel__row-detail">
          {row.stop.type === 'shelter' ? 'Shelter' : 'Campsite'} &middot; mile{' '}
          {row.stop.mile.toFixed(1)}
          {/* THE TWO FACTS A HIKER PICKS A STOP ON (#1198). They live on the
              waypoint card, and the card is unreachable while the builder owns
              the tap - so until now choosing where to spend the night meant
              choosing blind, on the screen built for choosing.

              ON THE ROW RATHER THAN BEHIND A TAP, which is better than the
              card would have been even if the card were reachable: a hiker
              deciding between two shelters reads both rows at once instead of
              opening and closing two sheets to compare four numbers.

              EACH APPEARS ONLY WHERE IT WAS PUBLISHED. Absent capacity is not
              zero and absent water is not "no water" - lib/dayHikeStops.ts
              carries both rules from StoredPoi, and a row inventing either
              would be inventing it about the thing being decided. */}
          {row.stop.capacity !== undefined && <> &middot; sleeps {row.stop.capacity}</>}
          {row.stop.waterDistanceFt !== undefined && (
            <>
              {' '}
              &middot; water{' '}
              {formatShortDistance(
                // The floor the card applies to the same published column, from
                // the one home both now read (lib/units.ts). A stop claiming a
                // hiker walks zero feet to water reads as a bug rather than as
                // the very short walk it asserts.
                Math.max(MIN_STATED_FEET, row.stop.waterDistanceFt),
                units,
              )}
            </>
          )}
          {/* Said, never priced. The walk out to a stop is ground the app has
              no evidence about - see lib/dayHikeStops.ts - so the distance is
              shown and the minutes are not invented. */}
          {far && (
            <>
              {' '}
              &middot; {formatShortDistance(row.stop.offCourseFeet, units)} off the walk
            </>
          )}
        </span>
        <button
          type="button"
          className="day-hike-panel__row-remove"
          onClick={() => onRemoveStop(row.stop.poiId)}
        >
          <span className="day-hike-panel__sr">Remove {row.stop.name}</span>
          <span aria-hidden="true">&times;</span>
        </button>
      </li>
    )
  }

  return (
    <li className="day-hike-panel__row day-hike-panel__row--leg">
      <span className="day-hike-panel__row-index" aria-hidden="true">
        {String(row.index).padStart(2, '0')}
      </span>
      <span
        className="day-hike-panel__blaze"
        aria-hidden="true"
        style={
          row.blazeColor === null
            ? undefined
            : { background: blazePaintColor(row.blazeColor) }
        }
      />
      <span className="day-hike-panel__row-name">{row.name ?? 'Unnamed trail'}</span>
      <span className="day-hike-panel__row-detail">
        {formatDistance(row.miles, units)} &middot; mile {row.fromMile.toFixed(1)}&ndash;
        {row.toMile.toFixed(1)}
      </span>
      {/* NO DELETE ON A LEG, and lib/dayHikeRows.ts argues it: a leg is what
          the router made of two taps, not something the hiker chose, so
          "delete this leg" has no defined effect. The taps below are the
          removable thing. */}
    </li>
  )
}
