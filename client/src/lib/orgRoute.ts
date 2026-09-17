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

/**
 * Which of the volunteer's own five screens is open.
 *
 *  `tread` is the bare address, for the reason `page=home` is bare under
 *  setup: a hiker who bookmarks their own miles from a welcome email should
 *  get `/my/tread`, not `/my/tread?page=tread`. The other four are query
 *  parameters because they are the same console with a different screen in
 *  it, not four documents.
 */
export type TreadPage = 'tread' | 'phone' | 'handback' | 'ridge' | 'profile'

export const TREAD_PAGES: readonly TreadPage[] = [
  'tread',
  'phone',
  'handback',
  'ridge',
  'profile',
]

/** Which console page is open, for the same reason and with the same shape. */
export type SetupPage =
  | 'home'
  | 'approve'
  | 'registry'
  | 'signoff'
  | 'addtrail'
  | 'embeds'
  | 'emails'
  | 'leaving'

export const SETUP_PAGES: readonly SetupPage[] = [
  'home',
  'approve',
  'registry',
  'signoff',
  'addtrail',
  'embeds',
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
  | { readonly kind: 'tread'; readonly org?: string; readonly page?: TreadPage }
  // THE TWO NOMINATE ADDRESSES, and they are here for the same reason the
  // three above are: both are arrived at from OUTSIDE the app and cannot be
  // reached by tapping.
  //
  // `/nominate` is where /for-orgs/nominate/ sends a hiker. That page is
  // static and has no sign-in to offer - the site carries no Supabase client
  // at all - so the address they typed is carried here, where there is an
  // account to check and a browser that can do the challenge's arithmetic.
  //
  // `/n/:token` is the only thing three people at a nominated club ever
  // receive from us. They have no account and are not asked to make one to
  // answer "is this yours?", so the token in the link is the whole of the
  // addressing. `/no-thank-you` under it is what RFC 8058's List-Unsubscribe
  // header points at, so a mail client can offer one click without anybody
  // reading to the bottom of the message.
  | { readonly kind: 'nominate'; readonly website?: string }
  | { readonly kind: 'proposal'; readonly token: string; readonly refusing?: boolean }

/** The three routes that are the CONSOLE - a rail, a shell, an organization.
 *
 *  `nominate` and `proposal` are deliberately not in it. Neither has a slug,
 *  neither belongs to an organization the visitor has a seat at, and the
 *  club's proposal screen has no account behind it at all. Giving them the
 *  console's shell would draw an org rail for somebody who is not at that org
 *  - and the type is here rather than a cast so that adding a fourth route
 *  later fails to compile in the two files that assume a slug, which is how
 *  these two were caught. */
export type ConsoleRoute = Extract<OrgRoute, { kind: 'setup' | 'volunteers' | 'tread' }>

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

function asTreadPage(value: string | null): TreadPage {
  return TREAD_PAGES.includes(value as TreadPage) ? (value as TreadPage) : 'tread'
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
  // NEVER THROWS. This runs on App's first frame, so anything it raises is a
  // white screen instead of a map - and the inputs are a browser's own
  // `location.href` plus whatever a test environment has stubbed over `URL`.
  // Null is the ordinary answer for a URL that is not one of the three, and
  // an unparseable one is not one of the three either.
  let parsed: URL
  try {
    parsed = typeof url === 'string' ? new URL(url, 'https://ourhike.org') : url
  } catch {
    return null
  }
  const parts = segments(parsed.pathname, base)
  if (parts === null) return null

  if (parts[0] === 'my' && parts[1] === 'tread' && parts.length === 2) {
    const org = parsed.searchParams.get('org')
    const page = asTreadPage(parsed.searchParams.get('page'))
    const route: OrgRoute = { kind: 'tread' }
    return {
      ...route,
      ...(org ? { org } : {}),
      ...(page === 'tread' ? {} : { page }),
    }
  }

  if (parts[0] === 'nominate' && parts.length === 1) {
    const website = parsed.searchParams.get('website')
    return website ? { kind: 'nominate', website } : { kind: 'nominate' }
  }

  if (parts[0] === 'n' && parts[1]) {
    // A token is a secret carried in a URL, so an unrecognised path under one
    // is not quietly treated as the proposal itself.
    if (parts.length === 2) return { kind: 'proposal', token: parts[1] }
    if (parts.length === 3 && parts[2] === 'no-thank-you') {
      return { kind: 'proposal', token: parts[1], refusing: true }
    }
    return null
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
    const query = [
      route.org ? `org=${encodeURIComponent(route.org)}` : null,
      route.page && route.page !== 'tread' ? `page=${route.page}` : null,
    ].filter(Boolean)
    return query.length === 0
      ? `${prefix}my/tread`
      : `${prefix}my/tread?${query.join('&')}`
  }
  if (route.kind === 'nominate') {
    return route.website
      ? `${prefix}nominate?website=${encodeURIComponent(route.website)}`
      : `${prefix}nominate`
  }
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
