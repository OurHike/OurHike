// The map notices where you parked (#1008, storyboard frame D8).
//
// The second door back to a saved day hike, and the one that matters at 8am
// with no signal: a hike planned at home is offered by the map when the
// hiker is standing at its start. No searching, no remembering what it was
// called. The candidates come from lib/dayHikeShelf.ts's
// `dayHikesNearHere` - straight-line distance from the GPS fix to each
// saved start, inside a radius that ships `@unvalidated` there.
//
// LOWER THIRD, COLLAPSED FIRST. Everything tapped mid-walk lives in the
// map's lower third (WIREFRAMES.md §1's interaction rule), so this docks
// where the builder bars do, in the same `routeSheet` slot - and it opens
// as one row, not a sheet: the map is the screen a hiker is here for, and
// a panel that self-opens over it because the phone is near a trailhead
// would be the app deciding what somebody came to do. The tap opens the
// rows; the × puts the door away for the session, because the radius is
// generous enough to linger mid-walk and a door nobody asked for needs a
// way off the screen.
//
// "OPEN", NOT "FOLLOW". The frame's button says "Follow this one", and
// following - a live position against the route - is not built for network
// hikes. The row opens the hike's card: the legs, the ways off, the plan.
// The weaker true word over the stronger plausible one.

import { useState } from 'react'

import type { NearbyDayHike } from '../lib/dayHikeShelf'
import { dayLongDateLabel } from '../lib/planDisplay'
import { formatDistance, type UnitSystem } from '../lib/units'
import '../screens/plan.css'

export interface DayHikesHereProps {
  near: readonly NearbyDayHike[]
  units: UnitSystem
  /** YYYY-MM-DD today, for the one sentence worth adding to a row - passed
   *  in so the derivation is testable against a fixed day. */
  today: string
  onOpen: (id: string) => void
  /** The full list, on the Plan tab. */
  onAll: () => void
  onDismiss: () => void
}

export function DayHikesHere({
  near,
  units,
  today,
  onOpen,
  onAll,
  onDismiss,
}: DayHikesHereProps) {
  const [open, setOpen] = useState(false)

  if (near.length === 0) return null

  if (!open) {
    return (
      <div className="hikes-here hikes-here--closed">
        <button type="button" className="hikes-here__pill" onClick={() => setOpen(true)}>
          {near.length === 1
            ? 'One of your day hikes starts here'
            : `${near.length} of your day hikes start here`}
        </button>
        <button type="button" className="hikes-here__dismiss" onClick={onDismiss}>
          <span className="visually-hidden">Put this away</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>
    )
  }

  return (
    <div className="hikes-here" role="region" aria-label="Your day hikes near here">
      <div className="hikes-here__head">
        <span className="hikes-here__title">
          {near.length === 1
            ? 'One of your day hikes starts here'
            : `${near.length} of your day hikes start here`}
        </span>
        <button type="button" className="hikes-here__dismiss" onClick={onDismiss}>
          <span className="visually-hidden">Put this away</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {near.map(({ hike, miles }) => (
        <button
          type="button"
          className="hikes-here__row"
          key={hike.id}
          onClick={() => onOpen(hike.id)}
        >
          <span className="hikes-here__row-top">
            <span className="hikes-here__row-name">{hike.name}</span>
            {/* Straight-line to the start, and said so - not trail walked. */}
            <span className="hikes-here__row-away">
              {formatDistance(miles, units, 'fine')} away
            </span>
          </span>
          <span className="hikes-here__row-meta">
            {formatDistance(hike.figures.miles, units)}
            {hike.date !== null &&
              ` · planned ${dayLongDateLabel(hike.date)}${
                hike.date === today ? '. That’s today.' : ''
              }`}
          </span>
        </button>
      ))}

      <button type="button" className="hikes-here__all" onClick={onAll}>
        All your day hikes ›
      </button>
    </div>
  )
}
