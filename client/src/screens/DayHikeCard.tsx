// The finished day hike (#980, frame `1l`) - the blocks with a source today.
//
// The frame is the richest in its group and this card deliberately renders
// LESS of it than it draws. What ships: the legs with each organization's own
// name on its trail, the walked miles, the LOOP badge, the ways off, the
// one-line credit to the orgs that keep the ground walkable, and - since
// #1008 - a date field, the gap rows for a multi-segment walk, and the
// "Leave this with someone" door (frame D6, screens/LeaveWithSomeone.tsx).
// What waits, and on what (#980 keeps the ledger): the turn list (a naming
// rule #934 left open), "Starts at · Parking" (#981's pipeline data), the
// on-route POI counts (a policy #768's rule does not cover), the ± elevation
// and ≈time (no elevation exists for network trails - the same reason the
// builder bar prices nothing), and the frame's "Chip in ›" (no org's donate
// wording exists anywhere in the registry or the stewards export to speak
// with, and inventing one would be this app putting words in a steward's
// mouth).
//
// The figures prefer the LIVE resolution and fall back to the stored cache
// with a sentence saying so - never silently. lib/dayHikes.ts's provenance
// note is the rule: the cache was computed from the graph the phone held at
// save time, and a card that prints it over today's different graph without
// comment is a display outrunning its source.

import { useState } from 'react'

import type { BailOut, ResolvedDayHike } from '../lib/dayHikeCard'
import type { DayHike } from '../lib/dayHikes'
import type { PlanTextLegs } from '../lib/dayHikePlanText'
import { dayHikeGaps } from '../lib/dayHikeShelf'
import { dayLongDateLabel } from '../lib/planDisplay'
import { orgLabelFrom, type Stewards } from '../lib/stewards'
import { formatDistance, type UnitSystem } from '../lib/units'
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
  stewards: Stewards
  units: UnitSystem
  networkAvailable: boolean
  /** review: Done pressed, nothing stored yet - Save is the primary action.
   *  saved: opened from the Plan tab, where delete lives. */
  mode: 'review' | 'saved'
  onSave?: () => void
  onClose: () => void
  onDelete?: () => void
  /** Set or clear the hike's date (#1008). The list and the trailhead door
   *  both read it, which is what made a card with no way to write one a
   *  gap rather than a nicety. */
  onSetDate?: (date: string | null) => void
}

export function DayHikeCard({
  hike,
  resolved,
  bailOuts,
  stewards,
  units,
  networkAvailable,
  mode,
  onSave,
  onClose,
  onDelete,
  onSetDate,
}: DayHikeCardProps) {
  // Two taps to destroy a walk somebody built, for More.tsx's discard reason:
  // Delete and its neighbour look alike, and one of them has no way back.
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  // "Leave this with someone" (frame D6) replaces the card in the same
  // sheet frame - one surface continuing, the bar-to-card convention.
  const [leaving, setLeaving] = useState(false)

  const orgLabel = orgLabelFrom(stewards)
  const legs = resolved !== null ? resolved.legs : hike.figures.legs
  const miles = resolved !== null ? resolved.miles : hike.figures.miles
  const gaps = dayHikeGaps(hike)
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

  // The orgs sentence counts organizations somebody actually named - legs the
  // export left unattributed are real trail but no org to credit, and "One
  // organization" over an unattributed walk would be an invented steward.
  const orgCount = new Set(
    legs.map((leg) => leg.source).filter((source) => source !== null),
  ).size
  const ground = hike.looped ? 'loop' : 'route'

  return (
    <div className="day-hike-card" role="dialog" aria-label={hike.name}>
      <button type="button" className="route-stops__close" onClick={onClose}>
        <span className="visually-hidden">Close the day hike</span>
        <span aria-hidden="true">×</span>
      </button>

      <div className="day-hike-card__head">
        <h2 className="day-hike-card__title">{hike.name}</h2>
        <span className="day-hike-card__when">
          {hike.date !== null ? dayLongDateLabel(hike.date) : 'no date yet'}
          {hike.looped && <span className="day-hike-card__badge">LOOP</span>}
        </span>
      </div>

      <p className="day-hike-card__figures">
        {formatDistance(miles, units)} · {legs.length}{' '}
        {legs.length === 1 ? 'leg' : 'legs'}
      </p>

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
        // about it: wait for a data sync, or accept the walk has drifted off
        // the published network.
        <p className="day-hike-card__note" role="note">
          {networkAvailable
            ? 'This phone’s current trail map can’t place this walk, so these are the figures from the day it was saved — and ways off can’t be worked out.'
            : 'This phone hasn’t got the trail network yet, so these are the figures from the day this hike was saved — and ways off can’t be worked out.'}
        </p>
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
              <span className="day-hike-card__row-name">
                {leg.name ?? 'Unnamed trail'}
              </span>
              <span className="day-hike-card__row-figures">
                {formatDistance(leg.miles, units)}
              </span>
              <span className="day-hike-card__row-org">{orgLabel(leg.source)}</span>
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
              <div
                className="day-hike-card__row day-hike-card__row--mile"
                key={`${bailOut.miles}-${at}`}
              >
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
                <span className="day-hike-card__row-org">{orgLabel(bailOut.source)}</span>
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
        <>
          <button type="button" className="plan__primary" onClick={onSave}>
            Save this day hike
          </button>
          <button type="button" className="day-hike-card__quiet" onClick={onClose}>
            Back to the map
          </button>
        </>
      ) : (
        <>
          {/* The saved hike's one primary action (frame D6): the only
              safety-shaped thing in the day flow that is not a map, and
              the thing a hiker opens this card for on the morning of. */}
          <button
            type="button"
            className="plan__primary"
            onClick={() => setLeaving(true)}
          >
            Leave this with someone
          </button>
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
