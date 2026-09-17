/**
 * The three URLs, and every URL that is not one of them (#970).
 *
 * The test that matters most is `an unknown path is not a route`: a router
 * that returned a default for an unknown path would be claiming every deep
 * link #970 leaves open, which is precisely the over-reach this module is
 * scoped to avoid. The basename tests are the second: #970's own first
 * constraint is that a basename read from anywhere but `VITE_BASE_PATH`
 * breaks deep links in exactly one environment - the one nobody tests.
 */

import { describe, expect, it } from 'vitest'
import { basePath, orgRoutePath, parseOrgRoute, sameOrgRoute } from './orgRoute'

const ROOT = '/'
const PROJECT_PAGES = '/OurHike/'

describe('parsing the three routes', () => {
  it('reads a volunteer to their own miles', () => {
    expect(parseOrgRoute('https://ourhike.org/my/tread', ROOT)).toEqual({ kind: 'tread' })
  })

  it('carries the org a welcome email named', () => {
    expect(
      parseOrgRoute('https://ourhike.org/my/tread?org=ramapo-trail-conference', ROOT),
    ).toEqual({
      kind: 'tread',
      org: 'ramapo-trail-conference',
    })
  })

  it('reads a console to its org home when no page is named', () => {
    expect(
      parseOrgRoute('https://ourhike.org/org/ramapo-trail-conference/setup', ROOT),
    ).toEqual({
      kind: 'setup',
      slug: 'ramapo-trail-conference',
      page: 'home',
    })
  })

  it('reads the page a console bookmark named', () => {
    expect(parseOrgRoute('https://ourhike.org/org/x/setup?page=registry', ROOT)).toEqual({
      kind: 'setup',
      slug: 'x',
      page: 'registry',
    })
  })

  it('falls back to a real page rather than trusting a typo in the URL', () => {
    // A hand-edited `?page=` is somebody's guess, not an instruction. Landing
    // on the console's home beats rendering nothing.
    expect(parseOrgRoute('https://ourhike.org/org/x/setup?page=nonsense', ROOT)).toEqual({
      kind: 'setup',
      slug: 'x',
      page: 'home',
    })
  })

  it('reads one volunteer profile inside the volunteer surface', () => {
    expect(
      parseOrgRoute('https://ourhike.org/org/x/volunteers?page=person&person=p1', ROOT),
    ).toEqual({
      kind: 'volunteers',
      slug: 'x',
      page: 'person',
      person: 'p1',
    })
  })
})

describe('what is not a route', () => {
  it.each([
    'https://ourhike.org/',
    'https://ourhike.org/map',
    'https://ourhike.org/org',
    'https://ourhike.org/org/x',
    'https://ourhike.org/org/x/setup/extra',
    'https://ourhike.org/org//setup',
    'https://ourhike.org/my',
    'https://ourhike.org/my/tread/extra',
    // Wireframe 4c's deep link, which #970 still owns and this does not.
    'https://ourhike.org/app/map/mi/476.6',
  ])('%s is not a route this module claims', (url) => {
    expect(parseOrgRoute(url, ROOT)).toBeNull()
  })
})

describe('the basename, which is the one thing that breaks in exactly one environment', () => {
  it('reads a route under a project-pages base', () => {
    expect(parseOrgRoute('https://x.github.io/OurHike/my/tread', PROJECT_PAGES)).toEqual({
      kind: 'tread',
    })
  })

  it('refuses the same path when it is not under the base', () => {
    // The failure this prevents: a build served at /OurHike/ reading
    // `/my/tread` - somebody else's path - as its own route.
    expect(parseOrgRoute('https://x.github.io/my/tread', PROJECT_PAGES)).toBeNull()
  })

  it('normalises a base with or without its trailing slash', () => {
    expect(basePath('/OurHike')).toBe('/OurHike/')
    expect(basePath('/OurHike/')).toBe('/OurHike/')
    expect(basePath('/')).toBe('/')
  })

  it('writes paths under the base it was given', () => {
    expect(orgRoutePath({ kind: 'tread' }, PROJECT_PAGES)).toBe('/OurHike/my/tread')
  })
})

describe('writing a route back out', () => {
  it('round-trips every route it can parse', () => {
    const routes = [
      { kind: 'tread' as const },
      { kind: 'tread' as const, org: 'ramapo-trail-conference' },
      { kind: 'setup' as const, slug: 'x', page: 'home' as const },
      { kind: 'setup' as const, slug: 'x', page: 'signoff' as const },
      { kind: 'volunteers' as const, slug: 'x', page: 'coverage' as const },
      { kind: 'volunteers' as const, slug: 'x', page: 'person' as const, person: 'p1' },
    ]
    for (const route of routes) {
      expect(
        parseOrgRoute(`https://ourhike.org${orgRoutePath(route, ROOT)}`, ROOT),
      ).toEqual(route)
    }
  })

  it("leaves the console's home at the bare address", () => {
    // One screen with two lives, so an org bookmarking their console should
    // get /org/x/setup rather than /org/x/setup?page=home.
    expect(orgRoutePath({ kind: 'setup', slug: 'x', page: 'home' }, ROOT)).toBe(
      '/org/x/setup',
    )
  })

  it('escapes a slug rather than letting it write the path', () => {
    const path = orgRoutePath({ kind: 'setup', slug: 'a/b?c', page: 'home' }, ROOT)
    expect(path).toBe('/org/a%2Fb%3Fc/setup')
  })
})

describe('telling two addresses apart', () => {
  it('knows when a move would change nothing', () => {
    const here = { kind: 'volunteers' as const, slug: 'x', page: 'roles' as const }
    expect(sameOrgRoute(here, { ...here })).toBe(true)
    expect(sameOrgRoute(here, { ...here, page: 'coverage' })).toBe(false)
    expect(sameOrgRoute(here, null)).toBe(false)
    expect(sameOrgRoute(null, null)).toBe(true)
  })
})
