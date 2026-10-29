import { beforeEach, describe, expect, it } from 'vitest'
import {
  ACTIVE_DAYS_KEY,
  activeDaysThisYear,
  daysIncludingToday,
  localDate,
  recordActiveDay,
} from './activeDays'

// The day count the support ask waits on (#1876): distinct local dates in a
// calendar year, on this phone only.

beforeEach(() => localStorage.clear())

const at = (iso: string) => new Date(iso)

describe('counting the days a hiker used OurHike this year', () => {
  it('counts a day once, however many times the app opens that day', () => {
    expect(recordActiveDay(at('2026-06-01T08:00:00'))).toBe(1)
    expect(recordActiveDay(at('2026-06-01T19:30:00'))).toBe(1)
    expect(recordActiveDay(at('2026-06-02T07:00:00'))).toBe(2)
  })

  it('says at launch what today will make the count, before the first tap records it', () => {
    for (const day of ['01', '03', '09', '14'])
      recordActiveDay(at(`2026-07-${day}T12:00:00`))

    expect(daysIncludingToday(at('2026-07-20T06:00:00'))).toBe(5)
    expect(daysIncludingToday(at('2026-07-14T18:00:00'))).toBe(4)
    expect(daysIncludingToday(at('2027-01-02T06:00:00'))).toBe(1)
  })

  it('reaches five on the fifth distinct day, not the fifth launch', () => {
    for (const day of ['01', '01', '03', '03', '09', '14']) {
      recordActiveDay(at(`2026-07-${day}T12:00:00`))
    }
    expect(activeDaysThisYear(at('2026-07-14T13:00:00'))).toBe(4)
    expect(recordActiveDay(at('2026-07-20T12:00:00'))).toBe(5)
  })

  it('starts again at one on the first day of a new year', () => {
    recordActiveDay(at('2026-12-30T12:00:00'))
    recordActiveDay(at('2026-12-31T12:00:00'))
    expect(activeDaysThisYear(at('2027-01-01T09:00:00'))).toBe(0)
    expect(recordActiveDay(at('2027-01-01T09:00:00'))).toBe(1)
  })

  it('adds nothing when the clock is set back to a day already counted', () => {
    recordActiveDay(at('2026-05-10T12:00:00'))
    recordActiveDay(at('2026-05-12T12:00:00'))
    expect(recordActiveDay(at('2026-05-11T12:00:00'))).toBe(2)
  })

  it('reads a record it cannot parse as no days, so the ask can only come late', () => {
    localStorage.setItem(ACTIVE_DAYS_KEY, '{"year":"2026"}')
    expect(activeDaysThisYear(at('2026-05-10T12:00:00'))).toBe(0)
  })

  it('names the day by the phone’s own calendar, not UTC', () => {
    expect(localDate(new Date(2026, 0, 9, 23, 30))).toBe('2026-01-09')
  })
})
