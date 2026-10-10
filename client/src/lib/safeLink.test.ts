import { describe, it, expect } from 'vitest'
import { isSafeContactLink, isSafeLink } from './safeLink'

// The schemes here are the ones measured on 2026-09-17 (#1578): React 19.2.7
// rewrites `javascript:` on its own, and passes every other one of these to
// the anchor unchanged - which is why the allowlist, not React, is the
// defence for them.
const NOT_A_PAGE = [
  'javascript:alert(1)',
  'data:text/html,<script>alert(1)</script>',
  'intent://scan/#Intent;scheme=zxing;end',
  'vbscript:msgbox(1)',
  'file:///etc/passwd',
  'blob:https://ourhike.org/2d1e',
]

describe('isSafeLink', () => {
  it('admits http and https, whatever the case of the scheme', () => {
    expect(isSafeLink('https://www.nynjtc.org/hike/hike-vista-loop-trail/')).toBe(true)
    expect(isSafeLink('http://example.org/reroute')).toBe(true)
    expect(isSafeLink('HTTPS://EXAMPLE.ORG/')).toBe(true)
  })

  it.each(NOT_A_PAGE)('refuses %s', (url) => {
    expect(isSafeLink(url)).toBe(false)
  })

  it('refuses mailto and tel - a page is not a person', () => {
    expect(isSafeLink('mailto:crew@example.org')).toBe(false)
    expect(isSafeLink('tel:+12125551234')).toBe(false)
  })

  it('refuses a string the URL parser cannot read', () => {
    expect(isSafeLink('http://')).toBe(false)
  })
})

// SEC-3 of PR #1805's second review, and decision 94: a data link back into
// the app opens it in a new tab, and auth-js 2.115.0 (implicit flow,
// detectSessionInUrl) signs that tab in from an `access_token` and
// `refresh_token` in the URL's fragment or query - as whoever minted them.
const SESSION =
  'access_token=ATTACKER&refresh_token=ATTACKER_R&expires_in=3600&token_type=bearer'
// The deployed app, for the cases jsdom's http://localhost:3000 cannot show.
const APP = 'https://ourhike.org/app/'

describe('isSafeLink refuses a link back into the app', () => {
  it("refuses an absolute link to the page's own origin, with or without a session in it", () => {
    expect(isSafeLink(`${window.location.origin}/app/`)).toBe(false)
    expect(isSafeLink(`${window.location.origin}/app/#${SESSION}`)).toBe(false)
    expect(isSafeLink(`https://ourhike.org/app/?${SESSION}`, APP)).toBe(false)
    expect(isSafeLink('HTTPS://OURHIKE.ORG/for-orgs/', APP)).toBe(false)
  })

  it.each([
    ['a path', '/notices'],
    ['a bare word', 'notices'],
    ['a parent path', '../app/'],
    ['a fragment carrying a session', `#${SESSION}`],
    ['a query carrying a session', `?${SESSION}`],
    ['a host with no scheme', '//example.org/reroute'],
  ])('refuses a relative link: %s', (_, url) => {
    expect(isSafeLink(url)).toBe(false)
  })

  it('refuses an https: link with no slashes, which an https page resolves against itself', () => {
    // The dbt ATC check's scheme regex and NYNJTC's starts_with(link, 'http') both pass this one (SEC-3).
    expect(new URL(`https:#${SESSION}`, APP).origin).toBe('https://ourhike.org')
    expect(isSafeLink(`https:#${SESSION}`, APP)).toBe(false)
    expect(isSafeLink('https:example.org/reroute', APP)).toBe(false)
  })

  it.each([
    ['in its fragment', `https://example.org/notice#${SESSION}`],
    ['in its query', `https://example.org/notice?${SESSION}`],
    ['a refresh token alone', 'https://example.org/notice#refresh_token=R'],
    ["a PKCE callback's code", 'https://example.org/callback?code=0f9e'],
    ["in a hash route's query", 'https://example.org/#/route?access_token=A'],
    ['named in capitals', 'https://example.org/#ACCESS_TOKEN=A'],
  ])(
    'refuses a link to another site carrying a sign-in token (%s), which a redirect would carry back',
    (_, url) => {
      expect(isSafeLink(url)).toBe(false)
    },
  )

  it('admits a page anchor named after a key, which carries no value', () => {
    expect(isSafeLink('https://example.org/docs#code')).toBe(true)
  })

  it('admits a link whose parameter only contains the letters of one', () => {
    expect(isSafeLink('https://www.nps.gov/planyourvisit/alerts.htm?parkCode=acad')).toBe(
      true,
    )
    expect(isSafeLink('https://example.org/events?zipcode=12345&code_of_conduct=1')).toBe(
      true,
    )
  })

  it('admits another origin under the same domain', () => {
    expect(isSafeLink('https://demo.ourhike.org/join', APP)).toBe(true)
  })
})

describe('isSafeContactLink', () => {
  it('admits a page, an address and a number', () => {
    expect(isSafeContactLink('https://example.org/volunteer')).toBe(true)
    expect(isSafeContactLink('mailto:crew@example.org')).toBe(true)
    expect(isSafeContactLink('tel:+12125551234')).toBe(true)
  })

  it.each(NOT_A_PAGE)('refuses %s', (url) => {
    expect(isSafeContactLink(url)).toBe(false)
  })

  it('refuses sms and any other scheme a phone would act on', () => {
    expect(isSafeContactLink('sms:+12125551234')).toBe(false)
    expect(isSafeContactLink('market://details?id=org.example')).toBe(false)
  })

  it('refuses a page back into the app as isSafeLink does', () => {
    expect(isSafeContactLink('/volunteer')).toBe(false)
    expect(isSafeContactLink(`#${SESSION}`)).toBe(false)
    expect(isSafeContactLink(`${window.location.origin}/app/`)).toBe(false)
    expect(isSafeContactLink(`https://example.org/volunteer#${SESSION}`)).toBe(false)
  })
})
