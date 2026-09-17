// The location picker as a window of its own, over whichever surface asked
// (#1563, the maintainer's steer of 2026-09-17: "the location should be
// exposed as a second emergent window").
//
// WHAT THIS REPLACES. The picker first shipped as a drawer inside the report
// window, above the tiles, and inside the long form under its location line.
// That cost the one thing #1480 had just bought: on the smallest phone the
// tile frame scrolled again the moment the drawer opened, and the picker was
// competing for room with the six tiles it exists to serve. A window of its
// own has the whole screen, closes back onto exactly the surface that opened
// it, and leaves that surface's frame the size it was measured at.
//
// ONE SHEET, THREE HOSTS. The report window, the long form and the closure
// form each render this over themselves; none of them draws a picker inline
// any more. The picker inside is reporting/LocationPicker.tsx unchanged, so
// what it offers and in what order is decided once.
//
// WHO OWNS WHAT. The host owns the choice, the words and whether this is open
// - it hands them down and takes them back through the picker's callbacks -
// and this owns nothing but the frame: the title, Done, the scrim, focus while
// it is up, and the Tab loop. Escape closes it: the host with its own Escape
// handler (the report window) already peels this layer first, and this closes
// itself as well, which is the same answer twice rather than a race.
//
// STANDS ASIDE WITH ITS HOST. Rendered inside the host's own overlay, so when
// the host hides and goes inert for the map's crosshair this goes with it,
// and the point kept on the map arrives back as a new choice that closes it.

import { useEffect, useId, useRef } from 'react'
import { LocationPicker, type LocationPickerProps } from './LocationPicker'
import './locationSheet.css'

export interface LocationSheetProps extends LocationPickerProps {
  /** Close without changing anything - Done, Escape, or the scrim. */
  onClose: () => void
}

export function LocationSheet({ onClose, ...picker }: LocationSheetProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement | null>(null)

  // The dialog itself on open, never the first row: a row here CHANGES where
  // a report goes, and it should not sit under the first keystroke of
  // somebody who has not read the title yet - the same rule the report
  // window keeps about its tiles.
  useEffect(() => {
    dialogRef.current?.focus()
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      // A Tab loop of its own, so focus cannot walk out of the sheet into the
      // surface it covers. Queried per keystroke, like the report window's:
      // the rows change as the hiker types into the search box.
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
  }, [onClose])

  return (
    <div
      className="location-sheet__scrim"
      data-testid="location-sheet-scrim"
      // Closing on the scrim is a convenience Done and Escape both also
      // provide. Stopped here so the host's own scrim, which may close the
      // whole report window, never hears a tap meant for this one.
      onClick={(event) => {
        event.stopPropagation()
        onClose()
      }}
    >
      <div
        ref={dialogRef}
        className="location-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid="location-sheet"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="location-sheet__header">
          <h2 className="location-sheet__title" id={titleId}>
            Where is this?
          </h2>
          <button
            type="button"
            className="location-sheet__done"
            data-testid="location-sheet-done"
            onClick={onClose}
          >
            Done
          </button>
        </div>
        <div className="location-sheet__body">
          <LocationPicker {...picker} />
        </div>
      </div>
    </div>
  )
}
