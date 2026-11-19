import { expect, it } from 'vitest'
import { parseRoute, siteHref } from './route'

it('parseRoute reads every screen and sends anything else to the site list', () => {
  expect(parseRoute('')).toEqual({ screen: 'sites' })
  expect(parseRoute('#/')).toEqual({ screen: 'sites' })
  expect(parseRoute('#/analysis')).toEqual({ screen: 'analysis' })
  expect(parseRoute('#/guide')).toEqual({ screen: 'guide' })
  expect(parseRoute('#/site/abc-123')).toEqual({ screen: 'site', id: 'abc-123' })
  expect(parseRoute('#/nowhere')).toEqual({ screen: 'sites' })
  expect(parseRoute('#/site/')).toEqual({ screen: 'sites' })
  expect(parseRoute('#/work')).toEqual({ screen: 'work' })
  expect(parseRoute('#/claim/abc')).toEqual({ screen: 'claim', id: 'abc' })
  // Crew invites went with crews (2026-10-28): an old invite link lands on the list.
  expect(parseRoute('#/join/t0k3n')).toEqual({ screen: 'sites' })
  expect(parseRoute('#/claim/')).toEqual({ screen: 'sites' })
})

it('siteHref round-trips an id with characters a URL must escape', () => {
  const id = '{A1/B2 C3}'
  expect(parseRoute(siteHref(id))).toEqual({ screen: 'site', id })
})
