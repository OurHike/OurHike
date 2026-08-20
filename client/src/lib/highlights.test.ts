import { describe, it, expect } from 'vitest'
import {
  BASIS_STRENGTH,
  NAMED,
  PUBLISHED,
  VISITED,
  highlightMiles,
  highlightsWithin,
  parseHighlights,
  storedHighlights,
  strongestBasis,
  type Highlight,
} from './highlights'

/** One record in the shape pipeline/export_highlights.py's as_published writes. */
function artifact(overrides: Record<string, unknown> = {}) {
  return {
    id: 'mcafee-knob',
    name: 'McAfee Knob',
    bases: [NAMED],
    citations: {
      [NAMED]: {
        by: 'OurHike',
        note: 'The most photographed spot on the A.T.',
        reviewed: '2026-08-20',
      },
    },
    legs: [{ trail: 'AT', start_mile: 705.6, end_mile: 709.1 }],
    club: 'RATC',
    ...overrides,
  }
}

function parsed(overrides: Record<string, unknown> = {}): Highlight {
  return parseHighlights({ highlights: [artifact(overrides)] })[0]
}

describe('parseHighlights', () => {
  it('reads the record the exporter publishes', () => {
    expect(parsed()).toEqual({
      id: 'mcafee-knob',
      name: 'McAfee Knob',
      bases: [NAMED],
      citations: {
        [NAMED]: {
          by: 'OurHike',
          note: 'The most photographed spot on the A.T.',
          reviewed: '2026-08-20',
        },
      },
      legs: [{ trail: 'AT', startMile: 705.6, endMile: 709.1 }],
      club: 'RATC',
    })
  })

  it('carries the trail each leg is measured on', () => {
    // A mile only means something relative to one trail, which is why the
    // range moved down a level in the first place.
    expect(parsed().legs[0].trail).toBe('AT')
  })

  it('normalises a leg that arrives backwards', () => {
    // A negative length would quietly subtract from a multi-leg total.
    const backwards = parsed({
      legs: [{ trail: 'AT', start_mile: 709.1, end_mile: 705.6 }],
    })
    expect(backwards.legs[0]).toEqual({ trail: 'AT', startMile: 705.6, endMile: 709.1 })
  })

  it('reads a highlight that crosses trails', () => {
    const loop = parsed({
      legs: [
        { trail: 'AT', start_mile: 1823.4, end_mile: 1825.1 },
        { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
      ],
    })
    expect(loop.legs.map((leg) => leg.trail)).toEqual(['AT', 'Falling Waters Trail'])
  })

  it.each([
    ['a highlight with no placeable leg', { legs: [] }],
    ['a highlight whose legs are unreadable', { legs: [{ trail: 'AT' }] }],
    ['a highlight with no name', { name: '' }],
    ['a highlight with no id', { id: '' }],
    ['a highlight claiming no basis', { bases: [] }],
  ])('drops %s rather than putting a nameless marker on the map', (_label, override) => {
    expect(parseHighlights({ highlights: [artifact(override)] })).toEqual([])
  })

  it('keeps the rows beside a bad one', () => {
    const list = parseHighlights({
      highlights: [
        artifact({ id: '' }),
        artifact({ id: 'wayah-bald', name: 'Wayah Bald' }),
      ],
    })
    expect(list.map((h) => h.id)).toEqual(['wayah-bald'])
  })

  it.each([
    ['not an object', 42],
    ['null', null],
    ['an object with no highlights', {}],
  ])('yields nothing rather than throwing, given %s', (_label, raw) => {
    expect(parseHighlights(raw)).toEqual([])
  })

  it('treats an unattributed highlight as having no club, not a blank one', () => {
    expect(parsed({ club: null }).club).toBeNull()
    expect(parsed({ club: '' }).club).toBeNull()
  })

  it('keeps an empty reviewed date empty rather than inventing one', () => {
    // Today's date here would be a claim nobody made about a row nobody read.
    const bare = parsed({ citations: { [NAMED]: { by: 'OurHike' } } })
    expect(bare.citations[NAMED]).toEqual({ by: 'OurHike', note: '', reviewed: '' })
  })
})

describe('storedHighlights', () => {
  it('reads back what was stored', () => {
    const stored = [parsed()]
    expect(storedHighlights(stored)).toEqual(stored)
  })

  it('is not the artifact parser, which would silently empty the list', () => {
    // The stored shape is the DOMAIN shape (`startMile`); the artifact's is
    // not (`start_mile`). Running the wrong one produces an empty corridor
    // indistinguishable from a release publishing nothing - the exact bug
    // clubSections.ts's storedClubSections exists because of.
    const stored = [parsed()]
    expect(storedHighlights(stored)).toHaveLength(1)
    expect(parseHighlights(stored)).toHaveLength(0)
  })

  it('yields nothing for a store this version cannot read', () => {
    expect(storedHighlights({ nope: true })).toEqual([])
    expect(storedHighlights([{ id: 'x' }])).toEqual([])
  })
})

/**
 * "No blended score", as it reaches a screen.
 *
 * One basis is cited, the strongest, and the others are not shown beside it.
 * Two citations on one card would read as corroboration - two independent
 * sources agreeing - when they are two different questions with one answer
 * between them.
 */
describe('strongestBasis', () => {
  it('cites ATC over our own editorial list', () => {
    expect(strongestBasis(parsed({ bases: [NAMED, PUBLISHED] }))).toBe(PUBLISHED)
  })

  it('does not rank visited above published', () => {
    // It answers a different question - where this app's users sent something
    // - and one it must never be read as answering.
    expect(strongestBasis(parsed({ bases: [VISITED, PUBLISHED] }))).toBe(PUBLISHED)
    expect(BASIS_STRENGTH.indexOf(VISITED)).toBeLessThan(
      BASIS_STRENGTH.indexOf(PUBLISHED),
    )
  })

  it('does not let a basis it has never heard of outrank ATC', () => {
    expect(strongestBasis(parsed({ bases: [PUBLISHED, 'sponsored'] }))).toBe(PUBLISHED)
  })

  it('cites nothing rather than a basis it cannot word', () => {
    expect(strongestBasis(parsed({ bases: ['sponsored'] }))).toBeNull()
  })
})

describe('highlightMiles', () => {
  it('sums every leg, because one walk is one number', () => {
    const loop = parsed({
      legs: [
        { trail: 'AT', start_mile: 1823.4, end_mile: 1825.1 },
        { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
      ],
    })
    expect(highlightMiles(loop)).toBeCloseTo(4.9)
  })
})

describe('highlightsWithin', () => {
  const list = [
    parsed({ id: 'a', legs: [{ trail: 'AT', start_mile: 100, end_mile: 104 }] }),
    parsed({ id: 'b', legs: [{ trail: 'AT', start_mile: 700, end_mile: 709 }] }),
    parsed({ id: 'c', legs: [{ trail: 'AT', start_mile: 400, end_mile: 402 }] }),
  ]

  it('returns what overlaps the window, in mile order', () => {
    expect(highlightsWithin(list, 90, 500).map((h) => h.id)).toEqual(['a', 'c'])
  })

  it('counts a highlight the window merely clips', () => {
    expect(highlightsWithin(list, 703, 705).map((h) => h.id)).toEqual(['b'])
  })

  it('is direction-agnostic, like trailSlice', () => {
    expect(highlightsWithin(list, 500, 90).map((h) => h.id)).toEqual(['a', 'c'])
  })

  it('returns nothing for empty country', () => {
    expect(highlightsWithin(list, 1500, 1600)).toEqual([])
  })
})
