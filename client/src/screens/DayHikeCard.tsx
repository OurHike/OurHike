// The finished day hike (#980, frame `1l`) - the blocks with a source today.
//
// The frame is the richest in its group and this card deliberately renders
// LESS of it than it draws. What ships: the legs with each organization's own
// name on its trail, the walked miles, the LOOP badge, the ways off, and the
// one-line credit to the orgs that keep the ground walkable. What waits, and
// on what (#980 keeps the ledger): the turn list (a naming rule #934 left
// open), "Starts at · Parking" (#981's pipeline data), the on-route POI
// counts (a policy #768's rule does not cover), the ± elevation and ≈time
// (no elevation exists for network trails - the same reason the builder bar
// prices nothing), and the frame's "Chip in ›" (no org's donate wording
// exists anywhere in the registry or the stewards export to speak with, and
// inventing one would be this app putting words in a steward's mouth).
//
// The figures prefer the LIVE resolution and fall back to the stored cache
// with a sentence saying so - never silently. lib/dayHikes.ts's provenance
// note is the rule: the cache was computed from the graph the phone held at
// save time, and a card that prints it over today's different graph without
// comment is a display outrunning its source.

import { useState } from 'react'

import type { BailOut, ResolvedDayHike } from '../lib/dayHikeCard'
import type { DayHike } from '../lib/dayHikes'
import { dayLongDateLabel } from '../lib/planDisplay'
import { orgLabelFrom, type Stewards } from '../lib/stewards'
import { formatDistance, type UnitSystem } from '../lib/units'
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
}: DayHikeCardProps) {
  // Two taps to destroy a walk somebody built, for More.tsx's discard reason:
  // Delete and its neighbour look alike, and one of them has no way back.
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const orgLabel = orgLabelFrom(stewards)
  const legs = resolved !== null ? resolved.legs : hike.figures.legs
  const miles = resolved !== null ? resolved.miles : hike.figures.miles

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
          {/* Name and steward only - deliberately NO per-leg miles, though
              the frame draws them and RouteLeg carries a number. That number
              comes from legsFromEdges over whole edges, so a leg entered or
              left mid-edge (every tapped walk) overstates its ends, and an
              out-and-back undercounts re-walked ground - the route TOTAL is
              summed per tapped pair and is right, which is exactly why the
              two must not print side by side. The column returns when the
              legs are priced pair-wise too. */}
          {legs.map((leg, at) => (
            <div className="day-hike-card__row" key={`${leg.name ?? 'leg'}-${at}`}>
              <span className="day-hike-card__row-name">
                {leg.name ?? 'Unnamed trail'}
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
      ) : confirmingDelete ? (
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
    </div>
  )
}
