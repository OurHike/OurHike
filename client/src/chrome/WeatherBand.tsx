// NOAA's forecast on the waypoint card (#1056 build step 3).
//
// Two pieces, chosen by the maintainer by poll on 2026-09-30 against
// waypoint-weather-mock.html, then polished after the first build ("It really
// looks unprofessional. That needs a lot more polish"):
//
// - `WeatherPeekLine`, one line on the peek (frame A over B): the sky, today's
//   high and low, the chance of rain or snow, and how old the forecast is -
//   never a temperature without its age. An NWS alert on for this spot goes
//   above it, because a warning one pull away behind a calm "Today 56°" is the
//   forecast outrunning the thing that matters (poll, 2026-09-30).
// - `WeatherSection`, the opened card's band: the age line, the warnings line
//   from the published NWS list, six hours, five days as rows with each day's
//   range drawn against the week's, and the credit.
//
// Every rule about what may be shown is lib/weatherForecast.ts's; every
// sentence is lib/weatherText.ts's; every unit is lib/units.ts's.

import { useMemo } from 'react'
import { isDaylight } from '../lib/daylight'
import { useClock } from '../lib/useClock'
import {
  formatTemperature,
  formatWind,
  formatWindRange,
  temperatureUnitLabel,
  type UnitSystem,
} from '../lib/units'
import type { WaypointWeather } from '../lib/weatherData'
import {
  alertsForSquare,
  forecastView,
  localDateKey,
  type ForecastDay,
  type HourSlot,
  type SkyCover,
  type WeatherAlert,
} from '../lib/weatherForecast'
import {
  ageLine,
  alertTimesText,
  clockText,
  hourText,
  quietWarningsLine,
  weekdayText,
  whenText,
} from '../lib/weatherText'
import { AlertIcon, DropIcon, SkyIcon, WindIcon } from './weatherIcons'

type Forecast = Extract<WaypointWeather, { kind: 'forecast' }>

interface WeatherProps {
  weather: Forecast
  units: UnitSystem
  /** Where the waypoint is, for whether each hour is day or night. */
  lat: number
  lon: number
}

/** NWS's words for each category, by night and by day (lib/weatherForecast.ts's
 *  skyCover has the table's source). */
const SKY_WORDS: Record<SkyCover, [night: string, day: string]> = {
  clear: ['Clear', 'Sunny'],
  'mostly-clear': ['Mostly clear', 'Mostly sunny'],
  'partly-cloudy': ['Partly cloudy', 'Partly sunny'],
  'mostly-cloudy': ['Mostly cloudy', 'Mostly cloudy'],
  cloudy: ['Cloudy', 'Cloudy'],
}

function temperature(value: number | null, units: UnitSystem): string {
  return value === null ? '—' : formatTemperature(value, units)
}

/** A chance, quiet when it is zero so the eye goes to the ones that are not. */
function Chance({ value, className }: { value: number | null; className: string }) {
  if (value === null) return <span className={`${className} ${className}--none`}>—</span>
  return (
    <span className={`${className}${value === 0 ? ` ${className}--zero` : ''}`}>
      <DropIcon />
      {`${value}%`}
      <span className="visually-hidden"> chance of rain or snow</span>
    </span>
  )
}

function activeAlerts(weather: Forecast, now: Date): WeatherAlert[] {
  return weather.alerts === null
    ? []
    : alertsForSquare(weather.alerts.value, weather.square, now)
}

/** The peek's one line, and an alert above it when one is on. */
export function WeatherPeekLine({ weather, units, lat, lon }: WeatherProps) {
  const now = useClock()
  const view = useMemo(() => forecastView(weather.forecast, now), [weather.forecast, now])
  const alerts = activeAlerts(weather, now)
  const today = view.days[0]
  const next = view.hourly.slots[0]

  return (
    <>
      {alerts.map((alert) => (
        <p
          key={alert.id}
          className="poi-card__weather-warning"
          role="note"
          data-testid="poi-card-weather-warning"
        >
          <AlertIcon />
          <span>
            <strong>{alert.event}</strong>
            {alertTimesText(alert, now) !== null && ` ${alertTimesText(alert, now)}`}
          </span>
        </p>
      ))}
      {!today.none && (
        <p className="poi-card__weather-line" data-testid="poi-card-weather-line">
          {next?.sky != null && (
            <SkyIcon cover={next.sky} day={isDaylight(lat, lon, next.at)} />
          )}
          <span className="poi-card__weather-today">
            {today.highIsRestOfDay ? 'Rest of today ' : 'Today '}
            <strong>{temperature(today.highF, units)}</strong>
            <span className="poi-card__weather-slash">{' / '}</span>
            {temperature(today.lowF, units)}
          </span>
          {today.chance !== null && (
            <Chance value={today.chance} className="poi-card__weather-line-chance" />
          )}
          <span className="poi-card__weather-age">
            {today.madeDaysBefore === null
              ? `NOAA ${view.cycle.getMinutes() === 0 ? hourText(view.cycle) : clockText(view.cycle)}`
              : `made ${today.madeDaysBefore} d before`}
          </span>
        </p>
      )}
    </>
  )
}

