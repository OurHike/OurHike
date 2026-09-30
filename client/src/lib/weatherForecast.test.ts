import { describe, expect, it } from 'vitest'
import {
  HOURLY_TRUST_HOURS,
  alertsForSquare,
  forecastForSquare,
  forecastView,
  parseWeatherAlerts,
  parseWeatherCell,
  skyCover,
  type SquareForecast,
} from './weatherForecast'
import { weatherCellDocument } from '../../preview-shots/fixtures/weather.mjs'

// The forecast is preview-shots/fixtures/weather.mjs's: the Lakes of the
// Clouds square, (563, 2073), from NOAA's 08Z run of 2026-09-30 as UA
// published it, laid back onto that run's own times here. Tests run in UTC
// (vite.config.ts), so "today" is the UTC date; 13:30Z is 9:30 am in New
// Hampshire.

const SQUARE: [number, number] = [563, 2073]
const CYCLE = new Date('2026-09-30T08:00Z')

type Field = { times: string[]; values: (number | null)[][] }

function cellDocument(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    ...weatherCellDocument({ cycle: CYCLE, squares: [SQUARE, [563, 2074]] }),
    ...overrides,
  }
}

function fieldsOf(document: Record<string, unknown>): Record<string, Field> {
  return document.fields as Record<string, Field>
}

function lakesForecast(document = cellDocument()): SquareForecast {
  const cell = parseWeatherCell(document)
  if (cell === null) throw new Error('fixture did not parse')
  const forecast = forecastForSquare(cell, SQUARE)
  if (forecast === null) throw new Error('fixture square missing')
  return forecast
}

describe('parseWeatherCell', () => {
  it('reads the cell file export_weather.py writes', () => {
    const cell = parseWeatherCell(cellDocument())
    expect(cell?.cycle.toISOString()).toBe('2026-09-30T08:00:00.000Z')
    expect(cell?.squares.get('563,2073')).toBe(0)
  })

  it('refuses a file whose wind is not in knots, rather than printing every speed wrong', () => {
    const doc = cellDocument()
    ;(doc.units as Record<string, string>).windspd = 'm/s'
    expect(parseWeatherCell(doc)).toBeNull()
  })

  it('refuses another payload, another schema, or a file with no cycle', () => {
    expect(parseWeatherCell(cellDocument({ payload: 'weather_alerts' }))).toBeNull()
    expect(parseWeatherCell(cellDocument({ schema: 2 }))).toBeNull()
    expect(parseWeatherCell(cellDocument({ cycle: undefined }))).toBeNull()
  })

  it('has no forecast for a square the file does not list', () => {
    const cell = parseWeatherCell(cellDocument())
    expect(cell && forecastForSquare(cell, [1, 1])).toBeNull()
  })

  it('marks a square whose numbers were read from a land neighbour as borrowed', () => {
    const cell = parseWeatherCell(cellDocument({ borrowed: [[0, 563, 2072]] }))
    expect(cell && forecastForSquare(cell, SQUARE)?.borrowed).toBe(true)
  })
})

