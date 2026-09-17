// Reporting a problem, as a window over wherever you already were (#1133).
//
// WHAT THIS REPLACES, AND WHY IT IS A DIALOG. `screens/ReportTypePicker.tsx`
// was a full-screen route, and `screens/ReportForm.tsx` still is: App.tsx
// swaps the whole shell for one, tab bar included, which is the reason it
// needs a `Cancel` at all - without one, somebody who opened it by accident is
// stuck on it. So a hiker standing in front of a blow-down gave up the map to
// say so, and got it back only by completing or abandoning a form.
//
// The picker is gone (deleted in b74714af, the commit that wired this in);
// the form stays, because `bad_hikers` and `thanks` are long forms with
// things to type and neither files on a tap.
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
//
// AND THE 911 LINE IS CHROME, NOT A LIST ITEM (#1480). It sits between the
// header and the body, outside the region that scrolls, because "before the
// tap" is a claim about what a hiker has READ and a notice under a scroll has
// not been read. What is inside the body is everything a tap can act on; what
// is pinned around it is what the window says about itself.
//
// AND THE TAP NEEDS A PLACE (#1563). Under 1a a tap files, and a tap on a
// phone with no fix used to file a blowdown with no location of any kind -
// not even the hiker's words, which only the long form asked for. So the
// window carries the same location control the long form and the closure
// form carry (reporting/LocationPicker.tsx): the place is STATED in the
// header, as it always was, and CHANGEABLE under it to a named place nearby,
// the phone's own fix with its radius and age printed, or a spot marked on
// the map. A tap on a tile with nothing to place the report at is refused -
// the picker opens instead, and the tile files once it has an answer. That
// refusal is the one exception to "one tap files" and it is deliberate: 1a's
// argument was that the tap should cost the hiker nothing, which is not the
// same as costing the reader everything, and a report a moderator cannot
// place is a report they cannot act on.

import { useCallback, useEffect, useId, useRef, useState } from 'react'
import {
  hasPlace,
  locationWords,
  type FixSnapshot,
  type LocationChoice,
  type NearbyPlace,
} from '../lib/reportLocation'
import type { UnitSystem } from '../lib/units'
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
import { LocationPicker } from './LocationPicker'
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

export interface ReportWindowProps {
  /**
   * Where the report is - as the door supplied it, or as the hiker changed
   * it (lib/reportLocation.ts). The caller owns it, so the window asks
   * rather than deciding: `onChooseLocation` is the only way it moves.
   */
  location: LocationChoice
  /** The phone's fix as it is right now, or null. What a `fix` choice files
   *  at, and what the header prints for one - radius and age included. */
  fix: FixSnapshot | null
  /**
   * Named places worth offering, nearest first (lib/reportLocation.ts's
   * `nearbyPlaces`). Empty is an ordinary state - a fixless phone is near
   * nothing and an early start has passed nothing - and the picker draws no
   * list for it rather than an empty one.
   */
  places: readonly NearbyPlace[]
  /** Places found by name across everything on the phone, for the picker's
   *  search box. Absent draws no box. */
  onSearchPlaces?: (query: string) => readonly NearbyPlace[]
  /** Whether a trail index is on the phone - what tells "this spot" from
   *  "more than 3 mi off the trail" on a marked point. */
  knowsTrail: boolean
  /** The hiker's own unit system, for every distance and radius the picker
   *  writes (lib/units.ts, features/UX_CUSTOMIZATION.md). */
  units: UnitSystem
  onChooseLocation: (choice: LocationChoice) => void
  /**
   * Hand the hiker the map to aim at. The shell answers by standing this
   * window aside (`standingAside`) and, on Keep, by changing `location` to
   * the marked point. Absent draws no map row - a control that opens nothing
   * is worse than none.
   */
  onPointOnMap?: () => void
  /**
   * True while the crosshair is out over the map. The window is hidden and
   * inert rather than unmounted, holding every piece of its state - the note,
   * the words, which report is filed - exactly as the long form does for the
   * same tap (#1439).
   */
  standingAside?: boolean
  /** Signed exactly as every other contribution is - the floor in
   *  lib/reporterIdentity.ts applies, and the caller has already applied it. */
  reporterType: 'thru' | 'section' | 'day' | 'maintainer'
  /**
   * Write the report and hand back the outbox id, so Undo has something to
   * delete. Held back for {@link UNDO_WINDOW_MS} by the caller.
   *
   * `placeWords` is the hiker's own words for where this was, trimmed, and
   * empty unless nothing else could place the report. The caller sends them
   * only in that case (lib/reportLocation.ts's `reportLocationFields`).
   */
  onFile: (
    type: ReportTypeId,
    note: string,
    holdUntil: Date,
    placeWords: string,
  ) => Promise<string>
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
  location,
  fix,
  places,
  onSearchPlaces,
  knowsTrail,
  units,
  onChooseLocation,
  onPointOnMap,
  standingAside = false,
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
  const pickerRef = useRef<HTMLDivElement | null>(null)

