// Reporting a closure (#832) - the form this app has never had.
//
// A closure is a STRETCH, not a pin, which is the whole reason this is not
// another `ReportForm` type. A report snaps one GPS fix; a closure needs two
// miles, and the two ends are what the geometry (#674) anchors to.
//
// WHAT THIS ASKS A HIKER FOR, AND WHAT IT REFUSES TO ASK
//
// The end they are standing at, this app knows: the fix is already snapped to
// the centerline for the header's mile readout. The far end, usually, nobody
// standing at a washout knows - the trail bends out of sight, and the sign at
// the trailhead says "closed" without saying how far.
//
// So the far end is OPTIONAL, and leaving it out files a closure whose two
// miles are the same. That is deliberate, and it is the CLAUDE.md rule about
// omitting rather than guessing applied to a field the schema requires: a
// made-up far end is a stretch somebody drew, and it would be drawn as a band
// on every phone that downloads it. A single point says exactly what the
// reporter knew.
//
// The thing that makes this affordable is that a closure is not published by
// filing it. `moderation_status` starts at `submitted` and a moderator sets
// the real extent before any hiker sees a band - so an imprecise report is
// the start of a decision rather than the end of one. The form says that in
// words, because a hiker who believes they have just closed a trail for
// everybody would file differently from one who knows they are telling a
// club.
//
// WHY THERE IS NO STATUS FIELD
//
// `ClosureStatus` (open / closed / reroute_available) is server-controlled
// and starts at `closed`: somebody filing this is saying the trail is shut.
// Reopening one, or confirming a reroute exists, is a maintainer's judgment -
// see the column's own comment in backend/app/models/closure.py.

import { useState } from 'react'
import { CLOSURE_REASONS } from '../lib/closureDraft'
import type { ClosureReason } from '../lib/closureBanner'
import './reporting.css'

export interface ClosureFormSubmission {
  reason: ClosureReason
  startMile: number
  /** The same as `startMile` when the reporter did not know the far end. */
  endMile: number
  note?: string
  authoredAt: Date
}

export interface ClosureFormProps {
  /**
   * Where the hiker is, as a trail mile, or null.
   *
   * Null covers the two honest cases together - no GPS fix, or a fix that
   * could not be placed on the centerline - because the form does the same
   * thing in both: asks for the mile instead of prefilling it. What it never
   * does is prefill zero, which is Springer Mountain rather than "unknown".
   */
  hereMile: number | null
  onSubmit: (submission: ClosureFormSubmission) => void
  onCancel: () => void
  online?: boolean
  /** Injectable so the authoring stamp is testable. */
  now?: Date
}

/** A typed mile, or null when the box holds nothing usable.
 *
 *  Negative is refused rather than clamped: mi -3 is not a place, and a
 *  clamp would silently file mi 0 - Springer Mountain, a real place two
 *  thousand miles from wherever the typo happened. */
function typedMile(raw: string): number | null {
  const trimmed = raw.trim()
  if (trimmed === '') return null
  const value = Number(trimmed)
  if (!Number.isFinite(value) || value < 0) return null
  return value
}

export function ClosureForm({
  hereMile,
  onSubmit,
  onCancel,
  online = true,
  now,
}: ClosureFormProps) {
  // Taken at mount, like ReportForm's: somebody can start this, walk to the
  // sign to read it, and finish five minutes later. What matters is when
  // they saw the trail was shut.
  const [authoredAt] = useState(() => now ?? new Date())
  const [reason, setReason] = useState<ClosureReason>('storm_damage')
  const [start, setStart] = useState(() => (hereMile === null ? '' : hereMile.toFixed(1)))
  const [end, setEnd] = useState('')
  const [note, setNote] = useState('')
  const [refused, setRefused] = useState<string | null>(null)

  const submit = () => {
    const startMile = typedMile(start)
    if (startMile === null) {
      // Refused rather than filed with a hole. A closure with no miles is
      // not a closure - there is nothing for a moderator to go and look at,
      // and nothing for the geometry to anchor to.
      setRefused(
        'Say which mile the trail is shut at. If you have no signal for a fix, the mile is on the trail sign or the map.',
      )
      return
    }

    const endMile = typedMile(end)
    setRefused(null)
    onSubmit({
      reason,
      startMile,
      // The same mile twice when the far end is unknown - the honest shape
      // of "it is shut here and I could not see how far it runs".
      endMile: endMile ?? startMile,
      note: note.trim() === '' ? undefined : note.trim(),
      authoredAt,
    })
  }

  return (
    <main className="reporting">
      <h1 className="reporting__title">Report a closure</h1>

      <p className="reporting__limit" role="note">
        This goes to the club that looks after this stretch. It does not close the trail
        on anyone else&rsquo;s map — a moderator reads it first and sets where the closure
        really runs.
      </p>

      <fieldset className="reporting__field">
        <legend className="reporting__field-label">Why is it shut?</legend>
        {CLOSURE_REASONS.map((option) => (
          <label key={option.id} className="reporting__choice">
            <input
              type="radio"
              name="closure-reason"
              value={option.id}
              checked={reason === option.id}
              onChange={() => setReason(option.id)}
            />
            <span>
              <span className="reporting__choice-label">{option.label}</span>
              <span className="reporting__meta">{option.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>

      <label className="reporting__field">
        <span className="reporting__field-label">Shut from mile</span>
        <input
          className="reporting__input reporting__input--mile"
          // `inputMode` rather than `type="number"`: a number input on a
          // phone hides the decimal point on some keyboards, and a mile
          // without its tenth is a stretch a moderator has to guess at.
          inputMode="decimal"
          value={start}
          onChange={(event) => setStart(event.target.value)}
        />
        <span className="reporting__meta">
          {hereMile === null
            ? 'No fix on the trail yet — read the mile off the sign or the map.'
            : 'Where you are now. Change it if the closure starts somewhere else.'}
        </span>
      </label>

      <label className="reporting__field">
        <span className="reporting__field-label">To mile (if you know)</span>
        <input
          className="reporting__input reporting__input--mile"
          inputMode="decimal"
          value={end}
          onChange={(event) => setEnd(event.target.value)}
        />
        <span className="reporting__meta">
          Leave this empty if you cannot see where it ends. Nobody expects you to guess,
          and a guessed mile gets drawn as a real one.
        </span>
      </label>

      <label className="reporting__field">
        <span className="reporting__field-label">What did you see?</span>
        <textarea
          className="reporting__note"
          value={note}
          rows={4}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>

      {refused !== null && (
        <p className="reporting__error" role="alert">
          {refused}
        </p>
      )}

      {!online && (
        <p className="reporting__queued" role="status">
          No signal — this will wait in your outbox and sync later, keeping the time you
          wrote it.
        </p>
      )}

      <div className="reporting__actions">
        <button type="button" className="reporting__primary" onClick={submit}>
          {online ? 'Send' : 'Save to outbox'}
        </button>
        <button type="button" className="reporting__secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </main>
  )
}
