import { describe, it, expect } from 'vitest'
import {
  ascentBetween,
  journalEntries,
  JOURNAL_TYPES,
  MAX_JOURNAL_ENTRIES,
  nextShelter,
} from './todayJournal'

// The journal's honesty rules, pinned: no position means no entries (never a
// ranking from a place nobody is), no direction means nearest-first rather
// than a false "ahead", and the greeting's ascent refuses a window that does
// not cover the walk rather than pricing unmeasured climbs at zero.

const POIS = [
  { id: 'w1', name: 'Sartain Spring', type: 'water', mile: 713.8 },
  { id: 's1', name: 'Bailey Gap Shelter', type: 'shelter', mile: 720.8 },
  { id: 'c1', name: 'Wind Rock Campsite', type: 'campsite', mile: 708.0 },
  { id: 'p1', name: 'War Spur Trailhead', type: 'parking', mile: 714.2 },
  { id: 'v1', name: 'Wind Rock', type: 'viewpoint', mile: 714.9 },
  { id: 'x1', name: 'Unplaced Spring', type: 'water' },
]

describe('journalEntries', () => {
  it('ranks what is ahead, nearest first, for a northbounder', () => {
    const entries = journalEntries(POIS, 712.4, 'NOBO')

    expect(entries.map((e) => e.id)).toEqual(['w1', 's1'])
    expect(entries[0].distanceMi).toBeCloseTo(1.4, 5)
    expect(entries[1].distanceMi).toBeCloseTo(8.4, 5)
  })

  it('ranks the other way for a southbounder', () => {
    const entries = journalEntries(POIS, 712.4, 'SOBO')

    expect(entries.map((e) => e.id)).toEqual(['c1'])
    expect(entries[0].distanceMi).toBeCloseTo(4.4, 5)
  })

  it('ranks nearest in either direction when no direction is settled', () => {
    // "Ahead" is a claim about which way somebody is walking; without a
    // settled direction the section says NEARBY and membership matches.
    const entries = journalEntries(POIS, 712.4, undefined)

    expect(entries.map((e) => e.id)).toEqual(['w1', 'c1', 's1'])
  })

  it('ranks nothing from a position nobody has', () => {
    expect(journalEntries(POIS, undefined, 'NOBO')).toEqual([])
  })

  it('keeps to the journal types - a trailhead is the map’s business', () => {
    const ids = journalEntries(POIS, 712.4, 'NOBO').map((e) => e.id)

    expect(ids).not.toContain('p1')
    expect(ids).not.toContain('v1')
    expect(JOURNAL_TYPES).not.toContain('parking')
  })

  it('drops a POI nothing could place on the trail, rather than guessing', () => {
    expect(journalEntries(POIS, 712.4, 'NOBO').map((e) => e.id)).not.toContain('x1')
  })

  it('caps at one screen’s worth', () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      id: `m${i}`,
      name: `Spring ${i}`,
      type: 'water',
      mile: 713 + i,
    }))

    expect(journalEntries(many, 712.4, 'NOBO')).toHaveLength(MAX_JOURNAL_ENTRIES)
  })
})

describe('nextShelter', () => {
  it('names the first shelter in journal order', () => {
    const entries = journalEntries(POIS, 712.4, 'NOBO')

    expect(nextShelter(entries)?.id).toBe('s1')
  })

  it('names nothing when no shelter is ranked', () => {
    expect(nextShelter(journalEntries(POIS, 712.4, 'SOBO'))).toBeUndefined()
  })
})

describe('ascentBetween', () => {
  const SAMPLES = [
    { mile: 712, elevationFt: 2100 },
    { mile: 713, elevationFt: 2400 },
    { mile: 714, elevationFt: 2200 },
    { mile: 715, elevationFt: 2700 },
  ]

  it('sums the climbs and ignores the descents, like the rule it feeds', () => {
    // +300 then +500; the 200 ft descent buys nothing back - the same
    // no-descent-credit stance lib/naismith.ts documents.
    expect(ascentBetween(SAMPLES, 712, 715)).toBe(800)
  })

  it('counts a southbound walk in its own walk order', () => {
    // Southbound over the same ground: +200 (2200 from 2700? no - walked
    // 715->712: 2700 -> 2200 is descent, 2200 -> 2400 is +200, 2400 -> 2100
    // is descent).
    expect(ascentBetween(SAMPLES, 715, 712)).toBe(200)
  })

  it('refuses a span the samples do not cover, rather than underpricing it', () => {
    // Pricing unmeasured miles at zero ascent would UNDERSTATE the walk -
    // the direction "round toward caution" forbids.
    expect(ascentBetween(SAMPLES, 712, 720)).toBeNull()
    expect(ascentBetween(SAMPLES, 700, 715)).toBeNull()
  })

  it('tolerates a window edge landing between samples', () => {
    expect(ascentBetween(SAMPLES, 712.02, 714.98)).not.toBeNull()
  })

  it('refuses to answer from fewer than two samples', () => {
    expect(ascentBetween([{ mile: 712, elevationFt: 2100 }], 712, 712)).toBeNull()
    expect(ascentBetween([], 712, 715)).toBeNull()
  })
})
