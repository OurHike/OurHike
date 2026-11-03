import { expect, it } from 'vitest'
import { feet, isOfficial, miles, regimeWords, siteKind, siteName } from './format'
import { fixtureSites } from './fixtures'

it('feet and miles say "unknown" for a missing value rather than zero', () => {
  expect(feet(null)).toBe('unknown')
  expect(miles(null)).toBe('unknown')
  expect(feet(1234.4)).toBe('1,234 ft')
  expect(miles(0.44)).toBe('0.4 mi')
})

it('siteName falls back to the first eight characters of the ATC id when ATC gives no name', () => {
  expect(siteName({ ...fixtureSites[0], name: '  ' })).toBe('Site example-')
  expect(siteName(fixtureSites[0])).toBe('Example site 1')
})

it('siteKind and isOfficial treat shelters and club campsites as official, user-created sites as not', () => {
  const shelter = fixtureSites.find((s) => s.site_type === 'Shelter')!
  expect(siteKind(shelter)).toBe('Shelter')
  expect(isOfficial(shelter)).toBe(true)
  expect(siteKind(fixtureSites[0])).toBe('User-created campsite')
  expect(isOfficial(fixtureSites[0])).toBe(false)
  expect(siteKind({ ...fixtureSites[0], site_type: null })).toBe('Type not recorded')
})

it('regimeWords keeps the question mark on a guessed camping regime', () => {
  expect(regimeWords('dispersed_allowed?')).toBe('dispersed camping allowed?')
  expect(regimeWords('unknown')).toBe('not known')
})
