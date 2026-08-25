// The leave-with-someone card's text (#1008, frame D6). The load-bearing
// assertions are the negative ones: nothing on this card is a time the app
// computed, because the person holding it decides when to worry from it.

import { describe, expect, it } from 'vitest'

import type { DayHike } from './dayHikes'
import { dayHikePlanText, routeLine } from './dayHikePlanText'

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

const EMPTY = { startingFrom: '', car: '', notBackBy: '' }

describe('the card', () => {
  it('leads with the name and the date, in the hiker-voice spelling', () => {
    const text = dayHikePlanText(hike(), 6.2, 'imperial', EMPTY)
    expect(text.split('\n')[0]).toBe('Pine Meadow loop · sat 12 sep')
  })

  it('an undated hike gets the name alone - no invented day', () => {
    const text = dayHikePlanText(hike({ date: null }), 6.2, 'imperial', EMPTY)
    expect(text.split('\n')[0]).toBe('Pine Meadow loop')
  })

  it('prints the route in walk order and says the loop in words', () => {
    const text = dayHikePlanText(hike(), 6.2, 'imperial', EMPTY)
    expect(text).toContain(
      'Route: Reeves Meadow Trail → Pine Meadow Trail → Seven Hills Trail → back to the start',
    )
  })

  it('prints trail miles and says that is what they are', () => {
    const text = dayHikePlanText(hike(), 6.2, 'imperial', EMPTY)
    expect(text).toContain('How far: 6.2 mi on marked trails')
  })

  it('carries the typed lines verbatim, and the not-back-by sentence', () => {
    const text = dayHikePlanText(hike(), 6.2, 'imperial', {
      startingFrom: 'Reeves Meadow Visitor Center',
      car: 'grey Subaru, by the kiosk',
      notBackBy: '6:00 pm',
    })
    expect(text).toContain('Starting from: Reeves Meadow Visitor Center')
    expect(text).toContain('Car: grey Subaru, by the kiosk')
    expect(text).toContain("If I'm not back by 6:00 pm, something's wrong.")
  })

  it('omits an empty field entirely - absent means the hiker did not say', () => {
    const text = dayHikePlanText(hike(), 6.2, 'imperial', EMPTY)
    expect(text).not.toContain('Starting from')
    expect(text).not.toContain('Car:')
    expect(text).not.toContain('not back by')
  })

  it('NEVER computes a time: no ≈, no clock the hiker did not type', () => {
    const text = dayHikePlanText(hike(), 6.2, 'imperial', EMPTY)
    expect(text).not.toContain('≈')
    expect(text).not.toMatch(/\d{1,2}:\d{2}/)
    expect(text).not.toMatch(/walking/i)
  })

  it('says the card does not track anyone', () => {
    const text = dayHikePlanText(hike(), 6.2, 'imperial', EMPTY)
    expect(text).toContain('It does not track me.')
  })

  it('converts the distance for a metric reader', () => {
    const text = dayHikePlanText(hike(), 6.2, 'metric', EMPTY)
    expect(text).toContain('10.0 km on marked trails')
  })
})

describe('routeLine', () => {
  it('collapses an out-and-back to the shape, not the bookkeeping', () => {
    const outAndBack = hike({
      looped: false,
      figures: {
        miles: 4,
        legs: [
          { name: 'Pine Meadow Trail', source: null, blaze_color: null, miles: 2 },
          { name: 'Pine Meadow Trail', source: null, blaze_color: null, miles: 2 },
        ],
      },
    })
    expect(routeLine(outAndBack)).toBe('Pine Meadow Trail')
  })

  it('names an unnamed leg honestly and answers null with no legs at all', () => {
    const unnamed = hike({
      looped: false,
      figures: {
        miles: 2,
        legs: [{ name: null, source: null, blaze_color: null, miles: 2 }],
      },
    })
    expect(routeLine(unnamed)).toBe('an unnamed trail')
    expect(routeLine(hike({ figures: { miles: 2, legs: [] } }))).toBeNull()
  })
})
