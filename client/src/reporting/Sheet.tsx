// A small window over a surface (#1563): the frame the location sheet and
// the keep-this-spot window share, so what a "second emergent window" is in
// this app is decided once.
//
// WHAT THE FRAME OWNS AND WHAT IT DOES NOT. The title, one header button,
// the scrim, focus while it is up and where focus goes back to, the Tab
// loop, and Escape. Nothing about what is inside: the location sheet puts
// the picker here, the keep window puts an answer and two buttons.
//
// FOCUS COMES BACK WHERE IT WAS. Captured on mount and restored on unmount,
// the way the report window does it for its own opener, because two of the
// three surfaces this opens over - the long form and the closure form - are
// plain screens with no focus management of their own: without this, closing
// the sheet there dropped focus to the body and the next Tab started from
// the top of the page (found by the review of #1571).
//
// TWO WAYS OUT, NAMED APART. `action` is the header button and says what it
// does - Done on the location sheet, Cancel on the keep window - and
// `onDismiss` is Escape and a tap beside the sheet, which on the keep window
// means "tap again" rather than "leave the map". A single onClose could not
// tell those apart.

import { useEffect, useId, useRef, type ReactNode } from 'react'
import './sheet.css'

export interface SheetProps {
  /** Test ids: `${name}` on the dialog and `${name}-scrim` on the scrim. */
  name: string
  title: string
  /** The header's one button, and the test id it answers to. */
  action: { label: string; onClick: () => void; testId: string }
  /** Escape, and a tap on the scrim. */
  onDismiss: () => void
  /** An extra class on the dialog, for a body that needs its own rules. */
  className?: string
  children: ReactNode
}

export function Sheet({
  name,
  title,
  action,
  onDismiss,
  className,
  children,
}: SheetProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement | null>(null)

  // The dialog itself on open, never the first control: a control here
  // CHANGES where a report goes, and it should not sit under the first
  // keystroke of somebody who has not read the title yet - the same rule
  // the report window keeps about its tiles. And back to the opener on
  // close, for the reason in the header.
  const openedFrom = useRef<Element | null>(null)
  useEffect(() => {
    openedFrom.current = document.activeElement
    dialogRef.current?.focus()
    return () => {
      const returning = openedFrom.current
      if (returning instanceof HTMLElement && returning.isConnected) returning.focus()
    }
  }, [])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onDismiss()
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
  }, [onDismiss])

  return (
    <div
      className="sheet__scrim"
      data-testid={`${name}-scrim`}
      // Stopped here so the host's own scrim, which may close the whole
      // report window, never hears a tap meant for this one.
      onClick={(event) => {
        event.stopPropagation()
        onDismiss()
      }}
    >
      <div
        ref={dialogRef}
        className={className === undefined ? 'sheet' : `sheet ${className}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid={name}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sheet__header">
          <h2 className="sheet__title" id={titleId}>
            {title}
          </h2>
          <button
            type="button"
            className="sheet__action"
            data-testid={action.testId}
            onClick={action.onClick}
          >
            {action.label}
          </button>
        </div>
        <div className="sheet__body">{children}</div>
      </div>
    </div>
  )
}