function Hour({ slot, units, day }: { slot: HourSlot; units: UnitSystem; day: boolean }) {
  const said = [
    slot.sky === null ? null : SKY_WORDS[slot.sky][day ? 1 : 0],
    slot.tempF === null ? null : formatTemperature(slot.tempF, units),
    slot.chance === null ? null : `${slot.chance}% chance of rain or snow`,
  ].filter((part) => part !== null)
  return (
    <li className="poi-card__weather-hour">
      <span className="visually-hidden">{`${clockText(slot.at)}: ${said.join(', ')}`}</span>
      <span className="poi-card__weather-hour-time" aria-hidden="true">
        {hourText(slot.at)}
      </span>
      <span className="poi-card__weather-hour-sky" aria-hidden="true">
        {slot.sky !== null && <SkyIcon cover={slot.sky} day={day} />}
      </span>
      <span className="poi-card__weather-hour-temp" aria-hidden="true">
        {temperature(slot.tempF, units)}
      </span>
      <span aria-hidden="true">
        <Chance value={slot.chance} className="poi-card__weather-hour-chance" />
      </span>
    </li>
  )
}

/** The week's coldest low and warmest high, which every day's bar is drawn
 *  against - so a cold day reads as cold beside a warm one. */
function weekRange(days: ForecastDay[]): { min: number; max: number } | null {
  const values = days
    .flatMap((d) => [d.lowF, d.highF])
    .filter((v): v is number => v !== null)
  if (values.length === 0) return null
  return { min: Math.min(...values), max: Math.max(...values) }
}

function Day({
  day,
  units,
  first,
  range,
}: {
  day: ForecastDay
  units: UnitSystem
  first: boolean
  range: { min: number; max: number } | null
}) {
  const label = day.isToday ? 'Today' : weekdayText(day.date)
  const note =
    day.madeDaysBefore !== null
      ? first
        ? `made ${day.madeDaysBefore} d before`
        : `${day.madeDaysBefore} d before`
      : day.highIsRestOfDay
        ? 'rest of day'
        : null

  if (day.none) {
    return (
      <li className="poi-card__weather-day poi-card__weather-day--none">
        <span className="poi-card__weather-day-name">{label}</span>
        <span className="poi-card__weather-day-none">No forecast</span>
      </li>
    )
  }

  const span = range === null ? 0 : range.max - range.min
  const low = day.lowF ?? day.highF
  const high = day.highF ?? day.lowF
  const bar =
    range !== null && low !== null && high !== null && span > 0
      ? {
          left: `${(((Math.min(low, high) - range.min) / span) * 100).toFixed(1)}%`,
          width: `${Math.max((Math.abs(high - low) / span) * 100, 4).toFixed(1)}%`,
        }
      : null

  return (
    <li className="poi-card__weather-day">
      <span className="poi-card__weather-day-name">
        {label}
        {note !== null && <span className="poi-card__weather-day-note">{note}</span>}
      </span>
      <Chance value={day.chance} className="poi-card__weather-day-chance" />
      <span className="poi-card__weather-day-low">
        <span className="visually-hidden">, low </span>
        {temperature(day.lowF, units)}
      </span>
      <span className="poi-card__weather-day-bar" aria-hidden="true">
        {bar !== null && <span className="poi-card__weather-day-fill" style={bar} />}
      </span>
      <span className="poi-card__weather-day-high">
        <span className="visually-hidden">, high </span>
        {temperature(day.highF, units)}
      </span>
    </li>
  )
}

