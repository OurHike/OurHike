import { describe, expect, it } from 'vitest'
import {
  NO_FILTERS,
  clubs,
  filterSites,
  isFiltered,
  mileRange,
  toCsv,
  toggle,
} from './filters'
import { fixtureSites } from './fixtures'

describe('filterSites', () => {
  it('lists every site highest need first when NO_FILTERS is applied', () => {
    const shown = filterSites(fixtureSites, NO_FILTERS)
    expect(shown).toHaveLength(fixtureSites.length)
    expect(shown.map((s) => s.need)).toEqual(
      [...shown.map((s) => s.need)].sort((a, b) => b - a),
    )
  })

  it('keeps only one club and a mile range when both are set', () => {
    const shown = filterSites(fixtureSites, {
      ...NO_FILTERS,
      club: 'Example Trail Club',
      mileFrom: 101,
      mileTo: 103,
    })
    expect(shown.length).toBeGreaterThan(0)
    expect(
      shown.every(
        (s) => s.club === 'Example Trail Club' && s.mile! >= 101 && s.mile! <= 103,
      ),
    ).toBe(true)
  })

  it('treats a tier filter as excluding sites with no tier, rather than letting them through', () => {
    const shown = filterSites(fixtureSites, { ...NO_FILTERS, tiers: ['P1'] })
    expect(shown.map((s) => s.tier)).toEqual(Array(shown.length).fill('P1'))
  })

  it('matches the search text against the name, the ATC id and the land unit', () => {
    expect(
      filterSites(fixtureSites, { ...NO_FILTERS, search: 'shelter 3' }).map(
        (s) => s.rims_id,
      ),
    ).toEqual(['example-0003'])
    expect(
      filterSites(fixtureSites, { ...NO_FILTERS, search: 'example-0011' }),
    ).toHaveLength(1)
    expect(
      filterSites(fixtureSites, { ...NO_FILTERS, search: 'national forest' }),
    ).toHaveLength(fixtureSites.length)
  })
})

it('isFiltered is false for NO_FILTERS and for a search of only spaces', () => {
  expect(isFiltered(NO_FILTERS)).toBe(false)
  expect(isFiltered({ ...NO_FILTERS, search: '   ' })).toBe(false)
  expect(isFiltered({ ...NO_FILTERS, crews: ['team'] })).toBe(true)
})

it('clubs lists each club once, alphabetically', () => {
  expect(clubs(fixtureSites)).toEqual(['Example Trail Club', 'Second Example Club'])
})

it("mileRange gives the lowest and highest mile of one club's sites", () => {
  const [from, to] = mileRange(fixtureSites, 'Second Example Club')!
  expect(from).toBeCloseTo(100 + 40000 / 5280)
  expect(to).toBeCloseTo(100 + 50000 / 5280)
  expect(mileRange([], null)).toBeNull()
})

it('toggle adds a value that is absent and removes one that is present', () => {
  expect(toggle(['P1'], 'P2')).toEqual(['P1', 'P2'])
  expect(toggle(['P1', 'P2'], 'P1')).toEqual(['P2'])
})

it('toCsv quotes a cell holding a comma or a quote, and writes a missing value as empty', () => {
  const site = { ...fixtureSites[0], name: 'Rock, "the" ledge', tier: null }
  const [header, row] = toCsv([site]).trimEnd().split('\n')
  expect(header.split(',')[1]).toBe('name')
  expect(row).toContain('"Rock, ""the"" ledge"')
  expect(row.split(',')[9]).toBe('')
})
