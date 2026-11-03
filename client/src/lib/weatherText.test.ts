import { describe, expect, it } from 'vitest'
import {
  ageLine,
  alertTimesText,
  clockText,
  hourText,
  quietWarningsLine,
  whenText,
} from './weatherText'
import type { WeatherAlert } from './weatherForecast'

// The sentences WEATHER.md §5 drew. Tests run in UTC.

const NOW = new Date('2026-09-30T13:30Z')

describe('clock and hour text', () => {
  it('writes the clock lower case, as the approved drawing does: 4:00 am, 12:00 pm', () => {
    expect(clockText(new Date('2026-09-30T04:00Z'))).toBe('4:00 am')
    expect(clockText(new Date('2026-09-30T12:00Z'))).toBe('12:00 pm')
  })

  it('writes the strip hour without minutes: 10 am, 12 pm', () => {
    expect(hourText(new Date('2026-09-30T10:00Z'))).toBe('10 am')
    expect(hourText(new Date('2026-09-30T12:00Z'))).toBe('12 pm')
  })

  it('says yesterday for yesterday and a weekday before that', () => {
    expect(whenText(new Date('2026-09-29T17:40Z'), NOW)).toBe('yesterday 5:40 pm')
    expect(whenText(new Date('2026-09-27T17:40Z'), NOW)).toBe('Sun 5:40 pm')
  })
})

describe('ageLine', () => {
  const cycle = new Date('2026-09-30T08:00Z')

  it('counts a live check in hours once it is an hour old', () => {
    expect(ageLine(cycle, new Date('2026-09-30T11:10Z'), true, NOW)).toBe(
      'Forecast from 8:00 am · checked 2 h ago',
    )
  })

  it('says just now for a check under a minute old', () => {
    expect(ageLine(cycle, new Date('2026-09-30T13:29:30Z'), true, NOW)).toBe(
      'Forecast from 8:00 am · checked just now',
    )
  })
})

describe('quietWarningsLine', () => {
  it('admits the phone has never had the NWS list, rather than reading as all clear', () => {
    expect(quietWarningsLine(null, true, NOW).title).toBe(
      'No word on weather warnings on this phone yet',
    )
  })
})

describe('alertTimesText', () => {
  const alert: WeatherAlert = {
    id: 'x',
    event: 'Winter Storm Watch',
    headline: null,
    description: null,
    instruction: null,
    senderName: 'NWS Gray ME',
    onset: new Date('2026-10-02T18:00Z'),
    until: new Date('2026-10-03T12:00Z'),
  }

  it('says when an alert that has not started yet starts, as well as when it ends', () => {
    expect(alertTimesText(alert, NOW)).toBe('from Fri 6:00 pm until Sat 12:00 pm')
  })

  it('says nothing about an end NWS did not give', () => {
    expect(alertTimesText({ ...alert, onset: null, until: null }, NOW)).toBeNull()
  })
})
