/**
 * The organization surface's front door, and the first thing behind
 * `import()` rather than in front of it.
 *
 * App.tsx used to hold all of this: the route hook, three `lazy()` screens and
 * the switch between them. That put #970's whole router in the eager closure
 * for every hiker, to answer a question App only needed a boolean for -
 * lib/orgEntry.ts carries the measurement and why the split is drawn where it
 * is. What App keeps is `useOrgEntry()`; what moved here is everything that
 * reads a route rather than recognising one.
 *
 * THE THREE SCREENS STAY SEPARATELY LAZY inside this chunk. Importing them
 * statically would be simpler and would merge the console - 169 KB of it -
 * into the chunk a club officer downloads to answer "is this your
 * organization?" on a phone at a trailhead. They are three audiences, so they
 * stay three chunks; this file is only the switch.
 *
 * ONE ROUTE HOOK, which is OrgConsole's own constraint restated: two
 * instances of `useOrgRoute` would each keep a copy of the route, and a `go`
 * inside the console would move the URL while this switch still rendered the
 * old screen.
 */

import { Suspense, lazy, useEffect } from 'react'
import { useOrgRoute } from '../lib/useOrgRoute'
import type { UnitSystem } from '../lib/units'

const OrgConsole = lazy(() =>
  import('./OrgConsole').then((module) => ({ default: module.OrgConsole })),
)
const Nominate = lazy(() =>
  import('./screens/Nominate').then((module) => ({ default: module.Nominate })),
)
const Proposal = lazy(() =>
  import('./screens/Proposal').then((module) => ({ default: module.Proposal })),
)

export function OrgEntry({ units }: { units: UnitSystem }) {
  const routing = useOrgRoute()
  const route = routing.route

  // THE ONE DISAGREEMENT THIS SPLIT COULD PRODUCE, handled rather than
  // assumed away. App.tsx rendered this because `isOrgEntry` recognised the
  // address; if the full parse then says null, App has already returned and
  // there is nothing on screen to fall back to. `orgEntry.test.ts` asserts
  // the two agree over every URL shape either could answer differently, so
  // this is unreachable by anything that suite covers - and a hiker who found
  // the gap anyway gets the app rather than a blank page. `replace` rather
  // than `go` because a URL nobody asked for should not become a Back they
  // have to press twice.
  useEffect(() => {
    if (route === null) routing.replace(null)
  }, [route, routing])
  if (route === null) return null

  return (
    <Suspense fallback={<div className="app__screen">Opening…</div>}>
      {route.kind === 'nominate' ? (
        <Nominate onLeave={() => routing.go(null)} />
      ) : route.kind === 'proposal' ? (
        <Proposal token={route.token} {...(route.refusing ? { refusing: true } : {})} />
      ) : (
        <OrgConsole routing={routing} units={units} />
      )}
    </Suspense>
  )
}
