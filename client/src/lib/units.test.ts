import { describe, it, expect } from 'vitest'
import {
  formatDistance,
  formatElevation,
  formatShortDistance,
  unitSystemLabel,
} from './units'

// Two things are being held here and they pull in opposite directions.
//
// The imperial half must be a NO-OP. Every string in this app was imperial
// before this module existed, and each of those formats was a reviewed
// decision - the spur's two decimals under a tenth of a mile, the whole miles
// on a 398-mile advisory, the grouped thousands on an elevation. A units
// module that quietly re-rounds them would ship a copy change nobody asked for
// under cover of a settings toggle, and the imperial hiker is every hiker
// today (lib/userPreferences.ts defaults to it).
//
// The metric half must be what somebody would SAY. That is not the same as
// the imperial number converted: "0.08 km each way" is arithmetically correct
// and is not a sentence, which is why the metre cutover below is tested as a
// rule rather than as a spot check.

describe('formatElevation', () => {
  it('leaves the imperial figures exactly as the app already printed them', () => {
    // The ribbon's high mark and a Blood Mountain-sized climb, both grouped.
    expect(formatElevation(6_643, 'imperial')).toBe('6,643 ft')
    expect(formatElevation(1_400, 'imperial')).toBe('1,400 ft')
  })

  it('converts to whole metres', () => {
    // Clingmans Dome, the high point of the AT.
    expect(formatElevation(6_643, 'metric')).toBe('2,025 m')
    expect(formatElevation(1_400, 'metric')).toBe('427 m')
  })

  it('rounds rather than truncating, in both systems', () => {
    expect(formatElevation(1_240.6, 'imperial')).toBe('1,241 ft')
    // 300 ft is 91.44 m.
    expect(formatElevation(300, 'metric')).toBe('91 m')
  })

  it('says nothing about a climb of nothing, in either system', () => {
    expect(formatElevation(0, 'imperial')).toBe('0 ft')
    expect(formatElevation(0, 'metric')).toBe('0 m')
  })
})

describe('formatDistance', () => {
  it('leaves the imperial figures exactly as the app already printed them', () => {
    // closureBanner's "2.1 mi ahead", and the whole miles a broad advisory gets.
    expect(formatDistance(2.1, 'imperial')).toBe('2.1 mi')
    expect(formatDistance(398.4, 'imperial', 'whole')).toBe('398 mi')
    // The spur rule: two decimals only where one would round the fact away.
    expect(formatDistance(0.03, 'imperial', 'fine')).toBe('0.03 mi')
    expect(formatDistance(0.2, 'imperial', 'fine')).toBe('0.2 mi')
  })

  it('converts to kilometres at a hiker-sized distance', () => {
    expect(formatDistance(2.1, 'metric')).toBe('3.4 km')
    expect(formatDistance(398.4, 'metric', 'whole')).toBe('641 km')
  })

  it('drops to metres below a kilometre rather than printing a fraction of one', () => {
    // The median blue-blazed spur is 385 ft - 0.073 mi, 117 m.
    expect(formatDistance(0.073, 'metric', 'fine')).toBe('120 m')
    expect(formatDistance(0.3, 'metric')).toBe('480 m')
  })

  it('switches to kilometres exactly at one, and not before', () => {
    // 0.62 mi is 998 m; a mile more than clears it.
    expect(formatDistance(0.62, 'metric')).toBe('1,000 m')
    expect(formatDistance(0.63, 'metric')).toBe('1.0 km')
  })

  it('keeps a whole-mile span in whole kilometres, never in metres', () => {
    // `whole` is for spans too big for a decimal to be honest about. A span
    // that small is not one, and "800 m of trail" under a rule that exists for
    // 398-mile advisories would be a category error.
    expect(formatDistance(0.5, 'metric', 'whole')).toBe('1 km')
  })

  it('rounds metres to the nearest ten, not to the metre', () => {
    // 0.05 mi is 80.47 m. A bare "80" is the honest end of what a published
    // spur length is worth; "80.5" would claim a survey.
    expect(formatDistance(0.05, 'metric', 'fine')).toBe('80 m')
  })

  it('drops a trailing zero only where the caller asked it to', () => {
    // What HikePicker's readout does with two typed mileposts, and what the
    // banner deliberately does not: a figure that re-renders as somebody walks
    // keeps its width.
    expect(formatDistance(42, 'imperial', 'trimmed')).toBe('42 mi')
    expect(formatDistance(42.5, 'imperial', 'trimmed')).toBe('42.5 mi')
    expect(formatDistance(42, 'imperial')).toBe('42.0 mi')
    expect(formatDistance(42, 'metric', 'trimmed')).toBe('67.6 km')
    expect(formatDistance(100, 'metric', 'trimmed')).toBe('160.9 km')
  })

  it('states a distance of zero in the units asked for', () => {
    expect(formatDistance(0, 'imperial')).toBe('0.0 mi')
    expect(formatDistance(0, 'metric')).toBe('0 m')
  })
})

describe('formatShortDistance', () => {
  it('reads in feet or metres, never in miles', () => {
    // The wrong-way cue: how far off the blazes somebody has wandered.
    expect(formatShortDistance(240, 'imperial')).toBe('240 ft')
    expect(formatShortDistance(240, 'metric')).toBe('73 m')
  })
})

describe('unitSystemLabel', () => {
  it('names the unit a hiker reads, not the customs schedule it belongs to', () => {
    expect(unitSystemLabel('imperial')).toBe('Feet')
    expect(unitSystemLabel('metric')).toBe('Metres')
  })
})

describe('the module as a whole', () => {
  it('never returns a bare number - a caller cannot store what it hands back', () => {
    // The storage rule stated as a property: every function here returns a
    // string with a unit in it, so a converted value that reached IndexedDB
    // would have to have been re-parsed on purpose.
    const outputs = [
      formatElevation(1_000, 'metric'),
      formatDistance(1, 'metric'),
      formatDistance(0.01, 'metric', 'fine'),
      formatShortDistance(100, 'metric'),
    ]
    for (const output of outputs) {
      expect(output).toMatch(/^[\d,.]+ (m|km)$/)
    }
  })
})