  // What has been filed, if anything. `outboxId` is what Undo deletes;
  // `undoUntil` is when the button stops being offered; `phrase` is where it
  // went, captured at the tap - the fix can move after a report has filed at
  // it, and a receipt that moved with it would describe a report that did not.
  const [filed, setFiled] = useState<{
    type: ReportTypeId
    outboxId: string
    undoUntil: number
    phrase: string
  } | null>(null)
  const [note, setNote] = useState('')
  // Everything filed by this window and not taken back. A list rather than a
  // flag because both directions matter: "Note something else" files a second
  // report without clearing the first, and Undo removes one without
  // necessarily emptying the set.
  const [standing, setStanding] = useState<readonly string[]>([])
  // The hiker's own words for where this was, asked for by the picker only
  // when nothing else can place the report, and sent only then.
  const [placeWords, setPlaceWords] = useState('')
  // Whether a tap was just refused for want of a place. What turns the
  // picker's opening from an offer into an alert.
  const [refused, setRefused] = useState(false)
  // Whether the location picker is open. OPENS BY ITSELF when the door
  // supplied nothing the report can be placed at - no fix, no card, no press -
  // because every tile below it is about to refuse until it is answered, and
  // a control a hiker has to find is a control they meet after the refusal.
  const [picking, setPicking] = useState(() => !hasPlace(location, fix))
  // Ticks only while an undo window is open, so a window sitting on the tiles
  // costs no timer at all.
  const [remaining, setRemaining] = useState(0)

  // A point kept on the map arrives as a new `location` from the shell, and
  // the picker closes on it the way it closes on one of its own rows.
  // Adjusted during render rather than in an effect, which is React's own
  // pattern for reacting to a prop change without a wasted paint.
  const [seenLocation, setSeenLocation] = useState(location)
  if (seenLocation !== location) {
    setSeenLocation(location)
    if (location.kind === 'point') {
      setPicking(false)
      setRefused(false)
    }
  }

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

