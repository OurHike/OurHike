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

import { useEffect, useState } from 'react'

/** Matches where the primary pointer is precise - a mouse or a stylus. */
export const FINE_POINTER_MEDIA_QUERY = '(pointer: fine)'

function matches(): boolean {
  // Guarded rather than assumed, and defaulting the same way lib/useDesktop.ts
  // does: jsdom has no matchMedia unless a test stubs one, and the honest
  // answer to "cannot tell" is the touch one. A phone that wrongly gets zoom
  // buttons loses the thumb zone the wireframe reserves for locate; a desktop
  // that wrongly loses them still has a scroll wheel.
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function')
    return false
  return window.matchMedia(FINE_POINTER_MEDIA_QUERY).matches
}

/** Whether a precise pointer is driving this session. Re-evaluates when one is
 *  plugged in or unplugged. */
export function useFinePointer(): boolean {
  const [finePointer, setFinePointer] = useState(matches)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return

    const query = window.matchMedia(FINE_POINTER_MEDIA_QUERY)
    const update = (event: MediaQueryListEvent) => setFinePointer(event.matches)

    // Re-read on mount as well as on change, for the reason useDesktop.ts
    // gives: the first render used whatever matches() said before effects ran.
    setFinePointer(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  return finePointer
}
