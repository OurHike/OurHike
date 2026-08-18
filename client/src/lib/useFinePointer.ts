// Whether this device is driven by a precise pointer - a mouse or a stylus -
// rather than a finger.
//
// It exists for one decision: WIREFRAMES.md §1.5 makes the map's zoom buttons
// web-only, and both of its reasons are really about the finger. Pinch already
// zooms, and the bottom-right corner is the most reachable part of a phone
// screen, which is why locate is given it instead. Neither argument survives a
// mouse, which cannot pinch and has no thumb zone at all - so a desktop browser
// with no zoom buttons is left with the scroll wheel and nothing visible to
// press.
//
// Keyed on the POINTER and not the viewport width, for the same reason
// src/desktop.css keys its touch-target sizing that way: a 1024px tablet is a
// wide touch screen that still wants pinch, and a half-width window on a laptop
// is still a mouse. Width gets both of those backwards. lib/useDesktop.ts is
// the width question and is deliberately a separate hook.

import { useMediaQuery } from './useMediaQuery'

/** Matches where the primary pointer is precise - a mouse or a stylus. */
export const FINE_POINTER_MEDIA_QUERY = '(pointer: fine)'

/** Whether a precise pointer is driving this session. Re-evaluates when one
 *  is plugged in or unplugged.
 *
 *  Where the answer cannot be read (jsdom with no matchMedia stub), this is
 *  false, and false means the touch affordances: a phone that wrongly gets
 *  zoom buttons loses the thumb zone the wireframe reserves for locate; a
 *  desktop that wrongly loses them still has a scroll wheel. */
export function useFinePointer(): boolean {
  return useMediaQuery(FINE_POINTER_MEDIA_QUERY)
}
