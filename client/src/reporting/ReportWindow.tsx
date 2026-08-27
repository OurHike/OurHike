// Reporting a problem, as a window over wherever you already were (#1133).
//
// WHAT THIS REPLACES, AND WHY IT IS A DIALOG. `screens/ReportTypePicker.tsx`
// and `screens/ReportForm.tsx` are full-screen routes: App.tsx swaps the whole
// shell for them, tab bar included, which is the reason they need a `Cancel`
// at all - without one, somebody who opened the picker by accident is stuck on
// it. So a hiker standing in front of a blow-down gives up the map to say so,
// and gets it back only by completing or abandoning a form.
//
// A window costs none of that. The screen behind stays mounted and dimmed, so
// closing is free and `Cancel` stops being load-bearing.
//
// THE TAP FILES. This is variant 1a of the three the design handoff drew, and
// the maintainer's pick. Tapping a tile writes the report to the outbox there
// and then; the escape hatch is an Undo with a countdown rather than a form to
// finish. The argument is that the common case - one glove off, in the rain,
// in front of the thing - should not pay for the rare one, and the two rejected
// variants both made it.
//
// It is the same instinct FieldNoteSection.tsx already runs on ("THE TAP FILES
// IMMEDIATELY"), which is worth saying because these two surfaces now behave
// alike and a later reader should know that is deliberate rather than parallel
// evolution.
//
// AND THE UNDO IS REAL, which is the part that is not UI. lib/outbox.ts holds
// a filed report back for the length of the window, because App.tsx flushes
// the outbox immediately after saving (#640) - so without the hold, a phone
// with signal would routinely have sent the report before the countdown
// finished, leaving a button that says Undo and cannot.
//
// TWO OF THE EIGHT NEVER FILE ON A TAP - a closure, which needs two miles and
// leaves for ClosureSheet, and something unsafe, which is private to
// moderators and must show the 911 line before the tap rather than after it.
// reporting/categories.ts owns that distinction; this file only renders it.

import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { formatDistance, type UnitSystem } from '../lib/units'
import {
  CLOSURE_ROW,
  EMERGENCY_NOTICE,
  REPORT_CATEGORIES,
  UNSAFE_ROW,
  categoryLabel,
  filesOnTap,
  type ReportTypeId,
} from './categories'
import { REPORT_ICONS, type ReportIconName } from './icons'
import './reportWindow.css'

/**
 * How long a filed report can still be taken back.
 *
 * @unvalidated - eight seconds is the design handoff's number and nobody has
 * watched a hiker use it. What bounds the cost of it being wrong is that both
 * errors are recoverable: too short and the report stands, editable from the
 * outbox; too long and it sends a few seconds later than it might have, on a
 * queue whose ordinary delay is measured in hours. lib/outbox.ts's
 * MAX_UNDO_HOLD_MS is the ceiling any future value has to stay under.
 */
export const UNDO_WINDOW_MS = 8_000

/** Where the report lands, and how the header says so.
 *
 *  Named apart from chrome/FieldNoteSection.tsx's `ReportAnchor`, which App.tsx
 *  already imports, because they are not the same thing: that one is the place
 *  a report is ABOUT, and this one is that plus the words the header prints.
 *  One name for both would make the header's `label` look optional on a type
 *  where it is the whole reason this interface exists. */
export interface ReportWindowAnchor {
  /** The POI this is about, when it started from a place card. */
  poiId?: string
  lat?: number
  lon?: number
  mile?: number
  /** What the header prints - "Bailey Gap Shelter", "mi 628.4", or "here".
   *  The caller knows which; this file must not guess a place's name from a
   *  mile. */
  label: string
  /**
   * The same place as a phrase the receipt can end a sentence with - "at
   * Bailey Gap Shelter", "at mi 628.4", or plain "here".
   *
   * A SECOND FIELD RATHER THAN `at ${label}`, because "here" is an adverb and
   * the other two are nouns. Composing the preposition here produced "Filed —
   * blow down at here", which is what the first photograph of this screen
   * showed and no test had caught: every test used a mile anchor, where the
   * naive version reads perfectly.
   *
   * Supplied rather than derived, for `label`'s reason: sniffing for the
   * string "here" would be this file guessing at a distinction the caller
   * already knows.
   */
  phrase: string
}

