// Frame `1j`'s bar: tap a trail, it routes (#978,
// features/HIKE_PLANNING.md "The day hike on a network").
//
// Borrows chrome/RouteMapPickBar.tsx's shape, because the two are the same
// gesture on two different kinds of trail and a hiker should not learn the
// chrome twice. What changes is the refusal underneath: that bar declines a tap
// more than MAX_OFF_TRAIL_MILES off the A.T. corridor, and this one declines a
// tap that is not on a marked hiking route at all.
//
// THE FIGURES OBEY THE SAME RULES THE SHIPPED BUILDER OBEYS
//
// The `≈` prefix, five-minute rounding, and the word "walking". No arrival
// clock, and no difficulty score. Those are not this frame's inventions - they
// are what RouteStopsPanel already prints and what lib/naismith.ts already
// refuses to go beyond - and a second surface that quietly dropped one would
// be the more dangerous of the two, because a hiker would have no way to know
// which screen was the careful one.
//
// THE ORG TALLY IS LIVE, WHICH IS WHY IT IS HERE AND NOT ON THE CARD
//
// Frame `1j` prints "NYNJTC · 2 legs" and "ATC · 1 leg" WHILE the hiker is
// building, not afterwards. Three organizations keeping one loop walkable is
// the thing OurHike exists to make visible, and it reads differently when it
// accrues in front of somebody than when it appears as a credit at the end.
//
// ROADS ARE A ROW, NOT AN OMISSION
//
// #931 is drawn here as a LATER row on purpose. A missing capability the app is
// silent about reads as a bug; one the app names reads as a boundary. A hiker
// who needs a road shoulder to close a loop should see that OurHike knows the
// road is there and does not route on it - not wonder why the loop will not
// close.

import type { DayHikeDraft, DraftStatus } from '../lib/dayHikeDraft'
import { formatNaismithMinutes } from '../lib/naismith'
import { formatDistance, type UnitSystem } from '../lib/units'
import '../screens/plan.css'

export interface DayHikePickBarProps {
  draft: DayHikeDraft
  status: DraftStatus
  units: UnitSystem
  /** Display name per source key, from the steward records. */
  orgLabel: (source: string | null) => string
  /** Naismith minutes for the routed distance and its climb, or null when
   *  there is no elevation profile to price the climb from. */
  walkingMinutes: number | null
  onUndo: () => void
  onCloseLoop: () => void
  onDone: () => void
  onCancel: () => void
  canCloseLoop: boolean
}

/**
 * lib/naismith.ts's own display rule, with the one word this surface adds.
 *
 * Delegating rather than re-rounding is the point: the A.T. builder and this
 * one must print the same minutes the same way, and two copies of a rounding
 * rule is how they stop doing that without anybody deciding it.
 */
export function walkingTime(minutes: number | null): string | null {
  if (minutes === null || !Number.isFinite(minutes) || minutes <= 0) return null
  return `${formatNaismithMinutes(minutes)} walking`
}

export function DayHikePickBar({
  draft,
  status,
  units,
  orgLabel,
  walkingMinutes,
  onUndo,
  onCloseLoop,
  onDone,
  onCancel,
  canCloseLoop,
}: DayHikePickBarProps) {
  const route = status.kind === 'routed' ? status.route : null
  const time = walkingTime(walkingMinutes)

  return (
    <div className="day-hike-bar" role="region" aria-label="Build a day hike">
      <div className="day-hike-bar__head">
        <p className="day-hike-bar__prompt">
          Tap a trail to walk it. Tap again further along to turn.
        </p>
        <button type="button" className="day-hike-bar__cancel" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {draft.refusal !== null && (
        <p className="day-hike-bar__refusal" role="alert">
          {draft.refusal}
        </p>
      )}

      {status.kind === 'unroutable' && (
        <p className="day-hike-bar__refusal" role="alert">
          There&rsquo;s no marked route between those points on this map. They may be in
          different places, or the trail between them isn&rsquo;t one we hold.
        </p>
      )}

      {route !== null && (
        <>
          <p className="day-hike-bar__total">
            {route.legs.length} {route.legs.length === 1 ? 'leg' : 'legs'} ·{' '}
            {formatDistance(route.miles, units)}
            {time !== null && <> · {time}</>}
          </p>
          <ul className="day-hike-bar__orgs">
            {route.legsBySource.map((tally) => (
              <li key={tally.source ?? 'unattributed'} className="day-hike-bar__org">
                {orgLabel(tally.source)} · {tally.legs}{' '}
                {tally.legs === 1 ? 'leg' : 'legs'}
              </li>
            ))}
          </ul>
        </>
      )}

      {status.kind === 'started' && (
        <p className="day-hike-bar__total">Tap again further along to turn.</p>
      )}

      {/* No disabled buttons on this bar - the same rule LineSheet.tsx states
          and the A.T. builder now carries: a control that looks pressable and
          is not teaches a hiker the app is broken. A control that does not
          apply yet is absent, like Close the loop always was. */}
      <div className="day-hike-bar__actions">
        {(draft.points.length > 0 || draft.refusal !== null) && (
          <button type="button" className="day-hike-bar__action" onClick={onUndo}>
            Undo
          </button>
        )}
        {canCloseLoop && (
          <button type="button" className="day-hike-bar__action" onClick={onCloseLoop}>
            Close the loop
          </button>
        )}
        {route !== null && (
          <button
            type="button"
            className="day-hike-bar__action day-hike-bar__action--done"
            onClick={onDone}
          >
            Done
          </button>
        )}
      </div>

      {/* #931, drawn rather than omitted - see the header. Deliberately a row
          with a label and no control: there is nothing to press yet, and a
          dead button would say something different from what is true. */}
      <p className="day-hike-bar__later">
        <span className="day-hike-bar__later-name">Roads and connectors</span>
        <span className="day-hike-bar__later-tag">LATER</span>
      </p>
    </div>
  )
}