function Alert({ alert, now }: { alert: WeatherAlert; now: Date }) {
  const times = alertTimesText(alert, now)
  const fullText = [alert.headline, alert.description, alert.instruction].filter(
    (part): part is string => part !== null,
  )
  return (
    <div className="poi-card__weather-alert" role="note">
      <AlertIcon />
      <div className="poi-card__weather-alert-body">
        <strong>{alert.event}</strong>
        <span>
          {[times, alert.senderName].filter((part) => part !== null).join(' · ')}
        </span>
        {fullText.length > 0 && (
          <details className="poi-card__weather-alert-text">
            <summary>Read NWS&rsquo;s full text</summary>
            {fullText.map((part, i) => (
              <p key={i}>{part}</p>
            ))}
          </details>
        )}
      </div>
    </div>
  )
}

/** The opened card's Weather band. */
export function WeatherSection({ weather, units, lat, lon }: WeatherProps) {
  const now = useClock()
  const view = useMemo(() => forecastView(weather.forecast, now), [weather.forecast, now])
  const alerts = activeAlerts(weather, now)
  const alertsLive = weather.alerts?.live ?? false
  const quiet = quietWarningsLine(
    weather.alerts?.value.fetchedAt ?? null,
    alertsLive,
    now,
  )
  const { hourly } = view
  const lastSlot = hourly.slots.at(-1)
  const range = weekRange(view.days)

  return (
    <section
      className="poi-card__section poi-card__weather"
      data-testid="poi-card-weather"
    >
      <h3 className="poi-card__section-title">Weather here</h3>
      <p
        className={`poi-card__weather-age-line${weather.live ? '' : ' poi-card__weather-age-line--stale'}`}
      >
        {ageLine(view.cycle, weather.checkedAt, weather.live, now)}
      </p>

      {alerts.map((alert) => (
        <Alert key={alert.id} alert={alert} now={now} />
      ))}
      {(alerts.length === 0 || !alertsLive) && (
        <div
          className={`poi-card__weather-quiet${alertsLive ? '' : ' poi-card__weather-quiet--unknown'}`}
          role="note"
        >
          <span className="poi-card__weather-quiet-title">{quiet.title}</span>
          {quiet.detail !== null && <span>{quiet.detail}</span>}
        </div>
      )}

      {hourly.slots.length > 0 ? (
        <>
          <ol
            className={`poi-card__weather-hours${hourly.stale ? ' poi-card__weather-hours--stale' : ''}`}
            aria-label="Hour by hour"
          >
            {hourly.slots.map((slot) => (
              <Hour
                key={slot.at.getTime()}
                slot={slot}
                units={units}
                day={isDaylight(lat, lon, slot.at)}
              />
            ))}
          </ol>
          {hourly.stale && (
            <p className="poi-card__weather-note">
              {`Hour-by-hour timing is from ${whenText(view.cycle, now)} — showers may come earlier or later.`}
            </p>
          )}
          {hourly.windKt !== null && lastSlot !== undefined && (
            <p className="poi-card__weather-wind">
              <WindIcon />
              <span>
                {`Wind ${formatWindRange(hourly.windKt.min, hourly.windKt.max, units)}`}
                {hourly.gustKt !== null &&
                  `, gusts to ${formatWind(hourly.gustKt, units)}`}
                {` through ${clockText(lastSlot.at)}`}
              </span>
            </p>
          )}
          {hourly.thunder !== null && (
            <p className="poi-card__weather-note">
              {`Thunder chance up to ${hourly.thunder.chance}% at ${clockText(hourly.thunder.at)}`}
            </p>
          )}
        </>
      ) : (
        hourly.lastHour !== null && (
          <p className="poi-card__weather-note">
            {localDateKey(hourly.lastHour) === localDateKey(now)
              ? `The hour-by-hour forecast ran out at ${clockText(hourly.lastHour)}.`
              : `The hour-by-hour forecast ran out ${whenText(hourly.lastHour, now)}.`}
          </p>
        )
      )}

      <ol className="poi-card__weather-days" aria-label="Five days">
        {view.days.map((day, i) => (
          <Day key={day.date} day={day} units={units} first={i === 0} range={range} />
        ))}
      </ol>

      <p className="poi-card__weather-credit">
        {view.borrowed
          ? `NOAA forecast for the nearest land square · ${temperatureUnitLabel(units)}`
          : `NOAA forecast for this spot’s grid square · ${temperatureUnitLabel(units)}`}
      </p>
    </section>
  )
}