/** One place this hiker walked past today, as the picker lists it.
 *
 *  CARRIES ITS OWN COORDINATES, which this file never reads - the window
 *  renders a name and a distance back, and hands the whole place to
 *  `onPickAnchor`. The fields are here for that callback's contract: an
 *  anchor needs a lat and a lon, so the place a picker offers has to be able
 *  to become one.
 *
 *  Requiring them is what stops the tempting fill. An earlier cut passed
 *  `{ id, name, mile }` and let the caller look the coordinates up at pick
 *  time, which puts an `undefined` in front of somebody at exactly the moment
 *  `lat: 0, lon: 0` looks like a reasonable default - and 0,0 is the Atlantic
 *  off West Africa, the substitution this app already refuses in two other
 *  places (chrome/Header.tsx on the mile readout, screens/ReportForm.tsx on
 *  the location line). With the fields required, the lookup happens where the
 *  list is built and there is no gap left to fill. */
export interface PassedPlace {
  id: string
  name: string
  mile: number
  lat: number
  lon: number
}

export interface ReportWindowProps {
  anchor: ReportWindowAnchor
  /**
   * Where else this report could be anchored: the places today's walked miles
   * covered (lib/passedToday.ts). Empty is an ordinary state - an early start
   * has passed nothing - and the option is withheld rather than shown empty.
   */
  passedPlaces?: readonly PassedPlace[]
  /** The hiker's own mile, for ordering the list by how far back each place
   *  is. Absent when there is no fix, which is when the list cannot be
   *  ordered that way and says so by not offering itself. */
  fixMile?: number
  /** Re-anchor. The caller owns the anchor, so the window asks rather than
   *  deciding. */
  onPickAnchor?: (place: PassedPlace) => void
  /** The hiker's own unit system, for the distance each place is written at
   *  (lib/units.ts, features/UX_CUSTOMIZATION.md). */
  units: UnitSystem
  /** Signed exactly as every other contribution is - the floor in
   *  lib/reporterIdentity.ts applies, and the caller has already applied it. */
  reporterType: 'thru' | 'section' | 'day' | 'maintainer'
  /**
   * Write the report and hand back the outbox id, so Undo has something to
   * delete. Held back for {@link UNDO_WINDOW_MS} by the caller.
   */
  onFile: (type: ReportTypeId, note: string, holdUntil: Date) => Promise<string>
  /** Take it back out of the queue. The same `removeQueued` everything else
   *  uses - see lib/outbox.ts on why this is not a special withdrawal path. */
  onUndo: (outboxId: string) => Promise<void>
  /** A closure leaves this flow rather than continuing it (#832). */
  onReportClosure: () => void
  /** Something unsafe opens the long form, which is what it has always been:
   *  private, moderated, and never a one-tap file. */
  onReportUnsafe: () => void
  /**
   * Closing. `filedAnything` is true only when at least one report was written
   * AND not taken back, which is what the caller needs to decide whether this
   * was a contribution at all - a hiker who opened the window, read it and
   * closed it has not contributed anything, and must not be asked to sign in
   * for it.
   */
  onClose: (filedAnything: boolean) => void
  now?: Date
}

/** When the undo window for a report filed right now would close.
 *
 *  A module function rather than a line inside the component, and not only to
 *  quiet the purity lint: `Date.now()` written in a component body is genuinely
 *  ambiguous about whether it runs on render or on the tap, and the answer
 *  matters here - a hold computed at render time would start counting from
 *  whenever React last drew the tiles rather than from the tap that filed.
 *  Out here it can only be the tap, because only the tap calls it. */
