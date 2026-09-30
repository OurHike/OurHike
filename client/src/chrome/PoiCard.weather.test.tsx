import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { PoiCard, type PoiDetail } from './PoiCard'
import type { WaypointWeather } from '../lib/weatherData'
import {
  forecastForSquare,
  parseWeatherAlerts,
  parseWeatherCell,
  type WeatherAlerts,
} from '../lib/weatherForecast'
import {
  weatherAlertsDocument,
  weatherCellDocument,
} from '../../preview-shots/fixtures/weather.mjs'

// NOAA's forecast on the waypoint card (#1056 build step 3), as the
// maintainer chose it by poll on 2026-09-30 against waypoint-weather-mock.html:
// one line on the peek (frame A), a "Weather here" band in the opened card,
// units that follow the feet/metres setting, and the published NWS list's
// warnings line on the card now rather than at step 4.
//
// The fetching is lib/weatherData.ts's and has its own tests; here the hook is
// replaced so each test says exactly which forecast the card holds. Tests run
// in UTC, so NOAA's 08Z run prints as "8:00 am".

let weather: WaypointWeather = { kind: 'none' }
vi.mock('../lib/weatherData', () => ({ useWaypointWeather: () => weather }))

const HUT: PoiDetail = {
  id: 'atc_shelters:lakes',
  name: 'Lakes of the Clouds Hut',
  type: 'shelter',
  lat: 44.2587,
  lon: -71.319,
  confidence: 'high',
  source: 'atc_shelters',
  mile: 1853.9,
}
const SQUARE: [number, number] = [563, 2073]
const CYCLE = new Date('2026-09-30T08:00Z')
const NOW = new Date('2026-09-30T13:30Z')

function alertsOf(alerts: Record<string, unknown>[] = []): WeatherAlerts {
  const parsed = parseWeatherAlerts(
    weatherAlertsDocument({ fetchedAt: new Date('2026-09-30T08:52Z'), alerts }),
  )
  if (parsed === null) throw new Error('alerts fixture did not parse')
  return parsed
}

function holding({
  live = true,
  checkedAt = new Date('2026-09-30T13:18Z'),
  alerts = alertsOf(),
}: {
  live?: boolean
  checkedAt?: Date
  alerts?: WeatherAlerts | null
} = {}): WaypointWeather {
  const cell = parseWeatherCell(weatherCellDocument({ cycle: CYCLE, squares: [SQUARE] }))
  const forecast = cell && forecastForSquare(cell, SQUARE)
  if (forecast === null || forecast === undefined)
    throw new Error('fixture did not parse')
  return {
    kind: 'forecast',
    square: SQUARE,
    forecast,
    checkedAt,
    live,
    alerts: alerts === null ? null : { value: alerts, checkedAt, live },
  }
}

const ADVISORY = {
  id: 'urn:oid:example',
  event: 'Wind Advisory',
  headline: 'Wind Advisory issued September 30 until October 1 at 8:00AM EDT',
  description: '* WHAT...Northwest winds 20 to 30 mph with gusts up to 50 mph.',
  instruction: null,
  sender_name: 'NWS Gray ME',
  onset: '2026-09-30T04:03:00-04:00',
  expires: '2026-09-30T15:15:00-04:00',
  ends: '2026-10-01T08:00:00-04:00',
  squares: [SQUARE],
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  weather = { kind: 'none' }
})

function peek(units: 'imperial' | 'metric' = 'imperial') {
  return render(<PoiCard poi={HUT} map={null} units={units} onClose={vi.fn()} />)
}

function openCard(units: 'imperial' | 'metric' = 'imperial') {
  const view = peek(units)
  fireEvent.click(screen.getByTestId('poi-card-expand'))
  return view
}

describe('the peek', () => {
  it("carries today's high and low, the chance of rain or snow, and NOAA's run time on one line", () => {
    weather = holding()
    peek()
    expect(screen.getByTestId('poi-card-weather-line')).toHaveTextContent(
      'Today 56° / 47°2% chance of rain or snowNOAA 8 am',
    )
  })

  it('names the weather on the pull, so a hiker knows the forecast is behind it', () => {
    weather = holding()
    peek()
    expect(screen.getByTestId('poi-card-expand')).toHaveTextContent('Weather & details')
  })

  it('prints °C with the metres setting: 13° / 8°', () => {
    weather = holding()
    peek('metric')
    expect(screen.getByTestId('poi-card-weather-line')).toHaveTextContent(
      'Today 13° / 8°',
    )
  })

  it('says how far ahead the forecast was made once it is from an earlier day, in place of the run time', () => {
    vi.setSystemTime(new Date('2026-10-01T13:30Z'))
    weather = holding({ live: false })
    peek()
    expect(screen.getByTestId('poi-card-weather-line')).toHaveTextContent(
      'Today 61° / 53°36% chance of rain or snowmade 1 d before',
    )
  })

  it('leads with an NWS alert on for this spot, ahead of the forecast', () => {
    weather = holding({ alerts: alertsOf([ADVISORY]) })
    peek()
    // Ends 8 am EDT tomorrow, which is 12:00 pm in the UTC these tests run in.
    expect(screen.getByTestId('poi-card-weather-warning')).toHaveTextContent(
      'Wind Advisory until tomorrow 12:00 pm',
    )
  })

  it('shows no weather at all, and the plain pull, while there is no forecast to show', () => {
    peek()
    expect(screen.queryByTestId('poi-card-weather-line')).toBeNull()
    expect(screen.getByTestId('poi-card-expand')).toHaveTextContent(/^Details/)
  })
})

