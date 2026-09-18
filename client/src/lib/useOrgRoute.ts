/**
 * The browser half of #970's three routes: read the URL, write the URL, and
 * answer Back.
 *
 * `lib/orgRoute.ts` is the pure half and is where the argument lives. This is
 * the ~50 lines that touch `history` and `popstate`, kept apart from it so
 * the parsing can be tested without a DOM and so the one file that talks to
 * the History API is small enough to read in a sitting.
 *
 * WHAT IT DELIBERATELY DOES NOT DO:
 *
 * - **It does not own the app's navigation.** `lib/navigator.ts` does, and
 *   its own header says it is NOT A ROUTER. This runs beside it: the org
 *   console is a screen the shell renders when this hook says a route is
 *   open, and every other screen in the app is unaffected.
 * - **It does not intercept links.** There is no click handler here. A move
 *   inside the console calls `go`; a link out of it is an ordinary link and
 *   the browser does what browsers do.
 * - **It does not restore scroll.** Back within the console re-renders a
 *   screen at the top, which is what a tab switch does anyway.
 *
 * ONE SUBTLETY WORTH KEEPING. The first render reads `window.location`, so a
 * hiker who opened `/my/tread` from a welcome email lands there rather than
 * on the map and then jumping. That is the whole reason this is a URL and not
 * a button.
 */

import { useCallback, useEffect, useState } from 'react'
import { parseOrgRoute, type OrgRoute } from './orgRoute'

export interface OrgRouting {
  /** The route the URL names, or null when the app is anywhere else. */
  readonly route: OrgRoute | null
  /** Go to a route, pushing a history entry. Null leaves the console. */
  readonly go: (route: OrgRoute | null) => void
  /** Go to a route without a history entry - for a redirect the hiker did
   *  not ask for, which should not become a Back they have to press twice. */
  readonly replace: (route: OrgRoute | null) => void
}

function currentRoute(): OrgRoute | null {
  if (typeof window === 'undefined') return null
  return parseOrgRoute(window.location.href)
}

export function useOrgRoute(): OrgRouting {
  const [route, setRoute] = useState<OrgRoute | null>(currentRoute)

  useEffect(() => {
    // Back and Forward. Nothing else fires `popstate` - a `pushState` does
    // not - so this is only ever the browser's own buttons, which is exactly
    // the event this hook exists to answer.
    const onPop = () => setRoute(currentRoute())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  // WRITING A URL IS LOADED WHEN SOMEBODY NAVIGATES, not at launch. Reading
  // one has to happen on the first frame - App.tsx asks before its first
  // render whether this is a console address - and writing one cannot happen
  // until a tap, by which time the console's own chunk is already in. That
  // split is what keeps `orgRoutePath` and `sameOrgRoute` out of the eager
  // closure LAUNCH_BUDGET.md §3 budgets; see lib/orgRoutePath.ts.
  //
  // The await costs one microtask on a tap that is changing the whole screen,
  // and the module is resolved from memory after the first navigation.
  const move = useCallback(async (next: OrgRoute | null, mode: 'push' | 'replace') => {
    const { orgRoutePath, sameOrgRoute } = await import('./orgRoutePath')
    if (sameOrgRoute(next, currentRoute())) {
      // Same address. Pushing an identical entry means Back does nothing
      // visible once, which reads as the button being broken.
      setRoute(next)
      return
    }
    // Leaving the console goes to the app's own root rather than to
    // `history.back()`: Back would be wrong for somebody who arrived here
    // from an email, where there is nothing behind this page.
    const url =
      next === null
        ? orgRoutePath({ kind: 'tread' }).replace(/my\/tread$/, '')
        : orgRoutePath(next)
    window.history[mode === 'push' ? 'pushState' : 'replaceState'](null, '', url)
    setRoute(next)
  }, [])

  // `void` rather than returning the promise: `go` is a navigation, and a
  // caller awaiting it would be waiting on a module fetch to decide whether
  // a button worked.
  const go = useCallback((next: OrgRoute | null) => void move(next, 'push'), [move])
  const replace = useCallback(
    (next: OrgRoute | null) => void move(next, 'replace'),
    [move],
  )

  return { route, go, replace }
}
