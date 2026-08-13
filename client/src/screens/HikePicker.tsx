// Where a hiker says which way they are walking (#335).
//
// Two numbers and two shortcuts. What this deliberately is NOT is the first
// screen of a route builder - features/HIKE_PLANNING.md owns that, it is v2's
// first feature, and every field beyond a start and an end is that doc
// arguing its way in early. lib/plannedHike.ts holds the boundary.
//
// A SCREEN, NOT A DIALOG
//
// It is reached from More and it replaces More while it is open, so there is
// nothing behind it to dim, nothing to trap focus against, and no Escape
// handler to get half right - Cancel is on screen. DownloadsDialog is a
// window because the download can be opened from anywhere; this cannot.
//
// DIRECTION IS SHOWN, NEVER ASKED
//
// There is no NOBO/SOBO control, because there are already two: the numbers.
// `start < end` is northbound and that is the whole rule. A toggle beside them
// would be a second source of truth that could disagree with the pair it was
// meant to describe - the same call backend/app/models/hike.py makes by having
// no `direction` column. What this does instead is say which way the numbers
// mean, as they are typed, so nobody has to work the rule out.
//
// SETTING ONE IS OPTIONAL, AND THIS SAYS SO
//
// Every part of this app works without a hike. Browsing needs no account and
// no plan, which is why Clear is an ordinary button rather than a destructive
// corner: finishing a hike, or changing plans at a road crossing, must not
// mean clearing app data to get back to the state a hiker started in.

import { useState } from 'react'
import type { HikeDirection } from '../chrome/Header'
import {
  plannedDirection,
  plannedHike,
  wholeTrail,
  type PlannedHike,
} from '../lib/plannedHike'
import { formatDistance, type UnitSystem } from '../lib/units'
import './settings.css'

export interface HikePickerProps {
  /** What is set now, or null for a hiker who has not said. */
  hike: PlannedHike | null
  /**
   * The trail's own length, from the centerline index - or null before the
   * trail data has finished arriving.
   *
   * Null is a real state rather than a spinner's excuse: the shortcuts need a
   * number to end at, so they say why they cannot help, while the two inputs
   * still work for anyone who knows their mile markers.
   */
  trailMiles: number | null
  /**
   * Which units the readout below the two fields is written in.
   *
   * The FIELDS are mile markers and stay in miles under either setting - they
   * are the numbers on the trail, and lib/units.ts says why. What converts is
   * the one sentence that describes how far apart they are, which is an
   * ordinary distance and the only measurement on this screen.
   */
  units?: UnitSystem
  onSave: (hike: PlannedHike) => void
  onClear: () => void
  onClose: () => void
}

function directionLabel(direction: HikeDirection): string {
  return direction === 'NOBO' ? 'Northbound' : 'Southbound'
}

export function HikePicker({
  hike,
  trailMiles,
  units = 'imperial',
  onSave,
  onClear,
  onClose,
}: HikePickerProps) {
  // Held as text, not as numbers. A number input mid-edit is legitimately
  // empty, or "1.", or "-", and coercing every keystroke fights the person
  // typing - so the parse happens in one place, and `plannedHike` is the one
  // thing that decides whether a pair describes a hike at all.
  const [start, setStart] = useState(hike === null ? '' : String(hike.startMile))
  const [end, setEnd] = useState(hike === null ? '' : String(hike.endMile))

  const parsed = plannedHike(
    Number.parseFloat(start),
    Number.parseFloat(end),
    trailMiles ?? undefined,
  )

  const applyShortcut = (direction: HikeDirection) => {
    if (trailMiles === null) return
    const whole = wholeTrail(direction, trailMiles)
    setStart(String(whole.startMile))
    setEnd(String(whole.endMile))
  }

  return (
    <div className="more">
      <section className="settings__group">
        <h2 className="settings__heading">Your hike</h2>
        <p className="settings__note">
          Telling OurHike where you are walking lets the map say what is ahead of you,
          rather than waiting until you have walked far enough for it to work out which
          way you are going. It is optional.
        </p>

        <button
          type="button"
          className="settings__action"
          onClick={() => applyShortcut('NOBO')}
          disabled={trailMiles === null}
        >
          Whole trail, northbound
        </button>
        <button
          type="button"
          className="settings__action"
          onClick={() => applyShortcut('SOBO')}
          disabled={trailMiles === null}
        >
          Whole trail, southbound
        </button>
        {trailMiles === null && (
          <p className="settings__note">
            The trail data is still arriving, so the whole-trail shortcuts are not ready
            yet. You can still enter mile markers.
          </p>
        )}

        <label className="settings__field">
          Starting at mile
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
        </label>
        <label className="settings__field">
          Finishing at mile
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
        </label>

        {/* A live reading of what the two numbers mean, rather than a control
            that could contradict them. `role="status"` because it changes
            under the person typing and is the confirmation they are after. */}
        <p className="settings__note" role="status">
          {parsed === null
            ? 'Two different mile markers describe a hike; the same one twice does not.'
            : `${directionLabel(plannedDirection(parsed))} · ${formatDistance(
                Math.abs(parsed.endMile - parsed.startMile),
                units,
                // Two typed mileposts, subtracted: a hiker who entered 100 and
                // 142 reads "42 mi", not "42.0 mi".
                'trimmed',
              )}`}
        </p>

        <button
          type="button"
          className="settings__action"
          disabled={parsed === null}
          onClick={() => parsed !== null && onSave(parsed)}
        >
          Save
        </button>
        {hike !== null && (
          <button type="button" className="settings__action" onClick={onClear}>
            Clear this hike
          </button>
        )}
        <button type="button" className="settings__action" onClick={onClose}>
          Cancel
        </button>
      </section>
    </div>
  )
}
