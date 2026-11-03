/**
 * The first frame's half of #970's router: is this an organization address,
 * and has that answer changed.
 *
 * `useOrgRoute` is the other half and is where a route is actually read. This
 * hook exists so that reading one can be behind `import()` at all - App.tsx
 * needs an answer before its first render, and a boolean is an answer it can
 * get without the page tables. lib/orgEntry.ts has the measurement that made
 * the split worth making.
 *
 * WHY IT LISTENS TO TWO EVENTS. `popstate` is Back and Forward, the same
 * thing `useOrgRoute` listens for. `ORG_ROUTE_CHANGED` is the console writing
 * a URL: `history.pushState` deliberately does not fire `popstate`, so
 * without it a hiker who left the console - `go(null)` from the nominate
 * screen - would have the app's own URL in the address bar and the org shell
 * still on screen, which is the one way this split can strand somebody.
 */

import { useEffect, useState } from 'react'
import { isOrgEntry } from './orgEntry'

/** Dispatched on `window` by `useOrgRoute` after it writes a URL. */
export const ORG_ROUTE_CHANGED = 'ourhike:orgroute'

function atOrgEntry(): boolean {
  if (typeof window === 'undefined') return false
  return isOrgEntry(window.location.href)
}

export function useOrgEntry(): boolean {
  const [inOrg, setInOrg] = useState(atOrgEntry)

  useEffect(() => {
    const recheck = () => setInOrg(atOrgEntry())
    window.addEventListener('popstate', recheck)
    window.addEventListener(ORG_ROUTE_CHANGED, recheck)
    return () => {
      window.removeEventListener('popstate', recheck)
      window.removeEventListener(ORG_ROUTE_CHANGED, recheck)
    }
  }, [])

  return inOrg
}
