// The day summary (#966, wireframe 2c frame 1): what a walked day was,
// opened from the timeline row that has gone grey.
//
// END OF DAY, BACKWARD-LOOKING ONLY. The wireframe's guardrail is the one
// Plan.tsx already carries and this card is the surface most likely to
// break it, because it is the one that arrives when a hiker has just
// finished walking and is most receptive to being told how they did.
// Nothing here compares the day against its target, prints what it was
// meant to be, or scores it. There is no figure on this card that a plan
// contributed - only where the day ran, and what the hiker filed while
// walking it.
//
// TWO VOICES, KEPT APART (the wireframe's whimsy rule). The app is funny in
// empty states and waits - Plan.tsx's "you could just walk north and find
// out". This card is funny only because it quotes the hiker's own trail
// back at them: a milestone they passed, and the line they wrote
// themselves. It never jokes about how they walked, so the one generated
// sentence here states a fact about the ground and stops.
//
// THREE FIGURES THE WIREFRAME ASKS FOR ARE NOT ON THIS CARD, each for its
// own reason, and the reasons matter more than the tiles would have:
//
//   "8h40 moving"        NOT A MEASUREMENT. lib/walkedMiles.ts records
//                        merged mile intervals and deliberately no
//                        timestamps, so the app cannot know how long a day
//                        took. What it can say is how long the STRETCH is
//                        estimated to take, which is Naismith, which is
//                        what the ≈ and the word "walking" mark - the same
//                        qualification RouteStopsPanel puts on a route.
//   "Field notes filed"  no source (#967) - a note leaves the outbox when
//                        it sends, so the count would mean "not sent yet".
//   "Water you drank at" no source, and not observable (#967).
//
// A SHEET OVER THE PLAN SCREEN, docked to its bottom edge like the
// call-it-a-day and cascade sheets it sits beside in the same flow.

import { useEffect, useState } from 'react'
import { longestDryRun, milestoneCrossed } from '../lib/daySummary'
import { DAY_NOTE_MAX_CHARS, type PlanDayView } from '../lib/plan'
import { dayLongDateLabel, stopLabel } from '../lib/planDisplay'
import { formatNaismithMinutes } from '../lib/naismith'
import { ownPhotosOn } from '../lib/poiPhotos'
import type { LegFigures } from '../lib/route'
import type { StoredPoi } from '../lib/trailData'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'
import './plan.css'

export interface DaySummaryProps {
  day: PlanDayView
  /** The day's stretch, from the published profile - undefined on a
   *  download with no profile, which drops the climb and the estimate
   *  rather than printing either at zero. */
  figures: LegFigures | undefined
  pois: readonly StoredPoi[]
  units: UnitSystem
  /** Whether the next day is also a record, so the card can offer it. Days
   *  that have not been walked have no summary to show. */
  nextDayWalked: boolean
  onNextDay: () => void
  /** Keep the hiker's line. Empty clears it. */
  onKeepNote: (note: string) => void
  onClose: () => void
}

/**
 * KEY THIS BY THE DAY. The two `useState` initialisers below read `day`, so
 * they are correct only for the day the component mounted on - which is why
 * Plan.tsx passes `key={day.id}` and why #986 happened before it did. A
 * caller that renders this for a second day without remounting it will show
 * the first day's line and count under the second day's header.
 */
export function DaySummary({
  day,
  figures,
  pois,
  units,
  nextDayWalked,
  onNextDay,
  onKeepNote,
  onClose,
}: DaySummaryProps) {
  const [note, setNote] = useState(day.note ?? '')

  // The photo count is the one figure that has to be read out of IndexedDB.
  // Null while it is unknown, and the tile is ABSENT rather than zero until
  // it resolves: "Photos you kept: 0" flashing before the real number is a
  // card telling a hiker they photographed nothing today.
  const [photos, setPhotos] = useState<number | null>(null)
  useEffect(() => {
    if (day.date === null) {
      setPhotos(null)
      return
    }
    let live = true
    ownPhotosOn(day.date)
      .then((count) => {
        if (live) setPhotos(count)
      })
      // Absence, silently - the same posture useOwnPhotos takes about the
      // same store. A card that must render without it does.
      .catch(() => {
        if (live) setPhotos(null)
      })
    return () => {
      live = false
    }
  }, [day.date])

  const distanceMi = Math.abs(day.end.mile - day.start.mile)
  const milestone = milestoneCrossed(day.start.mile, day.end.mile)
  const dry = longestDryRun(pois, day.start.mile, day.end.mile)

  return (
    <div className="day-summary" role="dialog" aria-label="Your day">
      <div className="day-summary__head">
        <span className="day-summary__when">
          {day.date === null ? '' : `${dayLongDateLabel(day.date)} · `}
          {day.dayNumber === null ? 'a zero' : `day ${day.dayNumber}`}
        </span>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <h2 className="day-summary__title">
        {stopLabel(day.start)} → {stopLabel(day.end)}
      </h2>

      <p className="day-summary__figures">
        {formatDistance(distanceMi, units)}
        {figures !== undefined && (
          <>
            {' · '}
            {formatElevation(figures.ascentFt, units)} ↑{' · '}
            {/* Naismith, and it says so: an estimate for this stretch, not
                a stopwatch on the hiker's day. */}
            {formatNaismithMinutes(figures.minutes)} walking
          </>
        )}
      </p>

      {milestone !== null && (
        <p className="day-summary__memory">
          Somewhere in there you passed mile {milestone.toLocaleString('en-US')}.
        </p>
      )}

      <section className="day-summary__filed">
        <span className="day-summary__filed-title">your day, from what you filed</span>
        <dl className="day-summary__tiles">
          {photos !== null && (
            <div className="day-summary__tile">
              {/* "Kept", not "taken": a library import with no capture date
                  is dated the day it was added (lib/poiPhotos.ts), and this
                  count cannot tell those apart. */}
              <dt>Photos you kept</dt>
              <dd>{photos}</dd>
            </div>
          )}
          {dry !== null && (
            <div className="day-summary__tile">
              <dt>Longest stretch with no water on the map</dt>
              <dd>{formatDistance(dry.miles, units)}</dd>
            </div>
          )}
        </dl>
        {dry !== null && (
          <p className="day-summary__caveat" role="note">
            {dry.waterCount === 0
              ? 'No water waypoint on any of today — which is what the map carries, not what the trail has.'
              : 'Between the water waypoints this map carries. Coverage is incomplete, so the trail may have had more.'}
          </p>
        )}
      </section>

      <label className="day-summary__note">
        <span>Add a line for future you</span>
        <textarea
          value={note}
          maxLength={DAY_NOTE_MAX_CHARS}
          rows={2}
          placeholder="the ponies were unbothered"
          onChange={(event) => setNote(event.target.value)}
        />
      </label>

      <button type="button" className="plan__primary" onClick={() => onKeepNote(note)}>
        Keep
      </button>
      {nextDayWalked && (
        <button
          type="button"
          className="plan__action plan__action--quiet"
          onClick={onNextDay}
        >
          The next day →
        </button>
      )}
    </div>
  )
}
