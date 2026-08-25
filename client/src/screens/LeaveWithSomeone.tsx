// "Leave this with someone" (#1008, storyboard frame D6) - the one
// safety-shaped thing in the day-hike flow that is not a map.
//
// The card is composed by lib/dayHikePlanText.ts, which is where the rules
// live: the app's figures print with the app's own words, the hiker's lines
// print verbatim, and **"if I'm not back by" is a field, never a
// calculation** - the app has no arrival clock and must not pretend to one.
// This file is only the form around that text and the two ways to hand it
// over.
//
// TWO WAYS OUT, EACH OFFERED ONLY WHERE IT EXISTS. "Send it" uses the
// phone's own share sheet and renders only when `navigator.share` does -
// LineSheet's rule again: a control that looks pressable and is not teaches
// a hiker the app is broken, and on a desktop browser without Web Share the
// honest offer is the copy button alone. Copy follows AboutBuild.tsx's
// clipboard idiom, including the reason it never optional-chains: `await
// undefined` resolves happily, and the button would report a copy that
// never happened on precisely the browsers where it did not.
//
// NOTHING HERE IS PERSISTED. The typed lines describe one walk on one day -
// the car park changes, the person changes, and a stale "back by 6pm"
// prefilled next month is exactly the confidently-wrong claim this card
// exists to avoid. Typing three short lines each time is the cost, and it
// is the honest one.

import { useState } from 'react'

import type { DayHike } from '../lib/dayHikes'
import {
  dayHikePlanText,
  type LeaveWordFields,
  type PlanTextFigures,
} from '../lib/dayHikePlanText'
import type { UnitSystem } from '../lib/units'
import './plan.css'

export interface LeaveWithSomeoneProps {
  hike: DayHike
  /** The app's half of the card, from one derivation - see PlanTextFigures.
   *  It carries its own provenance, so the text can hedge a cached figure
   *  rather than handing somebody a number the screen behind it refused to
   *  stand behind. */
  figures: PlanTextFigures
  units: UnitSystem
  onClose: () => void
  /** Injectable for tests; defaults to the real navigator. */
  share?: (text: string) => Promise<void>
  canShare?: boolean
  /** The phone's local calendar day, injectable for tests. */
  today?: string
}

type HandOver = 'idle' | 'shared' | 'share-failed' | 'copied' | 'copy-failed'

export function LeaveWithSomeone({
  hike,
  figures,
  units,
  onClose,
  share,
  canShare = typeof navigator !== 'undefined' && 'share' in navigator,
  today,
}: LeaveWithSomeoneProps) {
  const [fields, setFields] = useState<LeaveWordFields>({
    startingFrom: '',
    car: '',
    notBackBy: '',
  })
  const [handOver, setHandOver] = useState<HandOver>('idle')

  const text =
    today === undefined
      ? dayHikePlanText(hike, figures, units, fields)
      : dayHikePlanText(hike, figures, units, fields, today)

  const sendIt = async () => {
    try {
      if (share !== undefined) {
        await share(text)
      } else {
        await navigator.share({ text })
      }
      setHandOver('shared')
    } catch {
      // A cancelled share sheet also lands here, and saying "failed" to
      // somebody who changed their mind would be wrong - so the message
      // points at the copy path rather than declaring an error.
      setHandOver('share-failed')
    }
  }

  const copyIt = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setHandOver('copied')
    } catch {
      setHandOver('copy-failed')
    }
  }

  // Editing a field retires the hand-over status, because that status is a
  // claim about bytes that have already left: "Copied." standing over a card
  // the hiker has since added "if I'm not back by 6:00 pm" to would vouch for
  // exactly the version missing the line this whole sheet exists for.
  const setField = (key: keyof LeaveWordFields) => (value: string) => {
    setFields((current) => ({ ...current, [key]: value }))
    setHandOver('idle')
  }

  return (
    <div className="leave-word" role="dialog" aria-label="Leave this with someone">
      <div className="legend__head">
        <h2 className="legend__title">Leave this with someone</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="leave-word__lede">
        A plain-text card of this walk, for somebody staying behind. It survives a phone
        with no OurHike on it.
      </p>

      <label className="leave-word__field">
        <span className="leave-word__label">Starting from</span>
        <input
          type="text"
          value={fields.startingFrom}
          onChange={(event) => setField('startingFrom')(event.target.value)}
          placeholder="the visitor center lot on Seven Lakes Drive"
        />
      </label>

      <label className="leave-word__field">
        <span className="leave-word__label">The car</span>
        <input
          type="text"
          value={fields.car}
          onChange={(event) => setField('car')(event.target.value)}
          placeholder="grey Subaru, by the kiosk"
        />
      </label>

      <label className="leave-word__field leave-word__field--back-by">
        <span className="leave-word__label">If I&rsquo;m not back by</span>
        <input
          type="text"
          value={fields.notBackBy}
          onChange={(event) => setField('notBackBy')(event.target.value)}
          placeholder="6:00 pm"
        />
        {/* The sentence that keeps this a field. It reads oddly beside an
            app full of estimates, which is exactly why it is said. */}
        <span className="leave-word__note">
          You write this one. We won&rsquo;t guess an arrival time from a walking
          estimate.
        </span>
      </label>

      <div className="leave-word__preview-block">
        <span className="leave-word__label">What they get</span>
        <pre className="leave-word__preview">{text}</pre>
      </div>

      {canShare && (
        <button type="button" className="plan__primary" onClick={() => void sendIt()}>
          Send it
        </button>
      )}
      <button
        type="button"
        className={canShare ? 'day-hike-card__quiet' : 'plan__primary'}
        onClick={() => void copyIt()}
      >
        Copy as plain text
      </button>

      {handOver !== 'idle' && (
        <p className="leave-word__status" role="status">
          {handOver === 'shared' && 'Sent.'}
          {handOver === 'copied' && 'Copied.'}
          {handOver === 'share-failed' &&
            'Nothing was sent. Copy as plain text works everywhere.'}
          {handOver === 'copy-failed' &&
            'This browser would not let the app use the clipboard. The card above is the same text - select and copy it.'}
        </p>
      )}
    </div>
  )
}
