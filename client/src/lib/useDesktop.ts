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

import { useMediaQuery } from './useMediaQuery'

/** WEBSITE.md §6. Must match the `min-width` in src/desktop.css. */
export const DESKTOP_MIN_WIDTH = 900

export const DESKTOP_MEDIA_QUERY = `(min-width: ${DESKTOP_MIN_WIDTH}px)`

/** Whether this viewport gets the desktop layout. Re-evaluates on resize.
 *
 *  Where the answer cannot be read (jsdom with no matchMedia stub), this is
 *  false, and false means the phone layout: it works at every width, where
 *  the desktop layout at 375px would be a sidebar eating half the map. */
export function useDesktop(): boolean {
  return useMediaQuery(DESKTOP_MEDIA_QUERY)
}
