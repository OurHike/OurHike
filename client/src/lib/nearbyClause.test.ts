import { describe, it, expect } from 'vitest'
import { describeNearby, type NearbyPart } from './nearbyClause'

// The sentence a site's anchor says about the parts around it, and the reason
// it is written here at all: the pipeline used to compose it, in metres, for
// everybody (#625). What these assert is that one published set of parts comes
// out as two correct sentences, and that nothing about the wording moved except
// the unit.

const PRIVY: NearbyPart = { phrase: 'a multi-seat moldering privy', distance_ft: 131.2 }
const WATER: NearbyPart = { phrase: 'water', distance_ft: 295.3 }
const CAMPSITE: NearbyPart = { phrase: 'a group campsite', distance_ft: 82.0 }

describe('the sentence naming a site’s parts', () => {
  it('writes the same published parts in whichever units the hiker chose', () => {
    // THE WHOLE POINT. One artifact, two readers, and neither of them reads a
    // number somebody else's unit preference decided - which is what published
    // prose could only ever have offered them.
    const parts = [PRIVY, WATER, CAMPSITE]

    expect(describeNearby(parts, 'imperial')).toBe(
      'Nearby: a multi-seat moldering privy 131 ft away, water 295 ft and a group campsite 82 ft.',
    )
    expect(describeNearby(parts, 'metric')).toBe(
      'Nearby: a multi-seat moldering privy 40 m away, water 90 m and a group campsite 25 m.',
    )
  })

  it('says away once and carries it across the list', () => {
    // Three of them in a row reads as a sentence explaining its own grammar,
    // and "Nearby" has already said it. The pipeline's rule, kept exactly.
    const sentence = describeNearby([PRIVY, WATER, CAMPSITE], 'imperial') ?? ''

    expect(sentence.match(/ away/g)).toHaveLength(1)
    expect(sentence.indexOf(' away')).toBeLessThan(sentence.indexOf('water'))
  })

  it('still says away with one part', () => {
    expect(describeNearby([PRIVY], 'imperial')).toBe(
      'Nearby: a multi-seat moldering privy 131 ft away.',
    )
  })

  it('joins two parts with and, and three with commas and an and', () => {
    // No Oxford comma, matching the pipeline's own `_join` and the app's prose
    // elsewhere. Asserted because this is the half of the wording that crossed
    // languages, and a comma is exactly the kind of thing a port drops.
    expect(describeNearby([PRIVY, WATER], 'imperial')).toBe(
      'Nearby: a multi-seat moldering privy 131 ft away and water 295 ft.',
    )
    expect(describeNearby([PRIVY, WATER, CAMPSITE], 'imperial')).toContain(
      '131 ft away, water 295 ft and a group campsite 82 ft.',
    )
  })

  it('keeps the order the pipeline published and does not re-derive it', () => {
    // NEARBY_ORDER (privy, water, campsite) then distance, decided once in
    // pipeline/lib/poi_description.py. Sorting again here would be a second
    // opinion about which part comes first, and the pin's footer glyphs, the
    // chip strip and this sentence would stop agreeing about one site.
    //
    // So this hands them over in an order the pipeline would never produce and
    // asserts it survives: a client that re-sorted would "fix" this into the
    // canonical order and pass a test that only ever listed them correctly.
    const sentence = describeNearby([CAMPSITE, WATER, PRIVY], 'imperial') ?? ''

    expect(sentence).toBe(
      'Nearby: a group campsite 82 ft away, water 295 ft and a multi-seat moldering privy 131 ft.',
    )
  })

  it('says nothing at all when there is nothing around', () => {
    // Null and not "", so the card renders no paragraph rather than an empty
    // one - a gap in the layout reads as something that failed to load.
    expect(describeNearby([], 'imperial')).toBeNull()
    expect(describeNearby(undefined, 'imperial')).toBeNull()
  })

  it('writes no unit of its own, in either system', () => {
    // Every unit in this sentence comes from lib/units.ts, which is what
    // src/test/unitDisplay.test.ts enforces over the source and what this
    // asserts over the output: the feet sentence contains no metres and the
    // metric one contains no feet. A hand-written " m" here would be the
    // original defect, rebuilt on the phone.
    expect(describeNearby([PRIVY, WATER], 'imperial')).not.toMatch(/\d+ m\b/)
    expect(describeNearby([PRIVY, WATER], 'metric')).not.toMatch(/\d+ ft\b/)
  })
})
