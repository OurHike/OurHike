// One breakpoint, named once, for the layout that is not a phone.
//
// WEBSITE.md §6 puts it at 900px. Most of what happens above it is CSS
// (src/desktop.css), and that is deliberate: a rule inside a media query
// cannot regress the phone layout, which §8 names as the constraint that
// matters because the phone is the one that gets used on trail.
//
// A few things cannot be done in CSS, and they are why this hook exists. The
// legend is `role="dialog" aria-modal="true"` and renders nothing when closed;
// on a desktop it is a persistent panel that is never dismissed. No stylesheet
// can change what a component announces itself as, or make it render when it
// has returned null.
//
// The number lives here rather than only in the stylesheet so the two cannot
// drift - a JS breakpoint at 900 and a CSS one at 960 would produce a layout
// that is a sidebar with a modal legend in it, for a 60px band nobody would
// think to test.

import { useEffect, useState } from 'react'

/** WEBSITE.md §6. Must match the `min-width` in src/desktop.css. */
export const DESKTOP_MIN_WIDTH = 900

export const DESKTOP_MEDIA_QUERY = `(min-width: ${DESKTOP_MIN_WIDTH}px)`

function matches(): boolean {
  // Guarded rather than assumed. jsdom has no matchMedia unless a test stubs
  // one, and the honest default for "cannot tell" is the phone layout: it
  // works at every width, where the desktop layout at 375px would be a
  // sidebar eating half the map.
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia(DESKTOP_MEDIA_QUERY).matches
}

/** Whether this viewport gets the desktop layout. Re-evaluates on resize. */
export function useDesktop(): boolean {
  const [isDesktop, setIsDesktop] = useState(matches)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return

    const query = window.matchMedia(DESKTOP_MEDIA_QUERY)
    const update = (event: MediaQueryListEvent) => setIsDesktop(event.matches)

    // Re-read on mount as well as on change: the first render used whatever
    // matches() said before effects ran, and a window resized between the two
    // would otherwise keep the stale layout until the next resize.
    setIsDesktop(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  return isDesktop
}
