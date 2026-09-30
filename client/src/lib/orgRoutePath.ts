/**
 * Writing an org URL, which is only ever needed once somebody is navigating.
 *
 * **SPLIT OUT OF `orgRoute.ts` TO KEEP IT OUT OF THE FIRST FRAME.** Reading
 * the URL has to happen on every launch - `App.tsx` asks, before its first
 * render, whether this is a console address or the map. Writing one cannot
 * happen until a hiker taps something, and by then the console's own chunk has
 * loaded. `check-build-output.mjs` is what made the difference matter: the org
 * surface put roughly 1.5 KB into the eager closure and
 * LAUNCH_BUDGET.md §3's 250 KB had about 1.7 KB of room, so the branch cleared
 * it locally and failed by 146 bytes on CI.
 *
 * `useOrgRoute` reaches this with a dynamic `import()` inside its `move`, so
 * nothing here is parsed before the first frame. The delay that buys is one
 * microtask on a tap that is already changing the whole screen.
 */

import { basePath, type OrgRoute } from './orgRoute'

/** The URL a route is at, base included. The inverse of `parseOrgRoute`. */
export function orgRoutePath(
  route: OrgRoute,
  base: string = import.meta.env.BASE_URL,
): string {
  const prefix = basePath(base)
  if (route.kind === 'tread') {
    const query = [
      route.org ? `org=${encodeURIComponent(route.org)}` : null,
      route.page && route.page !== 'tread' ? `page=${route.page}` : null,
    ].filter(Boolean)
    return query.length === 0
      ? `${prefix}my/tread`
      : `${prefix}my/tread?${query.join('&')}`
  }
  if (route.kind === 'nominate') return `${prefix}nominate`
  if (route.kind === 'proposal') {
    const token = encodeURIComponent(route.token)
    return route.refusing ? `${prefix}n/${token}/no-thank-you` : `${prefix}n/${token}`
  }
  const slug = encodeURIComponent(route.slug)
  if (route.kind === 'setup') {
    // The stage checklist and org home are the same screen with two lives, so
    // `page=home` is the bare address rather than a parameter: an org
    // bookmarking their console should get `/org/x/setup`, not
    // `/org/x/setup?page=home`.
    return route.page === 'home'
      ? `${prefix}org/${slug}/setup`
      : `${prefix}org/${slug}/setup?page=${route.page}`
  }
  const person = route.person ? `&person=${encodeURIComponent(route.person)}` : ''
  return `${prefix}org/${slug}/volunteers?page=${route.page}${person}`
}

/** Whether two routes are the same address - so a push can be skipped. */
export function sameOrgRoute(a: OrgRoute | null, b: OrgRoute | null): boolean {
  if (a === null || b === null) return a === b
  return orgRoutePath(a, '/') === orgRoutePath(b, '/')
}