describe('the opened card', () => {
  it('puts a "Weather here" band between Conditions and About this place', () => {
    weather = holding()
    openCard()
    const titles = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(titles.indexOf('Weather here')).toBeLessThan(
      titles.indexOf('About this place'),
    )
  })

  it("dates the forecast by NOAA's run and the phone's last check", () => {
    weather = holding()
    openCard()
    expect(screen.getByTestId('poi-card-weather')).toHaveTextContent(
      'Forecast from 8:00 am · checked 12 min ago',
    )
  })

  it('dates the no-alert line to when the job asked NWS, and never says "No warnings"', () => {
    weather = holding()
    openCard()
    const band = screen.getByTestId('poi-card-weather')
    expect(band).toHaveTextContent('NWS had no alerts for this spot at 8:52 am')
    expect(band).not.toHaveTextContent(/No warnings/)
  })

  it("relays an alert in NWS's words, with who issued it and until when", () => {
    weather = holding({ alerts: alertsOf([ADVISORY]) })
    openCard()
    const band = screen.getByTestId('poi-card-weather')
    expect(band).toHaveTextContent('Wind Advisory')
    expect(band).toHaveTextContent('until tomorrow 12:00 pm · NWS Gray ME')
    expect(within(band).getByText('Read NWS’s full text')).toBeInTheDocument()
  })

  it('says the phone has not heard since the last check once it is out of signal', () => {
    weather = holding({ live: false })
    openCard()
    const band = screen.getByTestId('poi-card-weather')
    expect(band).toHaveTextContent('Forecast from 8:00 am · last checked 1:18 pm')
    expect(band).toHaveTextContent('No word on weather warnings since 8:52 am')
    expect(band).toHaveTextContent('A warning issued since then cannot reach this phone.')
  })

  it('lays out six hours and five days, wind in the unit the hiker chose', () => {
    weather = holding()
    openCard('metric')
    const band = screen.getByTestId('poi-card-weather')
    expect(
      within(band).getByRole('list', { name: 'Hour by hour' }).children,
    ).toHaveLength(6)
    expect(within(band).getByRole('list', { name: 'Five days' }).children).toHaveLength(5)
    expect(band).toHaveTextContent('Wind 6–9 km/h, gusts to 13 km/h through 7:00 pm')
    expect(band).toHaveTextContent('NOAA forecast for this spot’s grid square · °C')
  })

  it('draws a sun in the hours after sunrise at the hut and a moon in the hours after sunset', () => {
    // 13:30Z is 9:30 am in New Hampshire, after the 10:42Z sunrise; 02:30Z
    // the next day is 10:30 pm, after the 22:27Z sunset.
    weather = holding()
    openCard()
    const hours = within(screen.getByTestId('poi-card-weather')).getByRole('list', {
      name: 'Hour by hour',
    })
    expect(hours.querySelectorAll('.weather-icon__sun')).toHaveLength(6)
    expect(hours.querySelectorAll('.weather-icon__moon')).toHaveLength(0)
    expect(hours).toHaveTextContent('2:00 pm: Partly sunny, 50°')
    cleanup()

    vi.setSystemTime(new Date('2026-10-01T02:30Z'))
    weather = holding({ checkedAt: new Date('2026-10-01T02:18Z') })
    openCard()
    const night = within(screen.getByTestId('poi-card-weather')).getByRole('list', {
      name: 'Hour by hour',
    })
    expect(night.querySelectorAll('.weather-icon__moon')).toHaveLength(6)
    expect(night.querySelectorAll('.weather-icon__sun')).toHaveLength(0)
    expect(night).toHaveTextContent('3:00 am: Partly cloudy, 48°')
  })

  it("greys the hours and says why once NOAA's run is more than six hours old", () => {
    vi.setSystemTime(new Date('2026-09-30T14:30Z'))
    weather = holding()
    openCard()
    expect(screen.getByTestId('poi-card-weather')).toHaveTextContent(
      'Hour-by-hour timing is from 8:00 am — showers may come earlier or later.',
    )
  })

  it('reads "no forecast" for a day past the last one the phone holds, three days out of signal', () => {
    vi.setSystemTime(new Date('2026-10-03T14:00Z'))
    weather = holding({ live: false })
    openCard()
    const days = within(screen.getByTestId('poi-card-weather')).getByRole('list', {
      name: 'Five days',
    })
    expect(days.lastElementChild).toHaveTextContent('WedNo forecast')
    expect(screen.getByTestId('poi-card-weather')).toHaveTextContent(
      'Forecast is 3 days old (Wed 8:00 am)',
    )
  })
})