function undoWindowFromNow(): Date {
  return new Date(Date.now() + UNDO_WINDOW_MS)
}

function Icon({ name }: { name: ReportIconName }) {
  return (
    <svg
      className="report-window__icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      // 1.5 rather than Lucide's own 2, per the handoff. It is a rendering
      // decision, which is why reporting/icons.ts does not bake it in.
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      dangerouslySetInnerHTML={{ __html: REPORT_ICONS[name] }}
    />
  )
}

export function ReportWindow({
  anchor,
  passedPlaces = [],
  fixMile,
  onPickAnchor,
  units,
  reporterType,
  onFile,
  onUndo,
  onReportClosure,
  onReportUnsafe,
  onClose,
  now = new Date(),
}: ReportWindowProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement | null>(null)

  // What has been filed, if anything. `outboxId` is what Undo deletes;
  // `undoUntil` is when the button stops being offered.
  const [filed, setFiled] = useState<{
    type: ReportTypeId
    outboxId: string
    undoUntil: number
  } | null>(null)
  const [note, setNote] = useState('')
  // Everything filed by this window and not taken back. A list rather than a
  // flag because both directions matter: "Note something else" files a second
  // report without clearing the first, and Undo removes one without
  // necessarily emptying the set.
  const [standing, setStanding] = useState<readonly string[]>([])
  // Whether the anchor list is open, and what is typed into its filter.
  const [picking, setPicking] = useState(false)
  const [placeFilter, setPlaceFilter] = useState('')
  // Ticks only while an undo window is open, so a window sitting on the tiles
  // costs no timer at all.
  const [remaining, setRemaining] = useState(0)

  // FOCUS RETURNS WHERE IT CAME FROM. Captured on mount rather than passed in:
  // this window opens from four places and every one of them would otherwise
  // have to remember to hand back its own button.
  const openedFrom = useRef<Element | null>(null)
  useEffect(() => {
    openedFrom.current = document.activeElement
    // The dialog itself, not the first tile. Focusing a tile would put a
    // control that FILES A REPORT under the first keystroke of somebody who
    // has not read the window yet - and under 1a that keystroke is not
    // recoverable by pressing Escape.
    dialogRef.current?.focus()
    return () => {
      const returning = openedFrom.current
      if (returning instanceof HTMLElement) returning.focus()
    }
  }, [])

  // `standing` rather than a ref: the identity of this callback changing when
  // it changes is what keeps the Escape handler below closing over the right
  // answer instead of the one from the render it was installed on.
  const close = useCallback(() => {
    onClose(standing.length > 0)
  }, [onClose, standing])

  // Escape closes, and the scrim does too. Safe under 1a in a way it is not
  // under the other two variants: by the time there is anything to lose, the
  // report is already in the outbox. The only unsaved thing is the note, and
  // it is optional detail on a report that already stands.
  //
  // ESCAPE PEELS ONE LAYER, and the anchor picker is the layer. Closing the
  // whole window from inside an open list would lose the screen behind it,
  // which is the single thing this change exists to prevent - and it is what
  // a hiker gets by reflex, because Escape is how you back out of a list.
  //
  // The filter compounds it: `<input type="search">` clears itself on Escape
  // in WebKit and Blink, so somebody who typed three letters and pressed
  // Escape expecting the field to empty would instead lose the window. Both
  // are the same fix.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        if (picking) {
          setPicking(false)
          setPlaceFilter('')
          return
        }
        close()
        return
      }
      if (event.key !== 'Tab') return

      // A focus trap, hand-rolled because this is the app's first true modal
      // and one screen does not earn a dependency. Queried per keystroke
      // rather than cached: the body swaps entirely between the tiles and the
      // receipt, so any cached list would be stale exactly when it is used.
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), textarea, [href], input, select, [tabindex]:not([tabindex="-1"])',
      )
      if (focusable === undefined || focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (first === undefined || last === undefined) return

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [close, picking])

  // The countdown. Re-read from the clock each tick rather than decremented,
  // so a tab that was backgrounded comes back with the right answer instead of
  // however many ticks it managed to run.
  useEffect(() => {
    if (filed === null) return
    const tick = () => {
      const left = Math.max(0, filed.undoUntil - Date.now())
      setRemaining(left)
      return left
    }
    if (tick() === 0) return
    const timer = setInterval(() => {
      if (tick() === 0) clearInterval(timer)
    }, 250)
    return () => clearInterval(timer)
  }, [filed])

  const file = async (type: ReportTypeId) => {
    // The two that never one-tap. Checked here as well as being drawn as rows,
    // because the drawing is a promise and this is the enforcement: a future
    // refactor that renders one of them as a tile would otherwise file it.
    if (!filesOnTap(type)) {
      onReportUnsafe()
      return
    }
    const holdUntil = undoWindowFromNow()
    const outboxId = await onFile(type, note.trim(), holdUntil)
    setStanding((current) => [...current, outboxId])
    setFiled({ type, outboxId, undoUntil: holdUntil.getTime() })
  }

  const undo = async () => {
    if (filed === null) return
    await onUndo(filed.outboxId)
    setStanding((current) => current.filter((id) => id !== filed.outboxId))
    setFiled(null)
    setRemaining(0)
  }

  /**
   * The places today covered, NEAREST FIRST.
   *
   * ORDERED HERE RATHER THAN IN lib/passedToday.ts, which sorts ascending by
   * mile and keeps doing so. That is right for its two other readers - Today's
   * "Today so far" and the Volunteer tab both read the day as a list of places
   * - and it is wrong for a picker, because the two orders are only the same
   * thing walking north. A SOBO's day runs the other way, so mile-ascending
   * puts the place they passed an hour ago at the BOTTOM of the list they are
   * scrolling to find it in.
   *
   * Distance back from the fix is direction-free and is what a hiker
   * re-anchoring is actually thinking in ("that blow-down a mile back"). The
   * design handoff asked for it; what it did not have to weigh is that the
   * function it would have changed has two other callers, and this list is the
   * only one that wants it.
   *
   * NO COUNT, ANYWHERE. lib/passedToday.ts's own rule - the list "never
   * counts, and never mentions what was skipped" - because a number here is a
   * scoreboard of places a hiker walked past without reporting, which is the
   * guilt mechanic DATA_NUDGES.md rules out four times.
   */
  const nearbyFirst: readonly { place: PassedPlace; back: number }[] =
    fixMile === undefined
      ? []
      : passedPlaces
          .map((place) => ({ place, back: Math.abs(place.mile - fixMile) }))
          .sort((a, b) => a.back - b.back)

  const needle = placeFilter.trim().toLowerCase()
  const shownPlaces =
    needle === ''
      ? nearbyFirst
      : nearbyFirst.filter((row) => row.place.name.toLowerCase().includes(needle))

  const canRepick = onPickAnchor !== undefined && nearbyFirst.length > 0

  const undoable = filed !== null && remaining > 0

  /* The anchor list, when the header's Change is open. Above the tiles rather
     than below them: it answers "where", and a hiker who opened it is not
     looking at the categories until they have. */
  const anchorPicker = !picking ? null : (
    <div className="report-window__places" data-testid="report-places">
      {/* Offered past roughly half a dozen rows, which is where scanning a
          list stops being faster than typing three letters of a name. Below
          that it is a control in the way. */}
      {nearbyFirst.length > 6 && (
        <input
          type="search"
          className="report-window__filter"
          data-testid="report-place-filter"
          value={placeFilter}
          placeholder="Filter places"
          aria-label="Filter the places you passed"
          onChange={(event) => setPlaceFilter(event.target.value)}
        />
      )}
      <ul className="report-window__place-list" aria-label="Somewhere you passed today">
        {shownPlaces.map(({ place, back }) => (
          <li key={place.id}>
            <button
              type="button"
              className="report-window__place"
              data-testid={`report-place-${place.id}`}
              onClick={() => {
                onPickAnchor?.(place)
                setPicking(false)
                setPlaceFilter('')
              }}
            >
              <span className="report-window__place-name">{place.name}</span>
              {/* Tabular figures so a scrolling list does not jitter, and the
                  distance never truncates - it is the thing being sorted on,
                  so it is the thing a hiker is comparing.

                  A DIFFERENCE OF TWO MILES, not a mile marker, which is the
                  distinction #986 was: `formatDistance(place.mile, ...)`
                  would print a metric hiker's "757.7 km" for a place the row
                  above calls mi 470.8, and both are positions on this trail.
                  The subtraction happens here so that what reaches the
                  formatter is a distance. */}
              <span className="report-window__place-back">
                {`${formatDistance(back, units)} back`}
              </span>
            </button>
          </li>
        ))}
        {shownPlaces.length === 0 && (
          <li className="report-window__place-empty">Nothing by that name today.</li>
        )}
      </ul>
    </div>
  )

  const tiles = (
    <>
      {anchorPicker}
      <div className="report-window__grid">
        {REPORT_CATEGORIES.map((category) => (
          <button
            key={category.id}
            type="button"
            className="report-window__tile"
            data-testid={`report-tile-${category.id}`}
            onClick={() => void file(category.id)}
          >
            <Icon name={category.icon} />
            <span className="report-window__tile-label">{category.label}</span>
            <span className="report-window__tile-description">
              {category.description}
            </span>
          </button>
        ))}
      </div>

      {/* A peer of the grid rather than a seventh tile. Under 1a a tile
          promises a one-tap FILE, and this one asks for two miles - see
          categories.ts, and #832, which drew the same line when the promise
          was only a one-tap form. */}
      <button
        type="button"
        className="report-window__row"
        data-testid="report-row-closure"
        onClick={onReportClosure}
      >
        <span className="report-window__row-icon report-window__row-icon--closure">
          <Icon name={CLOSURE_ROW.icon} />
        </span>
        <span className="report-window__row-text">
          <span className="report-window__row-label">{CLOSURE_ROW.label}</span>
          <span className="report-window__row-description">
            {CLOSURE_ROW.description}
          </span>
        </span>
        <span className="report-window__row-chevron" aria-hidden="true">
          ›
        </span>
      </button>

      <div className="report-window__unsafe">
        <button
          type="button"
          className="report-window__row report-window__row--unsafe"
          data-testid="report-row-unsafe"
          onClick={onReportUnsafe}
        >
          <span className="report-window__row-icon report-window__row-icon--unsafe">
            <Icon name={UNSAFE_ROW.icon} />
          </span>
          <span className="report-window__row-text">
            <span className="report-window__row-label">{UNSAFE_ROW.label}</span>
            <span className="report-window__row-description">
              {UNSAFE_ROW.description}
            </span>
          </span>
          <span className="report-window__row-chevron" aria-hidden="true">
            ›
          </span>
        </button>

        {/* Before the tap, not after. Somebody in trouble right now needs to
            know this is the wrong tool while they can still act on it, rather
            than once they are already filling in a form. `role="note"`
            deliberately, not an alert: it is standing guidance, not an event.
            Copy is verbatim from what shipped and stays that way. */}
        <p className="report-window__emergency" role="note">
          {EMERGENCY_NOTICE}
        </p>
      </div>
    </>
  )

  const receipt =
    filed === null ? null : (
      <>
        {/* Announced, because the whole interaction is now over for most
          hikers: the tap filed it and there is nothing else they must do.
          Polite rather than assertive - it is confirmation, not an alarm. */}
        <div className="report-window__receipt" role="status" aria-live="polite">
          <p className="report-window__receipt-headline">
            {`Filed — ${categoryLabel(filed.type).toLowerCase()} ${anchor.phrase}`}
          </p>
          <p className="report-window__receipt-sub">
            {`It waits in your outbox and sends itself, keeping ${now.toLocaleTimeString(
              'en-US',
              { hour: 'numeric', minute: '2-digit' },
            )}.`}
          </p>
          {undoable && (
            <button
              type="button"
              className="report-window__undo"
              data-testid="report-undo"
              onClick={() => void undo()}
            >
              {`Undo · ${Math.ceil(remaining / 1000)}s`}
            </button>
          )}
        </div>

        <div className="report-window__detail">
          <p className="report-window__detail-label">Add detail — optional</p>
          <textarea
            className="report-window__note"
            data-testid="report-note"
            rows={3}
            value={note}
            placeholder="Big oak across the trail, you can step over the top."
            onChange={(event) => setNote(event.target.value)}
          />
          <button
            type="button"
            className="report-window__done"
            data-testid="report-done"
            onClick={close}
          >
            Done
          </button>
          <button
            type="button"
            className="report-window__again"
            data-testid="report-again"
            onClick={() => {
              // Back to the tiles with the anchor intact - the real multi-report
              // case, which is a hiker clearing a campsite finding three things.
              // The note is cleared with it: it described the report that was
              // just filed, and carrying it onto the next one would attach
              // somebody's words to the wrong thing.
              setFiled(null)
              setNote('')
            }}
          >
            Note something else
          </button>
        </div>
      </>
    )

  return (
    <div
      className="report-window__scrim"
      data-testid="report-window-scrim"
      // The scrim is not a control and takes no focus; it is the dialog's
      // backdrop, and closing on it is a convenience the close button and
      // Escape both also provide.
      onClick={close}
    >
      <div
        ref={dialogRef}
        className="report-window"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid="report-window"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="report-window__header">
          <div className="report-window__heading">
            <p className="report-window__eyebrow">
              {filed === null ? 'Report a problem' : 'Report · filed'}
            </p>
            <h2 className="report-window__title" id={titleId}>
              {filed === null ? 'What did you find?' : 'Anything to add?'}
            </h2>
            {/* The anchor, STATED RATHER THAN ASKED. Under 1a it is not a
                question: every entry point supplies one, and the hiker is
                standing at it. `Change` is the escape hatch for the case that
                is not that - a blow-down noticed and remembered a mile later
                - and it is deliberately the smaller of the two, because the
                stated anchor is right nearly every time. */}
            <p className="report-window__anchor" data-testid="report-anchor">
              {anchor.label}
              {/* CHANGE IS OFFERED ONLY WHEN THERE IS SOMETHING TO CHANGE TO.
                  A picker that opens onto an empty list is a control that
                  taught a hiker not to trust its labels - and an empty list is
                  an ORDINARY state here, not an error: an early start has
                  walked past nothing yet, and a phone with no fix cannot order
                  what it has. Withheld in both cases rather than shown
                  disabled. */}
              {canRepick && filed === null && (
                <button
                  type="button"
                  className="report-window__change"
                  data-testid="report-change-anchor"
                  onClick={() => setPicking((open) => !open)}
                  aria-expanded={picking}
                >
                  {picking ? 'Done' : 'Change'}
                </button>
              )}
            </p>
          </div>
          <button
            type="button"
            className="report-window__close"
            data-testid="report-close"
            onClick={close}
          >
            <span className="visually-hidden">Close</span>
            <span aria-hidden="true">×</span>
          </button>
        </div>

        <div className="report-window__body">{filed === null ? tiles : receipt}</div>

        {/* Signed the way every contribution is. Said out loud because a
            report carries an attribution a moderator weighs it by, and the
            person filing it should be able to see which one. */}
        <p className="visually-hidden">{`Signed as ${reporterType}`}</p>
      </div>
    </div>
  )
}
