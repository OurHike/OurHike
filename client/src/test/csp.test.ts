// The Content-Security-Policy the preview serves (#1602), pinned where a break
// would otherwise be silent.
//
// SILENCE IS THIS POLICY'S FAILURE MODE, twice over. It ships report-only, so
// a wrong directive blocks nothing and shows up only as a console message on a
// deployment nobody has open; and the hosts in it come from environment
// variables, so a build with one of them unset produces a policy that is
// syntactically fine and names a host nobody owns. Neither breaks a test, a
// build or a deploy on its own. The assertions below are what notices.
//
// The browser half is not here and cannot be: whether the app can live inside
// these directives is a question for a real page with real map data, which is
// what the preview deployment is for. What is testable here is the string -
// that it says what the build measured, and that it degrades honestly when a
// host is missing.

import { describe, it, expect } from 'vitest'
import {
  originOf,
  buildPolicy,
  headersFile,
  policyFromEnv,
  BASEMAP_ORIGIN,
  SPOTIFY_API_ORIGINS,
  SPOTIFY_PLAYER_ORIGIN,
  HOST_VARIABLES,
  HEADERS_PATH,
  HEADER_NAME,
} from '../../scripts/csp.mjs'

/** The shape a real preview build passes in - two hosts set, the API one not,
 *  which is exactly what pr-preview.yml produces (it declines to set
 *  VITE_API_BASE_URL). */
const PREVIEW_HOSTS = {
  dataBase: 'https://data.example.org/environments/ua',
  supabaseUrl: 'https://project.supabase.co',
  apiBase: undefined,
}

/** Reads one directive out of a policy string, so an assertion can name the
 *  directive it is about rather than matching a substring of the whole. */
function directive(policy: string, name: string): string | undefined {
  const found = policy
    .split('; ')
    .find((part) => part === name || part.startsWith(`${name} `))
  return found === undefined ? undefined : found.slice(name.length).trim()
}

describe('originOf', () => {
  it('keeps the origin and drops the path, so a data base URL with a prefix names one host', () => {
    expect(originOf('https://data.example.org/environments/ua')).toBe(
      'https://data.example.org',
    )
  })

  it('returns null for an unset host rather than the string "undefined"', () => {
    expect(originOf(undefined)).toBeNull()
    expect(originOf(null)).toBeNull()
    expect(originOf('')).toBeNull()
    expect(originOf('   ')).toBeNull()
  })

  it('returns null for a scheme a policy source cannot be, so javascript: cannot become one', () => {
    expect(originOf('javascript:alert(1)')).toBeNull()
    expect(originOf('data:text/html,hi')).toBeNull()
    expect(originOf('/environments/ua')).toBeNull()
    expect(originOf('data.example.org')).toBeNull()
  })

  it('keeps a non-default port, because an origin without it is a different origin', () => {
    expect(originOf('http://localhost:4173/app/')).toBe('http://localhost:4173')
  })
})