describe('forecastView - the five days', () => {
  const now = new Date('2026-09-30T13:30Z')

  it('gives each day its high, the night after it, and the wetter of its two 12-hour chances', () => {
    const days = forecastView(lakesForecast(), now).days
    expect(days.map((d) => [d.date, d.highF, d.lowF, d.chance])).toEqual([
      ['2026-09-30', 56, 47, 2],
      ['2026-10-01', 61, 53, 36],
      ['2026-10-02', 56, 41, 84],
      ['2026-10-03', 48, 34, 0],
      ['2026-10-04', 48, 38, 23],
    ])
  })

  it('reads Thursday as 36% because Thursday night is, though Thursday daytime is 17%', () => {
    // 00Z Fri ends Thursday's 8 am-8 pm window (17); 12Z Fri ends the night
    // after (36). A camper at the hut Thursday night needs the 36.
    const thursday = forecastView(lakesForecast(), now).days[1]
    expect(thursday.chance).toBe(36)
  })

  it('says nothing about how far ahead a forecast was made while it was made today', () => {
    const days = forecastView(lakesForecast(), now).days
    expect(days.every((d) => d.madeDaysBefore === null)).toBe(true)
  })

  it('rolls the days by the calendar three days out of signal, and says how far ahead each was made', () => {
    const days = forecastView(lakesForecast(), new Date('2026-10-03T14:00Z')).days
    expect(days.map((d) => [d.date, d.highF, d.lowF, d.madeDaysBefore, d.none])).toEqual([
      ['2026-10-03', 48, 34, 3, false],
      ['2026-10-04', 48, 38, 4, false],
      ['2026-10-05', 45, 28, 5, false],
      ['2026-10-06', 35, null, 6, false],
      ['2026-10-07', null, null, 7, true],
    ])
  })

  it('leaves a low the file does not hold as null on Tuesday, rather than borrowing Monday night', () => {
    const tuesday = forecastView(lakesForecast(), new Date('2026-10-03T14:00Z')).days[3]
    expect(tuesday.lowF).toBeNull()
  })

  it("falls back to the rest of today's hourly temperatures when an afternoon run carries no high for today", () => {
    // Drop today's maxt, as NBM's afternoon runs do, and read at 18Z: the
    // hours after now that are still today (UTC here) are 18Z-23Z.
    const doc = cellDocument()
    const maxt = fieldsOf(doc).maxt
    fieldsOf(doc).maxt = {
      times: maxt.times.slice(1),
      values: maxt.values.map((v) => v.slice(1)),
    }
    const today = forecastView(lakesForecast(doc), new Date('2026-09-30T18:00Z')).days[0]
    expect(today.highF).toBe(55)
    expect(today.highIsRestOfDay).toBe(true)
  })

  it('counts the age in calendar days from the run: yesterday is 1 even at 9:30 the next morning', () => {
    expect(forecastView(lakesForecast(), now).ageDays).toBe(0)
    expect(forecastView(lakesForecast(), new Date('2026-10-01T13:30Z')).ageDays).toBe(1)
  })
})

describe('forecastView - the hour-by-hour strip', () => {
  it('starts at the next whole hour and runs six hours: 14Z-19Z at 13:30Z', () => {
    const { slots } = forecastView(lakesForecast(), new Date('2026-09-30T13:30Z')).hourly
    expect(
      slots.map((s) => [s.at.toISOString().slice(11, 16), s.tempF, s.sky, s.chance]),
    ).toEqual([
      ['14:00', 50, 'partly-cloudy', 0],
      ['15:00', 52, 'partly-cloudy', 0],
      ['16:00', 53, 'mostly-cloudy', 0],
      ['17:00', 55, 'mostly-cloudy', 0],
      ['18:00', 55, 'mostly-cloudy', 0],
      ['19:00', 55, 'mostly-cloudy', 0],
    ])
  })

  it('sums the strip wind as a range of speeds and the highest gust, in knots as NBM gives them', () => {
    const hourly = forecastView(lakesForecast(), new Date('2026-09-30T13:30Z')).hourly
    expect(hourly.windKt).toEqual({ min: 3, max: 5 })
    expect(hourly.gustKt).toBe(7)
  })

  it('shows no thunder line when every hour of the strip is 0%', () => {
    expect(
      forecastView(lakesForecast(), new Date('2026-09-30T13:30Z')).hourly.thunder,
    ).toBeNull()
  })

  it('names the strip hour with the highest thunder chance when one is above zero', () => {
    const doc = cellDocument()
    const tstm01 = fieldsOf(doc).tstm01
    tstm01.values = tstm01.values.map((v) =>
      v.map((_, i) => (i === 7 ? 12 : i === 8 ? 4 : 0)),
    )
    const thunder = forecastView(lakesForecast(doc), new Date('2026-09-30T13:30Z')).hourly
      .thunder
    expect(thunder?.chance).toBe(12)
    expect(thunder?.at.toISOString()).toBe('2026-09-30T16:00:00.000Z')
  })

  it(`goes stale ${HOURLY_TRUST_HOURS} hours after NOAA's run, whether or not the phone has signal`, () => {
    expect(
      forecastView(lakesForecast(), new Date('2026-09-30T13:59Z')).hourly.stale,
    ).toBe(false)
    expect(
      forecastView(lakesForecast(), new Date('2026-09-30T14:01Z')).hourly.stale,
    ).toBe(true)
  })

  it('is empty once the hours run out, and remembers the last hour it held', () => {
    const hourly = forecastView(lakesForecast(), new Date('2026-10-03T14:00Z')).hourly
    expect(hourly.slots).toEqual([])
    expect(hourly.lastHour?.toISOString()).toBe('2026-10-02T08:00:00.000Z')
  })
})

