// One media-query subscription, shared by the two hooks that were line-for-
// line copies of it (#175): lib/useDesktop.ts (viewport width) and
// lib/useFinePointer.ts (pointer precision). They stay separate hooks because
// they answer different questions - see each one's header for which decision
// it exists for - but the machinery underneath is one thing, and two copies
// of a subscription is how one of them gets a fix the other silently misses.

import { useEffect, useState } from 'react'

function matches(query: string): boolean {
  // Guarded rather than assumed: jsdom has no matchMedia unless a test stubs
  // one, and `false` is the honest default for "cannot tell". What false
  // MEANS is each caller's decision to document - the phone layout for
  // useDesktop, the touch affordances for useFinePointer - and both callers
  // chose it because their false is the answer that works everywhere.
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function')
    return false
  return window.matchMedia(query).matches
}

/** Whether `query` currently matches. Re-evaluates when the browser says the
 *  answer changed - a resize past the breakpoint, a mouse plugged in. */
export function useMediaQuery(query: string): boolean {
  const [matched, setMatched] = useState(() => matches(query))

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return

    const list = window.matchMedia(query)
    const update = (event: MediaQueryListEvent) => setMatched(event.matches)

    // Re-read on mount as well as on change: the first render used whatever
    // matches() said before effects ran, and a window resized between the
    // two would otherwise keep the stale answer until the next change event.
    setMatched(list.matches)
    list.addEventListener('change', update)
    return () => list.removeEventListener('change', update)
  }, [query])

  return matched
}
