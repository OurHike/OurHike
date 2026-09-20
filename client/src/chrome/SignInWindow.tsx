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
// The ask has its own "Not now", so there is no second close control here:
// two controls doing one job is what screens/ReportForm.tsx's own comment
// warns is worse for a screen reader than none.

import { useEffect, useRef, type KeyboardEvent, type ReactNode } from 'react'
import './signInWindow.css'

export interface SignInWindowProps {
  /** The dialog's accessible name. The view inside carries its own heading;
   *  this is what a screen reader announces when the window opens. */
  label: string
  /** Escape, and whatever the view's own "Not now" does. */
  onClose: () => void
  children: ReactNode
}

export function SignInWindow({ label, onClose, children }: SignInWindowProps) {
  const window = useRef<HTMLDivElement>(null)

  useEffect(() => {
    window.current?.focus()
  }, [])

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') onClose()
  }

  return (
    <div
      ref={window}
      className="sign-in-window"
      role="dialog"
      aria-modal="true"
      aria-label={label}
      tabIndex={-1}
      onKeyDown={onKeyDown}
    >
      {children}
    </div>
  )
}