describe('skyCover', () => {
  it("words the sky in NWS's eighths: under 12.5% clear, then 37.5, 62.5 and 87.5", () => {
    expect(
      [0, 12.4, 12.5, 37.4, 37.5, 62.4, 62.5, 87.4, 87.5, 100].map(skyCover),
    ).toEqual([
      'clear',
      'clear',
      'mostly-clear',
      'mostly-clear',
      'partly-cloudy',
      'partly-cloudy',
      'mostly-cloudy',
      'mostly-cloudy',
      'cloudy',
      'cloudy',
    ])
  })
})

describe('parseWeatherAlerts and alertsForSquare', () => {
  const advisory = {
    id: 'urn:oid:2.49.0.1.840.0.example',
    event: 'Wind Advisory',
    headline:
      'Wind Advisory issued September 30 at 4:03AM EDT until October 1 at 8:00AM EDT',
    description: '* WHAT...Northwest winds 20 to 30 mph with gusts up to 50 mph.',
    instruction: null,
    severity: 'Moderate',
    sender_name: 'NWS Gray ME',
    onset: '2026-09-30T04:03:00-04:00',
    expires: '2026-09-30T15:15:00-04:00',
    ends: '2026-10-01T08:00:00-04:00',
    placed_by: 'zones',
    squares: [SQUARE],
  }
  const doc = {
    payload: 'weather_alerts',
    schema: 1,
    fetched_at: '2026-09-30T08:52:00Z',
    alerts: [advisory],
  }

  it("gives a square the alerts placed on it, in NWS's own words", () => {
    const alerts = parseWeatherAlerts(doc)
    expect(alerts?.fetchedAt.toISOString()).toBe('2026-09-30T08:52:00.000Z')
    const here = alerts && alertsForSquare(alerts, SQUARE, new Date('2026-09-30T13:30Z'))
    expect(here?.map((a) => [a.event, a.senderName])).toEqual([
      ['Wind Advisory', 'NWS Gray ME'],
    ])
    expect(
      alerts && alertsForSquare(alerts, [1, 1], new Date('2026-09-30T13:30Z')),
    ).toEqual([])
  })

  it("keeps an alert past its message's expiry until the hazard's own end, and drops it after", () => {
    const alerts = parseWeatherAlerts(doc)!
    expect(alertsForSquare(alerts, SQUARE, new Date('2026-09-30T20:00Z'))).toHaveLength(1)
    expect(alertsForSquare(alerts, SQUARE, new Date('2026-10-01T12:01Z'))).toHaveLength(0)
  })

  it('refuses a file with no fetched_at, because the warnings line could not say how old it is', () => {
    expect(parseWeatherAlerts({ ...doc, fetched_at: undefined })).toBeNull()
    expect(parseWeatherAlerts({ ...doc, payload: 'weather' })).toBeNull()
  })
})