  // Back from the map with the dialog's focus where the crosshair left it -
  // on nothing, since the window was inert. The dialog takes it again, for
  // the reason above: never a tile.
  useEffect(() => {
    if (!standingAside) dialogRef.current?.focus()
  }, [standingAside])

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
  // ESCAPE PEELS ONE LAYER, and the picker is the layer. Closing the whole
  // window from inside an open list would lose the screen behind it, which
  // is the single thing this change exists to prevent - and it is what a
  // hiker gets by reflex, because Escape is how you back out of a list.
  //
  // The search box compounds it: `<input type="search">` clears itself on
  // Escape in WebKit and Blink, so somebody who typed three letters and
  // pressed Escape expecting the field to empty would instead lose the
  // window. Both are the same fix.
  //
  // NOTHING WHILE STANDING ASIDE. The window is inert and the map has the
  // keys: an Escape meant for the crosshair bar must not close a window the
  // hiker cannot see.
  useEffect(() => {
    if (standingAside) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        if (picking) {
          setPicking(false)
          setRefused(false)
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
  }, [close, picking, standingAside])

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

  // What the header states, resolved against the fix as it is right now.
  const words = locationWords(location, fix, units, knowsTrail, now, placeWords)
  const placed = hasPlace(location, fix) || placeWords.trim() !== ''

  const file = async (type: ReportTypeId) => {
    // The two that never one-tap. Checked here as well as being drawn as rows,
    // because the drawing is a promise and this is the enforcement: a future
    // refactor that renders one of them as a tile would otherwise file it.
    if (!filesOnTap(type)) {
      onReportUnsafe()
      return
    }
    // THE TAP NEEDS A PLACE (#1563). Nothing to file it at - no fix, no named
    // place, no marked spot, not even words - and the tap opens the picker
    // instead of writing a report a moderator would read as "no location".
    // Focus goes into the picker so the refusal is heard as well as seen.
    if (!placed) {
      setPicking(true)
      setRefused(true)
      setTimeout(() => {
        pickerRef.current?.querySelector<HTMLElement>('input, textarea, button')?.focus()
      }, 0)
      return
    }
    const holdUntil = undoWindowFromNow()
    const outboxId = await onFile(type, note.trim(), holdUntil, placeWords.trim())
    setStanding((current) => [...current, outboxId])
    setFiled({ type, outboxId, undoUntil: holdUntil.getTime(), phrase: words.phrase })
  }

  const undo = async () => {
    if (filed === null) return
    await onUndo(filed.outboxId)
    setStanding((current) => current.filter((id) => id !== filed.outboxId))
    setFiled(null)
    setRemaining(0)
  }

  const undoable = filed !== null && remaining > 0

  /* The picker, when the header's Change is open or nothing has placed the
     report yet. Above the tiles rather than below them: it answers "where",
     and a hiker who opened it is not looking at the categories until they
     have. */
  const locationPicker = !picking ? null : (
    <div ref={pickerRef} data-testid="report-places">
      <LocationPicker
        choice={location}
        fix={fix}
        places={places}
        onSearch={onSearchPlaces}
        units={units}
        knowsTrail={knowsTrail}
        onChoose={(choice) => {
          onChooseLocation(choice)
          setPicking(false)
          setRefused(false)
        }}
        onPointOnMap={onPointOnMap}
        words={{
          value: placeWords,
          onChange: (value) => {
            setPlaceWords(value)
            setRefused(false)
          },
        }}
        needed={refused}
        now={now}
      />
    </div>
  )

  const tiles = (
    <>
      {locationPicker}
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

      {/* Still ruled off from the grid above it - what is up there is the
          trail, and this is about people on it. The 911 line used to close
          this block; it is pinned above the body now (#1480), which leaves
          the wrapper carrying one child and the rule that separates it. */}
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
            {`Filed — ${categoryLabel(filed.type).toLowerCase()} ${filed.phrase}`}
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
              // Back to the tiles with the place intact - the real multi-report
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
      className={
        standingAside
          ? 'report-window__scrim report-window__scrim--stood-aside'
          : 'report-window__scrim'
      }
      data-testid="report-window-scrim"
      // Out of reach as well as out of sight while the crosshair is out, for
      // the reason App.tsx gives about the long form: this window has a Close
      // and so does the pick bar in front of it, and two controls of the same
      // name - one of them the wrong one - is a worse thing to hand a screen
      // reader than a hidden subtree.
      inert={standingAside || undefined}
      aria-hidden={standingAside || undefined}
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
            {/* The place, STATED RATHER THAN ASKED. Under 1a it is not a
                question: every entry point supplies one, and the hiker is
                standing at it. `Change` is the escape hatch for the case that
                is not that - a blow-down noticed and remembered a mile later,
                or a fix the picker's own radius line shows to be poor - and it
                is deliberately the smaller of the two, because the stated
                place is right nearly every time.

                OFFERED WHENEVER THERE IS A REPORT TO PLACE, which is a change
                from the passed-places list it replaces (#1563). That list was
                withheld without walked miles and a fix; the picker always has
                something to offer - the map at least, and words when nothing
                else can say - so a control that opens onto nothing is no
                longer a state this can be in. Taken away once the report is
                filed: re-placing from a receipt would move a record already
                written. */}
            <p className="report-window__anchor" data-testid="report-anchor">
              {words.label}
              {filed === null && (
                <button
                  type="button"
                  className="report-window__change"
                  data-testid="report-change-anchor"
                  onClick={() => {
                    setPicking((open) => !open)
                    setRefused(false)
                  }}
                  aria-expanded={picking}
                >
                  {picking ? 'Done' : 'Change'}
                </button>
              )}
            </p>
            {/* HOW the place is known - the provenance the wire carries, in
                words, so a ±800 ft fix from twelve minutes ago reads as
                exactly that before anybody files under it. */}
            {filed === null && words.detail !== null && (
              <p
                className="report-window__anchor-detail"
                data-testid="report-anchor-detail"
              >
                {words.detail}
              </p>
            )}
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

        {/* THE 911 LINE IS PINNED, above the scroll rather than inside it
            (#1480). It used to close the body, which meant a hiker met it
            only by scrolling past every category first - measured 39 px below
            the fold on a 390x844 phone and 170 px below it on a 375x667 one,
            and the whole reason the line exists is to be read BEFORE the tap
            by somebody who is in trouble now. (53 and 184 are the body's own
            overflow at those sizes, which is a different measurement and what
            this comment first carried.)

            OUT OF THE BODY ENTIRELY rather than merely moved to the top of
            it, because a category list grows: anything added to the grid
            pushes what follows it down, and this is the one thing on this
            surface that must not be pushable. Pinned here it survives the
            scroll the body still has on a small phone or at a large text
            size.

            Only while the tiles are up, which is unchanged. After a tap the
            body is a receipt for a report that is already filed, and this is
            guidance about a decision that has been taken.

            `role="note"` deliberately, not an alert: it is standing guidance,
            not an event. Copy is verbatim from what shipped and stays that
            way - the position was wrong, the words were not. */}
        {filed === null && (
          <p className="report-window__emergency" role="note">
            {EMERGENCY_NOTICE}
          </p>
        )}

        <div className="report-window__body">{filed === null ? tiles : receipt}</div>

        {/* Signed the way every contribution is. Said out loud because a
            report carries an attribution a moderator weighs it by, and the
            person filing it should be able to see which one. */}
        <p className="visually-hidden">{`Signed as ${reporterType}`}</p>
      </div>
    </div>
  )
}
