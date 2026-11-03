// The sign-in ask as a small window over whatever is behind it (#1596).
//
// AN OVERLAY, NOT A `flowScreen`, and for the reason screens/ReportForm.tsx
// was moved down here in #1439: a `flowScreen` takes the map subtree out of
// flow and out of the accessibility tree, so the screen a hiker was standing
// on disappears behind the question. For a two-button ask that is a great
// deal of ceremony, and on the contribution path it takes away the map the
// report was about.
//
// Both steps of the email path live inside this one window - the address,
// then the code - rather than the second pushing a screen of its own. The
// window stays put and its contents change, which is what makes "send
// another code" and "use a different address" feel like the same place.
//
// Docked to the foot, following chrome/BailSheet.tsx, which is this app's
// idiom for a question asked over a screen rather than instead of one. At
// 900px and up it becomes a centred box, because a full-width strip across a
// laptop is a band of empty paper with three buttons lost in the middle.
//
// ESCAPE WITHOUT ARMING ANYTHING. The wrapper takes focus on mount rather
// than the first button, so Escape works immediately and a stray Enter does
// not start an OAuth round trip on whichever provider happens to be first.
// The view has its own "Not now", so there is no second close control here:
// two controls doing one job is what screens/ReportForm.tsx's own comment
// warns is worse for a screen reader than none.
//
// `aria-modal="true"` IS A PROMISE, AND THE FIRST VERSION DID NOT KEEP IT.
// It tells assistive technology that everything outside this element is
// unavailable, and nothing made that true: the review of #1596 got from the
// You settings screen, through the dialog, to "Report a problem with the
// app" - opening a second full screen UNDERNEATH an open modal - and a
// keyboard could Tab straight out into the sidebar. Two things keep the
// promise now, and both are in this file because the shell cannot do either
// without wrapping its whole fragment in a div:
//
//   - the backdrop below, which is a real element covering the viewport, so
//     a tap that lands outside the panel closes the window instead of
//     reaching whatever it was over. Transparent rather than dimmed: the map
//     staying visible is the whole of what #1596 changed, and a scrim would
//     undo it. What it blocks is the pointer, not the view.
//   - the Tab handler, which keeps focus inside the panel. Not a library and
//     not `inert` on the rest: `inert` would have to be applied by the shell
//     to siblings it builds in six branches, and this is the one element
//     that knows the window is open.

import { useEffect, useRef, type KeyboardEvent, type ReactNode } from 'react'
import './signInWindow.css'

/** Everything a Tab can land on inside the panel. `:not([disabled])` because
 *  the email step disables its own submit while a code is in flight, and a
 *  trap that cycles onto a dead control reads as focus having vanished. */
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export interface SignInWindowProps {
  /** The dialog's accessible name. The view inside carries its own heading;
   *  this is what a screen reader announces when the window opens. */
  label: string
  /** Escape, a tap on the backdrop, and whatever the view's own "Not now"
   *  does. */
  onClose: () => void
  children: ReactNode
}

export function SignInWindow({ label, onClose, children }: SignInWindowProps) {
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    panel.current?.focus()
  }, [])

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      onClose()
      return
    }
    if (event.key !== 'Tab') return

    const stops = [...(panel.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])]
    // Nothing to hold focus on - the panel keeps it, which is where it
    // started. Returning here rather than reading `stops[0]` of an empty
    // list, which is how a trap turns into a thrown TypeError.
    if (stops.length === 0) return

    const first = stops[0]
    const last = stops[stops.length - 1]
    const active = document.activeElement

    // The wrapper itself holds focus until the first Tab (see the note
    // above), so a plain Tab from there goes to the first control and a
    // Shift+Tab to the last - rather than out of the window, which is where
    // the browser would send it from a `tabIndex={-1}` div.
    if (active === panel.current) {
      event.preventDefault()
      ;(event.shiftKey ? last : first).focus()
      return
    }
    if (event.shiftKey && active === first) {
      event.preventDefault()
      last.focus()
      return
    }
    if (!event.shiftKey && active === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <>
      {/* Not a button and not focusable: the panel's own "Not now" is the
          control that closes this, and a second one in the tab order is the
          duplicate the note above rules out. `aria-hidden` keeps it out of
          the reading order; the pointer is the only thing it is for. */}
      <div className="sign-in-window__backdrop" aria-hidden="true" onClick={onClose} />
      <div
        ref={panel}
        className="sign-in-window"
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        {children}
      </div>
    </>
  )
}
