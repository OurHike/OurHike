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

  it('resolves a relative path against the page, as an anchor would', () => {
    expect(isSafeLink('/notices')).toBe(true)
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
})
