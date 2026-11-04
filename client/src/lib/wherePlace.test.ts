import { describe, expect, it } from 'vitest'
import { asksWhere, readTagPlace, whereOptions, TRAIL_STATES } from './wherePlace'
import { placeWords } from './challengeText'
import { ATC_CHALLENGE } from './challenges.fixtures'

const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

// features/CHALLENGES_BLAZE_CARD.md, hard requirement 2: "Where did it
// happen?" only when it can mean something.
describe('when earning an item asks where it happened (#1963)', () => {
  it('never asks for a gps tag - the walk is the place', () => {
    for (const entry of ATC_CHALLENGE.items) expect(asksWhere(entry, 'gps')).toBe(false)
  })

  it('never asks for an at-home item the reviewer marked off the trail', () => {
    expect(item('trivia-quiz').match).toEqual({ kind: 'self_report', onTrail: false })
    expect(asksWhere(item('trivia-quiz'), 'hand')).toBe(false)
  })

  it('asks for an at-home item the ATC’s own wording puts on the trail', () => {
    expect(item('white-blaze-photo').match).toEqual({
      kind: 'self_report',
      onTrail: true,
    })
    expect(asksWhere(item('white-blaze-photo'), 'hand')).toBe(true)
  })

  it('never asks for a named place - the place is the answer', () => {
    expect(asksWhere(item('mcafee-knob'), 'hand')).toBe(false)
    expect(asksWhere(item('virginia-triple-crown'), 'hand')).toBe(false)
  })

  it('asks which one for "any shelter" earned by hand', () => {
    expect(asksWhere(item('shelter-logbook'), 'hand')).toBe(true)
  })
})

describe('the Where sheet’s options', () => {
  it('offers Here only with a fix inside the corridor, and opens on it', () => {
    const options = whereOptions({ fixMile: 714.9, todayRanges: [] })
    expect(options.here).toEqual({ mile: 714.9 })
    expect(options.initial).toBe('here')
  })

  it('opens on "On the trail, somewhere" with no fix, and never asks for location', () => {
    const options = whereOptions({ fixMile: null, todayRanges: [] })
    expect(options.here).toBeNull()
    expect(options.walked).toBeNull()
    expect(options.initial).toBe('state')
  })

  it('offers today’s walk as the day’s whole extent, intervals merged and unordered', () => {
    const options = whereOptions({
      fixMile: null,
      todayRanges: [
        { startMile: 712, endMile: 716 },
        { startMile: 700.5, endMile: 703 },
      ],
    })
    expect(options.walked).toEqual({ fromMile: 700.5, toMile: 716 })
  })

  it('lists the fourteen states south to north, codes only', () => {
    expect(TRAIL_STATES.map((state) => state.code)).toEqual([
      'GA',
      'NC',
      'TN',
      'VA',
      'WV',
      'MD',
      'PA',
      'NJ',
      'NY',
      'CT',
      'MA',
      'VT',
      'NH',
      'ME',
    ])
    expect(JSON.stringify(TRAIL_STATES)).not.toMatch(/mile/i)
  })
})

describe('a stored place', () => {
  it('reads each kind back, and drops a malformed one rather than throwing', () => {
    expect(readTagPlace({ kind: 'here', mile: 714.9 })).toEqual({
      kind: 'here',
      mile: 714.9,
    })
    expect(readTagPlace({ kind: 'state', state: 'VA' })).toEqual({
      kind: 'state',
      state: 'VA',
    })
    expect(readTagPlace({ kind: 'poi', poi: 'x', name: 'X' })).toEqual({
      kind: 'poi',
      poi: 'x',
      name: 'X',
      mile: null,
    })
    expect(readTagPlace({ kind: 'off' })).toEqual({ kind: 'off' })
    expect(readTagPlace({ kind: 'state', state: 'ZZ' })).toBeNull()
    expect(readTagPlace({ kind: 'here' })).toBeNull()
    expect(readTagPlace('Virginia')).toBeNull()
  })

  it('prints as a mile, a day, a place, a state or not on the trail', () => {
    expect(placeWords({ kind: 'here', mile: 714.9 })).toBe('mi 714.9 · here')
    expect(placeWords({ kind: 'walked', fromMile: 710, toMile: 716 })).toBe(
      'mi 710.0 – mi 716.0 · walked today',
    )
    expect(
      placeWords({ kind: 'poi', poi: 'x', name: 'Campbell Shelter', mile: 713 }),
    ).toBe('Campbell Shelter · mi 713.0')
    expect(placeWords({ kind: 'state', state: 'VA' })).toBe('On the trail in Virginia')
    expect(placeWords({ kind: 'off' })).toBe('Not on the trail')
  })
})
