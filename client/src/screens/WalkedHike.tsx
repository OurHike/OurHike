// A walk already done (#982), on its own screen.
//
// WHY THIS IS NOT DayHikeCard IN THE PAST TENSE
//
// The maintainer's decision, 2026-08-27: *"Today shouldn't have other day
// hikes. I think the previous hikes need to live on a different screen."*
// Which is #982's own argument arriving one level down from the comparison it
// makes with `screens/DaySummary.tsx`: two surfaces that look similar and know
// different things is the cheaper mistake. A card that has to keep asking
// which tense it is in answers the question twice for every future addition.
//
// So the differences are structural rather than cosmetic:
//
//   DayHikeCard                        this
//   ------------------------------     ------------------------------
//   a walk that might happen            a walk that did
//   ways off, follow, leave-with-       none of them - there is nothing
//     someone                             left to bail out of
//   an undated hike is first-class      a date, because a walk happened
//                                         on a day
//   nothing the hiker writes            the one line they write themselves
//
// WHAT IT MUST NOT DO, AND THE TEST THAT SAYS SO
//
// No score. No comparison against anything. No pace judgement, no "faster
// than", no streak. `Plan.test.tsx` carries the standing negative assertion
// and `DaySummary.test.tsx` mirrors it; this screen's own suite carries it
// too, because value #1 forbids prescriptive gamification and a screen about
// a walk somebody already finished is exactly where it would creep in.
//
// One adjustment rather than a copy: DaySummary's forbidden-word list contains
// `'was '`, which a pace baseline line trips. This screen prints no pace line
// at all - see below - so the list is inherited whole.
//
// THE FIGURES ARE THE CACHE, AND IT SAYS SO
//
// A finished walk is re-resolved against the live graph like any other, and
// falls back to what was stored - the same precedence and the same disclosure
// `DayHikeCard` makes. What this screen does NOT print is a walking time: the
// hiker walked it, and telling somebody how long the app thinks their own
// finished walk took is the app arguing with them about their afternoon.

import { useState } from 'react'

import type { ResolvedDayHike } from '../lib/dayHikeCard'
import { distinctLegSources, MAX_NOTE_CHARS, type DayHike } from '../lib/dayHikes'
import { dayLongDateLabel } from '../lib/planDisplay'
import { orgLabelFrom, type Stewards } from '../lib/stewards'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'
import './plan.css'

export interface WalkedHikeProps {
  hike: DayHike
  /** The walk against this phone's live graph, or null - then the stored
   *  figures stand, and the screen says which. */
  resolved: ResolvedDayHike | null
  stewards: Stewards
  units: UnitSystem
  onClose: () => void
  onSetNote: (note: string) => void
  onSetDate: (date: string | null) => void
  onDelete?: () => void
}

export function WalkedHike({
  hike,
  resolved,
  stewards,
  units,
  onClose,
  onSetNote,
  onSetDate,
  onDelete,
}: WalkedHikeProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const orgLabel = orgLabelFrom(stewards)

  const legs = resolved !== null ? resolved.legs : hike.figures.legs
  const miles = resolved !== null ? resolved.miles : hike.figures.miles
  const climb = resolved?.climb ?? hike.figures.climb ?? null

  // Concurrent orgs included (#1115): a merged leg wears one trail's name,
  // and the organization whose designation was folded in still keeps that
  // ground walkable.
  const orgs = distinctLegSources(legs)

  return (
    <div className="walked-hike" role="dialog" aria-label={hike.name}>
      <button type="button" className="route-stops__close" onClick={onClose}>
        <span className="visually-hidden">Close this walk</span>
        <span aria-hidden="true">×</span>
      </button>

      {/* The date leads, because a walk that happened happened on a day, and
          that is the first thing somebody looking back wants. */}
      <div className="walked-hike__head">
        <label className="walked-hike__when">
          <span className="visually-hidden">The day you walked it</span>
          <input
            type="date"
            value={hike.date ?? ''}
            onChange={(event) =>
              onSetDate(event.target.value === '' ? null : event.target.value)
            }
          />
        </label>
        <h2 className="walked-hike__title">{hike.name}</h2>
        {hike.date !== null && (
          <span className="walked-hike__day">{dayLongDateLabel(hike.date)}</span>
        )}
      </div>

      {/* The hiker's own sentence, above the figures. It is the part of this
          screen the app did not write, and putting it first is what says so. */}
      <label className="walked-hike__note">
        <span className="visually-hidden">A line about the day</span>
        <textarea
          value={hike.note}
          maxLength={MAX_NOTE_CHARS}
          rows={3}
          placeholder="A line about the day…"
          onChange={(event) => onSetNote(event.target.value)}
        />
      </label>

      <dl className="walked-hike__figures">
        <div>
          <dt>Distance</dt>
          <dd>{formatDistance(miles, units)}</dd>
        </div>
        {climb !== null && (
          <div>
            <dt>Climb</dt>
            <dd>
              +{formatElevation(climb.gainFt, units)} / −
              {formatElevation(climb.lossFt, units)}
            </dd>
          </div>
        )}
      </dl>

      {resolved === null && (
        // The same disclosure DayHikeCard makes, for the same reason: these
        // numbers were computed from the graph this phone held when the walk
        // was saved, and printing them over today's different graph without
        // comment is a display outrunning its source.
        <p className="walked-hike__cached">
          These are the figures saved with the walk. This phone can&rsquo;t place it on
          the trail network right now to check them.
        </p>
      )}

      {legs.length > 0 && (
        <>
          <h3 className="day-hike-card__heading">Where you went</h3>
          <ul className="sheet__legs day-hike-card__legs">
            {legs.map((leg, at) => (
              <li key={`${leg.name ?? 'unnamed'}-${at}`} className="day-hike-card__leg">
                <span className="day-hike-card__leg-name">
                  {leg.name ?? 'Unnamed trail'}
                </span>
                <span className="day-hike-card__leg-miles">
                  {formatDistance(leg.miles, units)}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {orgs.length > 0 && (
        // The credit, which is the one thing this screen says that is not
        // about the hiker: somebody keeps that ground walkable.
        <p className="walked-hike__orgs">
          Kept walkable by {orgs.map((source) => orgLabel(source)).join(' and ')}.
        </p>
      )}

      {onDelete !== undefined && (
        <div className="walked-hike__actions">
          {confirmingDelete ? (
            <>
              <button
                type="button"
                className="day-hike-bar__action"
                onClick={() => setConfirmingDelete(false)}
              >
                Keep it
              </button>
              <button
                type="button"
                className="day-hike-bar__action day-hike-bar__action--done"
                onClick={onDelete}
              >
                Delete this walk
              </button>
            </>
          ) : (
            <button
              type="button"
              className="day-hike-bar__action"
              onClick={() => setConfirmingDelete(true)}
            >
              Delete
            </button>
          )}
        </div>
      )}
    </div>
  )
}