describe('buildPolicy', () => {
  it('names each configured host in connect-src, alongside self and the basemap', () => {
    const connect = directive(buildPolicy(PREVIEW_HOSTS), 'connect-src')
    expect(connect).toContain("'self'")
    expect(connect).toContain('https://data.example.org')
    expect(connect).toContain('https://project.supabase.co')
    expect(connect).toContain(BASEMAP_ORIGIN)
  })

  it('omits an unset host instead of emitting "undefined" as a source', () => {
    const policy = buildPolicy(PREVIEW_HOSTS)
    expect(policy).not.toContain('undefined')
    expect(policy).not.toContain('null')
    // The API host is the one pr-preview.yml leaves unset, so connect-src must
    // be the two hosts it does know plus self - not three with a hole in it.
    expect(directive(policy, 'connect-src')).toBe(
      "'self' https://tiles.openfreemap.org https://data.example.org https://project.supabase.co" +
        ' https://accounts.spotify.com https://api.spotify.com',
    )
  })

  it('names a host once when two variables point at the same origin', () => {
    const connect = directive(
      buildPolicy({
        dataBase: 'https://one.example.org/data',
        supabaseUrl: 'https://one.example.org',
        apiBase: 'https://one.example.org/api',
      }),
      'connect-src',
    )
    expect(connect).toBe(
      "'self' https://tiles.openfreemap.org https://one.example.org" +
        ' https://accounts.spotify.com https://api.spotify.com',
    )
  })

  it('still produces a usable policy when no host is configured at all', () => {
    const policy = buildPolicy({})
    expect(policy).not.toContain('undefined')
    expect(directive(policy, 'connect-src')).toBe(
      "'self' https://tiles.openfreemap.org https://accounts.spotify.com https://api.spotify.com",
    )
    expect(directive(policy, 'default-src')).toBe("'self'")
  })

  it('leaves no directive without a source, which a browser reads as blocking everything', () => {
    for (const part of buildPolicy({}).split('; ')) {
      expect(
        part.trim().split(/\s+/).length,
        `"${part}" has a name and no source`,
      ).toBeGreaterThan(1)
    }
  })

  it('allows no eval, because the build ships no wasm and no new Function', () => {
    const policy = buildPolicy(PREVIEW_HOSTS)
    expect(policy).not.toContain("'unsafe-eval'")
    expect(policy).not.toContain("'wasm-unsafe-eval'")
  })

  it('allows no inline script, because neither built page carries one', () => {
    expect(directive(buildPolicy(PREVIEW_HOSTS), 'script-src')).toBe("'self'")
  })

  it('allows workers from this origin, which is where all six worker chunks are built', () => {
    const policy = buildPolicy(PREVIEW_HOSTS)
    expect(directive(policy, 'worker-src')).toBe("'self'")
    // Safari's documented fallback for worker-src, and the iOS shell is WebKit.
    expect(directive(policy, 'child-src')).toBe("'self'")
  })

  it('allows blob and data images, which is how a photo and an icon reach the card', () => {
    const img = directive(buildPolicy(PREVIEW_HOSTS), 'img-src')
    expect(img).toContain('blob:')
    expect(img).toContain('data:')
  })

  it('refuses to be framed and refuses plugins, neither of which this app uses', () => {
    const policy = buildPolicy(PREVIEW_HOSTS)
    expect(directive(policy, 'frame-ancestors')).toBe("'none'")
    expect(directive(policy, 'object-src')).toBe("'none'")
    expect(directive(policy, 'base-uri')).toBe("'none'")
  })

  it('frames Spotify’s episode player and nothing else (#1683)', () => {
    expect(directive(buildPolicy(PREVIEW_HOSTS), 'frame-src')).toBe(SPOTIFY_PLAYER_ORIGIN)
  })

  it('lets the Spotify save reach Spotify’s token and library hosts', () => {
    const connect = directive(buildPolicy({}), 'connect-src')
    for (const origin of SPOTIFY_API_ORIGINS) expect(connect).toContain(origin)
  })

  it('produces the same string twice for the same hosts, so two servers cannot disagree', () => {
    expect(buildPolicy(PREVIEW_HOSTS)).toBe(buildPolicy({ ...PREVIEW_HOSTS }))
  })

  it('carries no unexpanded template, which is how a workflow variable goes missing quietly', () => {
    expect(buildPolicy(PREVIEW_HOSTS)).not.toMatch(/\$\{|\{\{/)
  })
})

describe('policyFromEnv', () => {
  it('reads the same three variables the build reads', () => {
    expect(HOST_VARIABLES).toEqual({
      dataBase: 'VITE_DATA_BASE_URL',
      supabaseUrl: 'VITE_SUPABASE_URL',
      apiBase: 'VITE_API_BASE_URL',
    })
    const policy = policyFromEnv({
      VITE_DATA_BASE_URL: 'https://data.example.org',
      VITE_SUPABASE_URL: 'https://project.supabase.co',
      VITE_API_BASE_URL: 'https://api.example.org',
    })
    for (const host of [
      'https://data.example.org',
      'https://project.supabase.co',
      'https://api.example.org',
    ]) {
      expect(directive(policy, 'connect-src')).toContain(host)
    }
  })

  it('produces a policy from an empty environment rather than throwing', () => {
    expect(policyFromEnv({})).toBe(buildPolicy({}))
  })
})

describe('headersFile', () => {
  it('writes a report-only rule, because the preview is a rehearsal and blocks nothing', () => {
    expect(HEADER_NAME).toBe('Content-Security-Policy-Report-Only')
    expect(headersFile(buildPolicy(PREVIEW_HOSTS))).toContain(
      'Content-Security-Policy-Report-Only:',
    )
  })

  it('scopes the rule to the app, not to the marketing site sharing the deployment', () => {
    expect(HEADERS_PATH).toBe('/app/*')
    expect(headersFile("default-src 'self'").split('\n')[0]).toBe('/app/*')
  })

  it('indents the header under its path and ends with a newline, as Pages parses it', () => {
    const file = headersFile("default-src 'self'")
    const lines = file.split('\n')
    expect(lines[1]).toBe("  Content-Security-Policy-Report-Only: default-src 'self'")
    expect(file.endsWith('\n')).toBe(true)
  })

  it('puts the whole policy on one line, since a wrapped header is a truncated header', () => {
    const file = headersFile(buildPolicy(PREVIEW_HOSTS))
    expect(file.trimEnd().split('\n')).toHaveLength(2)
  })
})
