// The download, as a window over whatever is already on screen.
//
// It was a tab of its own until 2026-08-05. What is behind it is ONE
// whole-corridor package (WIREFRAMES.md Known Deviations #1): started once,
// deleted maybe never. A permanent target in the thumb zone bought a screen
// almost nobody opens twice, and the moment someone genuinely wants it - "why
// is there no map under my trail line" - was reached by leaving the map. It is
// opened from the background picker now (chrome/BackgroundPicker.tsx), which is
// where that moment actually happens. See chrome/tabs.ts.
//
// A window rather than a bottom sheet like the legend, because it is not
// describing the map behind it. The legend answers "what am I looking at" and
// so has to leave the thing being looked at visible; this is a whole decision -
// which detail level, how many hundred megabytes, start, resume, delete - and
// the map is no part of it. On a phone it fills the screen; on a desktop it is
// a panel on a dimmed page (screens/downloads.css).
//
// The shell passes the body in rather than this file composing it, because
// what belongs in the window is the same set of things that belonged on the
// tab - the install prompt, the build's own "no data source configured"
// warning, whatever the last download failed with - and all of those are the
// shell's to know.
//
// Escape closes it, and so does a tap on the backdrop. There is deliberately
// NO focus trap: nothing else in this app has one, and half of one - focus
// moved in, nothing keeping it there - is the worse of the two states to be in
// because it looks handled. Focus does move to the panel on open, so a screen
// reader lands on what just appeared rather than staying wherever the control
// that opened it left it, and the close button is the first thing in.

import { useEffect, useRef, type ReactNode } from 'react'
import './downloads.css'

export interface DownloadsDialogProps {
  onClose: () => void
  children: ReactNode
}

const TITLE_ID = 'downloads-dialog-title'

export function DownloadsDialog({ onClose, children }: DownloadsDialogProps) {
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    panel.current?.focus()
  }, [])

  // On the document rather than the panel, so Escape works from the moment the
  // window opens whether or not focus ever reached anything inside it.
  useEffect(() => {
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', dismiss)
    return () => document.removeEventListener('keydown', dismiss)
  }, [onClose])

  return (
    <div
      className="downloads-dialog"
      // Only a hit on the backdrop ITSELF dismisses. Every click inside the
      // panel bubbles out through this element too, and a download deleted
      // because the tap landed a few pixels off the button would be the worst
      // possible thing for this particular window to get wrong.
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={panel}
        className="downloads-dialog__panel"
        role="dialog"
        /* NOT `aria-modal="true"` (#315), and that is this file's own
           reasoning followed through. The comment above already refuses a
           focus trap - "half of one is worse than none because it looks
           handled" - and `aria-modal` was the same mistake one layer up:
           it TELLS assistive tech the background is inert while Tab walks
           straight into it, so a screen-reader user is given a guarantee the
           page does not keep. The role still says "this is a dialog"; what is
           gone is the claim nobody was honouring.

           If a trap is ever built, this attribute comes back with it, in the
           same change. */
        aria-labelledby={TITLE_ID}
        tabIndex={-1}
      >
        <div className="downloads-dialog__head">
          <h2 id={TITLE_ID} className="downloads-dialog__title">
            Offline map
          </h2>
          <button type="button" className="downloads-dialog__close" onClick={onClose}>
            <span className="visually-hidden">Close</span>
            <span aria-hidden="true">×</span>
          </button>
        </div>

        <div className="downloads-dialog__body">{children}</div>
      </div>
    </div>
  )
}
