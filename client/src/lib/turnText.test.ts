// What a turn is called out loud (#1041, frames `D9` and `D10`).
//
// The sentences are the product here, so they are tested as sentences. Two
// of them carry a claim that has to keep being weaker than it looks: an arm
// whose side nobody could read must not acquire one, and the blaze advice
// must stay a rule of thumb rather than a measurement.

import { describe, expect, it } from 'vitest'

import type { TurnArm } from './dayHikeTurns'
import {
  armBlaze,
  blazeCheckLine,
  cameFromLine,
  otherArmLine,
  turnHeading,
  turnSummary,
} from './turnText'

const SEVEN_HILLS: TurnArm = {
  name: 'Seven Hills Trail',
  blaze_color: 'Blue',
  source: 'nynjtc',
  side: 'left',
  bearingDeg: 0,
}

describe('turnHeading and turnSummary', () => {
  it('lead with the direction and name the trail', () => {
    expect(turnHeading(SEVEN_HILLS)).toBe('Turn left onto Seven Hills Trail')
    expect(turnSummary(SEVEN_HILLS)).toBe('turn left onto Seven Hills Trail')
  })

  it('drop the direction rather than invent one', () => {
    // An edge with no published vertices - see TurnArm.side. Which trail to
    // take is still known and still worth saying; which way it goes is not.
    const noSide = { ...SEVEN_HILLS, side: null, bearingDeg: null }
    expect(turnHeading(noSide)).toBe('Onto Seven Hills Trail')
    expect(turnSummary(noSide)).toBe('onto Seven Hills Trail')
  })

  it('name an unnamed trail as one, rather than dropping the arm', () => {
    // Not "Unknown trail", which reads as a data fault, and not silence - the
    // arm is really there and a hiker at the fork will count it.
    expect(turnHeading({ ...SEVEN_HILLS, name: null })).toBe(
      'Turn left onto an unnamed trail',
    )
  })
})

describe('the arms that are not the route', () => {
  it('say where each goes AND that it is not yours', () => {
    expect(
      otherArmLine({ ...SEVEN_HILLS, name: 'Pine Meadow Trail', side: 'straight' }),
    ).toBe('Straight on is Pine Meadow Trail, blue blaze — not your route')
  })

  it('mark the way you came as the way you came', () => {
    expect(cameFromLine({ ...SEVEN_HILLS, name: 'Reeves Meadow', side: 'back' })).toBe(
      'Behind you is Reeves Meadow, blue blaze — the way you came',
    )
  })

  it('still place an arm whose direction is unknown', () => {
    expect(otherArmLine({ ...SEVEN_HILLS, side: null })).toBe(
      'Also here is Seven Hills Trail, blue blaze — not your route',
    )
  })
})

describe('armBlaze', () => {
  it('keeps confirmed-unblazed apart from nobody-checked', () => {
    // lib/blaze.ts's contract, which the tapped-line sheet already prints:
    // "None" is a confirmed fact and "Unknown" is a value that failed to
    // decode, and "Unblazed" over the second would be a claim nobody made.
    expect(armBlaze({ ...SEVEN_HILLS, blaze_color: 'None' })).toBe('Unblazed')
    expect(armBlaze({ ...SEVEN_HILLS, blaze_color: 'Unknown' })).toBe(
      'Blaze not recorded',
    )
    expect(armBlaze({ ...SEVEN_HILLS, blaze_color: null })).toBe('Blaze not recorded')
  })
})

describe('blazeCheckLine', () => {
  it('names the colour to look for, and claims no distance', () => {
    const line = blazeCheckLine(SEVEN_HILLS)
    expect(line).toContain('blue')
    // Frame `D10`'s "about 80 ft along, on the left" is deliberately absent:
    // nothing in this repository knows where a blaze is painted, so a
    // distance here would be a measurement nobody made.
    expect(line).not.toMatch(/\d/)
  })

  it('falls back to a colourless check where there is no colour to name', () => {
    const line = blazeCheckLine({ ...SEVEN_HILLS, blaze_color: null })
    expect(line).toContain('change colour')
    expect(line).not.toMatch(/\d/)
  })
})
