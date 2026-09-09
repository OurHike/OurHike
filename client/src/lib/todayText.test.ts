import { describe, it, expect } from 'vitest'
import {
  formatTodayEyebrow,
  greetingLead,
  splitPosition,
  todayGreeting,
} from './todayText'

describe('formatTodayEyebrow', () => {
  it('reads weekday, day, month, uppercased', () => {
    expect(formatTodayEyebrow(new Date(2026, 7, 26))).toBe('WED 26 AUG')
  })

  it('answers the same day from the same clock and a later one alike (#1324)', () => {
    // The memo is a module-level single entry, so the thing worth pinning is
    // that it is keyed on the DAY and not on the Date instance: useClock hands
    // out a fresh instance every minute, and an instance key would recompute
    // 1,439 times a day for an answer that changes once.
    expect(formatTodayEyebrow(new Date(2026, 7, 26, 6, 5))).toBe('WED 26 AUG')
    expect(formatTodayEyebrow(new Date(2026, 7, 26, 23, 59))).toBe('WED 26 AUG')
  })

  it('crosses midnight rather than serving yesterday out of the cache', () => {
    // The failure a one-entry cache invites, and the only one that would reach
    // a hiker: an app left open overnight showing the wrong day.
    expect(formatTodayEyebrow(new Date(2026, 7, 26, 23, 59))).toBe('WED 26 AUG')
    expect(formatTodayEyebrow(new Date(2026, 7, 27, 0, 1))).toBe('THU 27 AUG')
  })

  it('does not confuse the same date in a different month or year', () => {
    // The key is year-month-day rather than the day number, which a shorter
    // key would have got wrong exactly twelve times a year.
    expect(formatTodayEyebrow(new Date(2026, 7, 26))).toBe('WED 26 AUG')
    expect(formatTodayEyebrow(new Date(2026, 8, 26))).toBe('SAT 26 SEP')
    expect(formatTodayEyebrow(new Date(2027, 8, 26))).toBe('SUN 26 SEP')
  })
})

describe('splitPosition', () => {
  // Parsed from positionLine's own pinned format rather than recomputed -
  // the readout and the header must not hold two opinions about where the
  // hiker is.
  it('splits the located line into the big number and its unit', () => {
    expect(splitPosition('mi 1,407.2 · NOBO')).toEqual({
      kind: 'mile',
      mile: '1,407.2',
      unit: 'mi · NOBO',
    })
  })

  it('splits a located line with no direction yet', () => {
    expect(splitPosition('mi 8.0')).toEqual({ kind: 'mile', mile: '8.0', unit: 'mi' })
  })

  it('passes every non-mile state through as the sentence it is', () => {
    for (const sentence of [
      'Location is off',
      'No GPS signal',
      'Looking for GPS…',
      'Off the trail',
      'No trail data',
      '2.4 mi in · 3.8 mi to go',
    ]) {
      expect(splitPosition(sentence)).toEqual({ kind: 'sentence', sentence })
    }
  })
})

describe('todayGreeting', () => {
  const MORNING = new Date(2026, 7, 26, 7, 12)

  it('greets by the clock', () => {
    expect(greetingLead(new Date(2026, 7, 26, 7))).toBe('Good morning.')
    expect(greetingLead(new Date(2026, 7, 26, 14))).toBe('Good afternoon.')
    expect(greetingLead(new Date(2026, 7, 26, 19))).toBe('Good evening.')
    expect(greetingLead(new Date(2026, 7, 26, 3))).toBe('Good evening.')
  })

  it('says the distance and the walking time when both are known', () => {
    expect(
      todayGreeting({
        now: MORNING,
        destination: { name: 'Bailey Gap Shelter', distanceMi: 8.4 },
        estimate: '≈3h 40m',
      }),
    ).toBe('Good morning. Bailey Gap Shelter is 8.4 miles ahead — ≈3h 40m of walking.')
  })

  it('never renders an arrival clock, whatever the inputs', () => {
    // The prototype wrote "you'll be there around 4:40"; lib/naismith.ts's
    // rule ("never shown as an arrival clock") wins, recorded on #1054.
    const line = todayGreeting({
      now: MORNING,
      destination: { name: 'Bailey Gap Shelter', distanceMi: 8.4 },
      estimate: '≈3h 40m',
    })

    expect(line).not.toMatch(/\d{1,2}:\d{2}/)
    expect(line).not.toMatch(/[ap]\.?m\.?\b/i)
  })

  it('says the distance alone when the time is not measurable', () => {
    expect(
      todayGreeting({
        now: MORNING,
        destination: { name: 'Bailey Gap Shelter', distanceMi: 8.4 },
      }),
    ).toBe('Good morning. Bailey Gap Shelter is 8.4 miles ahead.')
  })

  it('greets and stops when nothing ahead is rankable', () => {
    expect(todayGreeting({ now: MORNING })).toBe('Good morning.')
  })

  it('says mile, singular, at exactly one', () => {
    expect(
      todayGreeting({
        now: MORNING,
        destination: { name: 'Bailey Gap Shelter', distanceMi: 1.0 },
      }),
    ).toBe('Good morning. Bailey Gap Shelter is 1.0 mile ahead.')
  })
})
