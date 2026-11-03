// The keys a small window answers to, in one place (#1563; review of #1571).
//
// WHAT THIS REPLACES. The report window and the sheet frame each carried a
// hand-rolled copy of the same document-level listener - Escape to close,
// Tab looping inside the dialog - and the copies had already drifted: the
// window's went quiet while the window stood aside for the map's crosshair,
// the sheet's did not, so an Escape pressed over the map dismissed a hidden
// sheet and dropped the tap that was waiting on it. One hook, one `active`
// flag, and a host that stands aside passes it.
//
// A HAND-ROLLED TRAP RATHER THAN A DEPENDENCY, still: these are the app's
// only true modals, and one hook does not earn a package.

import { useEffect, type RefObject } from 'react'

const FOCUSABLE =
  'button:not([disabled]), textarea, [href], input, select, [tabindex]:not([tabindex="-1"])'

export interface FocusTrapOptions {
  /**
   * False and nothing is heard: the dialog is mounted but hidden and inert
   * behind something else, and the keys belong to that something. The
   * report window passes `!standingAside`; a sheet passes what its host
   * hands it.
   */
  active?: boolean
  /** Escape. The event is stopped so nothing under the dialog hears it. */
  onEscape: () => void
  /** False and Tab is left alone - for a host whose own sheet is looping
   *  focus at that moment, so two loops do not fight over one keystroke. */
  loop?: boolean
}

/**
 * Escape closes and Tab loops, on `document` in the capture phase so the
 * dialog hears the key before whatever is under it. Queried per keystroke
 * rather than cached: a body can swap entirely between two renders (the
 * report window's tiles and receipt; a picker's rows as a search is typed),
 * so any cached list would be stale exactly when it is used.
 */
export function useFocusTrap(
  dialogRef: RefObject<HTMLElement | null>,
  { active = true, onEscape, loop = true }: FocusTrapOptions,
): void {
  useEffect(() => {
    if (!active) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onEscape()
        return
      }
      if (event.key !== 'Tab' || !loop) return
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE)
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
  }, [active, onEscape, loop, dialogRef])
}
