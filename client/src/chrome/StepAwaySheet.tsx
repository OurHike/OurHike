// Stepping away from a long hike (#1317).
//
// EVERY DOOR NAMES ITS CONSEQUENCE, and that is the whole design rather than
// a copy preference. These six do very different things to a hiker's record
// - one shifts a fortnight of dates, one keeps a mile for a year, one closes
// the hike, one ungroups it - and a sheet of verbs alone ("Zero", "Pause",
// "Finish") would make the destructive one look like the reversible ones.
// So each door says what happens underneath its name, in the tense of
// something that is about to be true.
//
// "FORGET THIS HIKE" IS THE ONLY ONE BEHIND A CONFIRM, and it is never
// behind a swipe. `removeHike`'s behaviour is that the sections survive - a
// hike is a way of looking at sections, and throwing away the way of looking
// must never throw away the walking - but a hiker cannot see that from the
// outside, so the door says it and the confirm says it again. A swipe would
// put the app's most alarming-sounding action behind the gesture most easily
// performed by accident on a phone in a pocket.

import type { HikeStatus } from '../lib/hikes'
import '../screens/plan.css'

export interface StepAwaySheetProps {
  hikeName: string
  status: HikeStatus
  /** Which door is waiting for a second press, or null. Held by the shell so
   *  closing the sheet cannot leave a half-armed confirm behind. */
  confirmingForget: boolean
  onZero: () => void
  onTownNight: () => void
  onPause: () => void
  onTurnAround: () => void
  onFinish: () => void
  onForget: () => void
  onCancelForget: () => void
  onClose: () => void
}

export function StepAwaySheet({
  hikeName,
  status,
  confirmingForget,
  onZero,
  onTownNight,
  onPause,
  onTurnAround,
  onFinish,
  onForget,
  onCancelForget,
  onClose,
}: StepAwaySheetProps) {
  return (
    <div className="plan-kind" role="dialog" aria-label="Step away from this hike">
      <div className="legend__head">
        <h2 className="legend__title">Step away from this hike</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="plan-kind__lede">{hikeName}</p>

      {/* The three that leave the hike open, in the order a hiker meets them:
          a day off, a night off, a season off. */}
      <Door
        name="A zero — walking again tomorrow"
        note="The day stays; the ones after it shift by one."
        onPick={onZero}
      />
      <Door
        name="Town tonight, back on here"
        note="Resupply logged at the stop. Nothing else moves."
        onPick={onTownNight}
      />
      {status !== 'paused' && (
        <Door
          name="Off trail — pause the hike"
          note="Keeps the mile you stopped at. Resume whenever, this year or next."
          onPick={onPause}
        />
      )}
      <Door
        name="Turning around"
        note="Swaps the two ends. The miles already walked stay walked."
        onPick={onTurnAround}
      />
      <Door
        name="I finished it"
        note="Closes the hike and keeps every section in it."
        onPick={onFinish}
      />

      {confirmingForget ? (
        <div className="plan-kind__door plan-kind__door--confirm">
          <span className="plan-kind__door-name plan-kind__door-name--danger">
            Forget this hike?
          </span>
          <span className="plan-kind__door-note">
            Every section stays in Plan, with its days, its miles and its dates. Only the
            grouping goes.
          </span>
          <div className="plan-kind__confirm-row">
            <button type="button" className="today__action" onClick={onCancelForget}>
              Keep it
            </button>
            <button
              type="button"
              className="today__action today__action--danger"
              onClick={onForget}
            >
              Forget it
            </button>
          </div>
        </div>
      ) : (
        <button type="button" className="plan-kind__door" onClick={onForget}>
          <span className="plan-kind__door-name plan-kind__door-name--danger">
            Forget this hike
          </span>
          <span className="plan-kind__door-note">
            Ungroups it. Every section stays in Plan.
          </span>
        </button>
      )}
    </div>
  )
}

function Door({
  name,
  note,
  onPick,
}: {
  name: string
  note: string
  onPick: () => void
}) {
  return (
    <button type="button" className="plan-kind__door" onClick={onPick}>
      <span className="plan-kind__door-name">{name}</span>
      <span className="plan-kind__door-note">{note}</span>
    </button>
  )
}
