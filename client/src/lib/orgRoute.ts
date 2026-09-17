/**
 * The three URLs the organization surface needs, and nothing else (#970).
 *
 * WHY THIS EXISTS AT ALL, and why it is this small. App.tsx has no router by
 * deliberate decision, and #970 is the issue that records what that costs -
 * no URL for a stretch, no landing page for a generated shelter page, no
 * link a share sheet can write, and a hiker's state lost on reload. That
 * issue also proposes the shape of the answer:
 *
 *   The set is small, and if it stays small a hand-rolled `popstate`
 *   listener over the existing state may be the whole change.
 *
 * The organization design cannot avoid the question: `/my/tread` is reachable
 * five ways by decision, and three of those five are a URL - its own
 * bookmarkable address, a link in a welcome email, and an org's own members
 * area. So this is that popstate listener, for THESE THREE ROUTES ONLY:
 *
 *   /org/:slug/setup         the console, its stage checklist and then org home
 *   /org/:slug/volunteers    roles, workdays, coverage, roster, welcome
 *   /my/tread                the volunteer's own miles
 *
 * `/app/map/mi/476.6` and every other deep link wireframe 4c draws are NOT
 * here, and the pull request that adds this does not close #970. If this
 * shape turns out to be right for them too, that is a finding to hand over
 * rather than a claim to make.
 *
 * THE BASENAME COMES FROM THE SAME PLACE THE ASSET PATHS DID. `ua.yml` and
 * `pages.yml` set `VITE_BASE_PATH` differently per environment, and #970's
 * first constraint is that a router taking its basename from anywhere else
 * breaks deep links in exactly one environment - the one nobody tests.
 * `import.meta.env.BASE_URL` is the value Vite built the asset paths from,
 * which is that variable after Vite has normalised it.
 *
 * NOTHING HERE TOUCHES App.tsx's DECISION ABOUT WHAT IS ON SCREEN beyond one
 * effect. That is #970's second constraint and #937's chokepoint: App.tsx is
 * the file 12 of the last 27 merge conflicts landed in, and a router woven
 * through it is a router every future branch fights.
 */

/** Which management page of an org's volunteer surface is open.
 *
 *  A query parameter rather than a path segment, deliberately: the six pages
 *  are one screen with a tab bar, and a person who bookmarks `?page=coverage`
 *  is bookmarking a tab rather than a document. Making each a path segment
 *  would promise six pages that can be linked to independently of the console
 *  around them, which is not what they are.
 */
export type VolunteerPage =
  'roles' | 'workdays' | 'coverage' | 'roster' | 'person' | 'welcome'

export const VOLUNTEER_PAGES: readonly VolunteerPage[] = [
  'roles',
  'workdays',
  'coverage',
  'roster',
  'person',
  'welcome',
]

/** Which console page is open, for the same reason and with the same shape. */
export type SetupPage =
  'home' | 'approve' | 'registry' | 'signoff' | 'addtrail' | 'emails' | 'leaving'

export const SETUP_PAGES: readonly SetupPage[] = [
  'home',
  'approve',
  'registry',
  'signoff',
  'addtrail',
  'emails',
  'leaving',
]

export type OrgRoute =
  | { readonly kind: 'setup'; readonly slug: string; readonly page: SetupPage }
  | {
      readonly kind: 'volunteers'
      readonly slug: string
      readonly page: VolunteerPage
      readonly person?: string
    }
  | { readonly kind: 'tread'; readonly org?: string }

/** The app's base path, with exactly one trailing slash. */
export function basePath(base: string = import.meta.env.BASE_URL): string {
  const trimmed = base.replace(/\/+$/, '')
  return `${trimmed}/`
}

/**
 * `pathname` with the basename taken off, as segments.
 *
 * Returns null when the path is not under the base at all, which is what
 * makes a router mounted at `/OurHike/` ignore `/somewhere-else` rather than
 * misreading its first segment as a route.
 */
function segments(pathname: string, base: string): string[] | null {
  const prefix = basePath(base)
  const path = pathname.endsWith('/') ? pathname : `${pathname}/`
  if (!path.startsWith(prefix)) return null
  return path
    .slice(prefix.length)
    .split('/')
    .filter((segment) => segment !== '')
}

function asSetupPage(value: string | null): SetupPage {
  return SETUP_PAGES.includes(value as SetupPage) ? (value as SetupPage) : 'home'
}

function asVolunteerPage(value: string | null): VolunteerPage {
  return VOLUNTEER_PAGES.includes(value as VolunteerPage)
    ? (value as VolunteerPage)
    : 'roles'
}

/**
 * The route a URL names, or null for every URL that is not one of the three.
 *
 * Null is the ordinary answer: the app's own entry, the map, every deep link
 * #970 leaves open. A router that returned a default route for an unknown
 * path would be claiming those URLs, which is exactly the over-reach this
 * module is scoped to avoid.
 */
export function parseOrgRoute(
  url: string | URL,
  base: string = import.meta.env.BASE_URL,
): OrgRoute | null {
  const parsed = typeof url === 'string' ? new URL(url, 'https://ourhike.org') : url
  const parts = segments(parsed.pathname, base)
  if (parts === null) return null

  if (parts[0] === 'my' && parts[1] === 'tread' && parts.length === 2) {
    const org = parsed.searchParams.get('org')
    return org ? { kind: 'tread', org } : { kind: 'tread' }
  }

  if (parts[0] === 'org' && parts.length === 3 && parts[1]) {
    const slug = parts[1]
    if (parts[2] === 'setup') {
      return { kind: 'setup', slug, page: asSetupPage(parsed.searchParams.get('page')) }
    }
    if (parts[2] === 'volunteers') {
      const person = parsed.searchParams.get('person')
      const route: OrgRoute = {
        kind: 'volunteers',
        slug,
        page: asVolunteerPage(parsed.searchParams.get('page')),
      }
      return person ? { ...route, person } : route
    }
  }

  return null
}

/** The URL a route is at, base included. The inverse of `parseOrgRoute`. */
export function orgRoutePath(
  route: OrgRoute,
  base: string = import.meta.env.BASE_URL,
): string {
  const prefix = basePath(base)
  if (route.kind === 'tread') {
    return route.org
      ? `${prefix}my/tread?org=${encodeURIComponent(route.org)}`
      : `${prefix}my/tread`
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
