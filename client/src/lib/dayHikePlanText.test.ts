// The leave-with-someone card's text (#1008, frame D6). The load-bearing
// assertions are the negative ones: nothing on this card is a time the app
// computed, and no figure on it is stated more confidently than the screen
// that handed it over - the person holding this decides when to worry.

import { describe, expect, it } from 'vitest'

import type { DayHike } from './dayHikes'
import { dayHikePlanText, routeLine, type PlanTextFigures } from './dayHikePlanText'

function hike(overrides: Partial<DayHike> = {}): DayHike {
  return {
    id: 'hike-1',
    name: 'Pine Meadow loop',
    date: '2026-09-12',
    segments: [
      [
        { coord: [-74.095, 41.25], poiId: null },
        { coord: [-74.085, 41.25], poiId: null },
      ],
    ],
    figures: {
      miles: 6.2,
      legs: [
        {
          name: 'Reeves Meadow Trail',
          source: 'nynjtc',
          blaze_color: 'white',
          miles: 1.1,
        },
        { name: 'Pine Meadow Trail', source: 'nynjtc', blaze_color: 'red', miles: 2.4 },
        { name: 'Seven Hills Trail', source: 'nynjtc', blaze_color: 'blue', miles: 2.7 },
      ],
    },
    looped: true,
    recorded: 'planned',
    ...overrides,
  }
}

function figures(overrides: Partial<PlanTextFigures> = {}): PlanTextFigures {
  return {
    miles: 6.2,
    legs: [
      { name: 'Reeves Meadow Trail' },
      { name: 'Pine Meadow Trail' },
      { name: 'Seven Hills Trail' },
    ],
    fromCache: false,
    gapMiles: 0,
    stretches: 1,
    ...overrides,
  }
}

const EMPTY = { startingFrom: '', car: '', notBackBy: '' }
const TODAY = '2026-09-12'

describe('the card', () => {
  it('leads with the name and the date, carrying the year', () => {
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, TODAY)
    expect(text.split('\n')[0]).toBe('Pine Meadow loop · sat 12 sep 2026')
  })

  it('names both days when the plan date is not the day it was written', () => {
    // A card written a week after the date it was planned for must not pass
    // for today's walk - the reader is building a timeline for worry from it.
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, '2026-09-19')
    expect(text.split('\n')[0]).toBe(
      'Pine Meadow loop · planned for sat 12 sep 2026, written sat 19 sep 2026',
    )
  })

  it('an undated hike is stamped with the day the card was written', () => {
    const text = dayHikePlanText(
      hike({ date: null }),
      figures(),
      'imperial',
      EMPTY,
      TODAY,
    )
    expect(text.split('\n')[0]).toBe('Pine Meadow loop · written sat 12 sep 2026')
  })

  it('prints the route in walk order and says the loop in words', () => {
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, TODAY)
    expect(text).toContain(
      'Route: Reeves Meadow Trail → Pine Meadow Trail → Seven Hills Trail → back to the start',
    )
  })

  it('prints trail miles and says that is what they are', () => {
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, TODAY)
    expect(text).toContain('How far: 6.2 mi on marked trails')
  })

  it('carries the typed lines verbatim, and the not-back-by sentence', () => {
    const text = dayHikePlanText(
      hike(),
      figures(),
      'imperial',
      {
        startingFrom: 'Reeves Meadow Visitor Center',
        car: 'grey Subaru, by the kiosk',
        notBackBy: '6:00 pm',
      },
      TODAY,
    )
    expect(text).toContain('Starting from: Reeves Meadow Visitor Center')
    expect(text).toContain('Car: grey Subaru, by the kiosk')
    expect(text).toContain("If I'm not back by 6:00 pm, something's wrong.")
  })

  it('omits an empty field entirely - absent means the hiker did not say', () => {
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, TODAY)
    expect(text).not.toContain('Starting from')
    expect(text).not.toContain('Car:')
    expect(text).not.toContain('not back by')
  })

  it('NEVER computes a time: no ≈, no clock the hiker did not type', () => {
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, TODAY)
    expect(text).not.toContain('≈')
    expect(text).not.toMatch(/\d{1,2}:\d{2}/)
    expect(text).not.toMatch(/walking/i)
  })

  it('says the card does not track anyone', () => {
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, TODAY)
    expect(text).toContain('It does not track me.')
  })

  it('converts the distance for a metric reader', () => {
    const text = dayHikePlanText(hike(), figures(), 'metric', EMPTY, TODAY)
    expect(text).toContain('10.0 km on marked trails')
  })
})

describe('what the figures are allowed to claim', () => {
  it('hedges a cached figure, because the screen behind it does', () => {
    // The card refuses to stand behind these numbers when it cannot resolve
    // the walk; handing the friend the number without the sentence would be
    // the display outrunning its source on the one safety artifact.
    const text = dayHikePlanText(
      hike(),
      figures({ fromCache: true }),
      'imperial',
      EMPTY,
      TODAY,
    )
    expect(text).toContain(
      'How far: 6.2 mi on marked trails (measured when this was planned, not re-checked since)',
    )
  })

  it('states a live figure flatly - a hedge on everything is a hedge on nothing', () => {
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, TODAY)
    expect(text).not.toContain('not re-checked since')
  })

  it('names ground with no trail under it rather than folding it into the total', () => {
    // The part of a day most likely to lose somebody, on the artifact a
    // searcher would be handed.
    const text = dayHikePlanText(
      hike({ looped: false }),
      figures({ miles: 5, gapMiles: 1.2, stretches: 2 }),
      'imperial',
      EMPTY,
      TODAY,
    )
    expect(text).toContain('How far: 5.0 mi on marked trails')
    expect(text).toContain(
      "Plus 1.2 mi with no trail under it, between the two stretches of this walk — I'll be crossing that on my own.",
    )
  })

  it('counts the stretches when there are more than two', () => {
    const text = dayHikePlanText(
      hike({ looped: false }),
      figures({ gapMiles: 2, stretches: 3 }),
      'imperial',
      EMPTY,
      TODAY,
    )
    expect(text).toContain('between the 3 stretches of this walk')
  })

  it('says nothing about gaps on a walk that has none', () => {
    const text = dayHikePlanText(hike(), figures(), 'imperial', EMPTY, TODAY)
    expect(text).not.toContain('no trail under it')
  })
})

describe('routeLine', () => {
  it('collapses an out-and-back to the shape, not the bookkeeping', () => {
    expect(
      routeLine([{ name: 'Pine Meadow Trail' }, { name: 'Pine Meadow Trail' }], false),
    ).toBe('Pine Meadow Trail')
  })

  it('names an unnamed leg honestly and answers null with no legs at all', () => {
    expect(routeLine([{ name: null }], false)).toBe('an unnamed trail')
    expect(routeLine([], false)).toBeNull()
  })

  it('takes the legs it is handed, so the caller can pass the live ones', () => {
    // The defect this shape prevents: naming the trails a republished graph
    // no longer routes through, beside a mileage from the route that
    // replaced them - two graphs' answers printed as one walk.
    expect(routeLine([{ name: 'Kakiat Trail' }], false)).toBe('Kakiat Trail')
  })
})
