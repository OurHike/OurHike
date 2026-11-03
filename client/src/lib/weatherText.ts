// The words on the waypoint card's weather (#1056 build step 3).
//
// Every sentence here is one WEATHER.md §5 drew and the maintainer approved on
// 2026-09-24, with the forecast's age in it: a number on this card is never
// shown without the time NOAA made it. Units are lib/units.ts's; this file
// writes times and sentences only.
//
// The Intl formatters are built on first use, not at import - #1324's rule for
// anything in the card's import closure, since an Intl built at module load is
// work in front of the first paint.

import type { WeatherAlert } from './weatherForecast'
import { localDateKey } from './weatherForecast'

let clockFormat: Intl.DateTimeFormat | null = null
let hourFormat: Intl.DateTimeFormat | null = null
let weekdayFormat: Intl.DateTimeFormat | null = null

/** "4:00 am" - lower case, the way the approved drawing writes it. */
export function clockText(time: Date): string {
  clockFormat ??= new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' })
  return clockFormat
    .format(time)
    .replace(/\s?AM$/, ' am')
    .replace(/\s?PM$/, ' pm')
}

/** "10 am", "12 pm" - the strip's hour. */
export function hourText(time: Date): string {
  hourFormat ??= new Intl.DateTimeFormat('en-US', { hour: 'numeric' })
  return hourFormat
    .format(time)
    .replace(/\s?AM$/, ' am')
    .replace(/\s?PM$/, ' pm')
}

/** "Thu" for a calendar day `YYYY-MM-DD`. Read at noon so no time zone can
 *  move it across midnight. */
export function weekdayText(date: string): string {
  weekdayFormat ??= new Intl.DateTimeFormat('en-US', { weekday: 'short' })
  const [year, month, day] = date.split('-').map(Number)
  return weekdayFormat.format(new Date(year, month - 1, day, 12))
}

function daysAgo(time: Date, now: Date): number {
  const from = Date.parse(`${localDateKey(time)}T00:00Z`)
  const to = Date.parse(`${localDateKey(now)}T00:00Z`)
  return Math.round((to - from) / 86_400_000)
}

/** "4:00 am", "yesterday 4:00 am" or "Wed 4:00 am". */
export function whenText(time: Date, now: Date): string {
  const days = daysAgo(time, now)
  if (days <= 0) return clockText(time)
  if (days === 1) return `yesterday ${clockText(time)}`
  return `${weekdayText(localDateKey(time))} ${clockText(time)}`
}

/**
 * The age line: when NOAA made the forecast, and when this phone last got it.
 *
 * "Forecast from" is NOAA's run, not when our job copied it - the older of the
 * two, so the line never makes a forecast look fresher than it is.
 */
export function ageLine(cycle: Date, checkedAt: Date, live: boolean, now: Date): string {
  const days = daysAgo(cycle, now)
  const made =
    days >= 2
      ? `Forecast is ${days} days old (${whenText(cycle, now)})`
      : `Forecast from ${whenText(cycle, now)}`
  if (!live) return `${made} · last checked ${whenText(checkedAt, now)}`
  const minutes = Math.floor((now.getTime() - checkedAt.getTime()) / 60_000)
  if (minutes < 1) return `${made} · checked just now`
  if (minutes < 60) return `${made} · checked ${minutes} min ago`
  return `${made} · checked ${Math.floor(minutes / 60)} h ago`
}

/** The warnings line when no alert is on for this square.
 *
 *  Never "No warnings" (WEATHER.md §5). With signal, the claim is dated to
 *  the moment the job asked NWS; without it, the line says the phone has not
 *  heard since then, which is the only true thing it can say. */
export function quietWarningsLine(
  fetchedAt: Date | null,
  live: boolean,
  now: Date,
): { title: string; detail: string | null } {
  if (fetchedAt === null) {
    return { title: 'No word on weather warnings on this phone yet', detail: null }
  }
  if (live) {
    return {
      title: `NWS had no alerts for this spot at ${whenText(fetchedAt, now)}`,
      detail: null,
    }
  }
  return {
    title: `No word on weather warnings since ${whenText(fetchedAt, now)}`,
    detail: 'A warning issued since then cannot reach this phone.',
  }
}

/** "until Thu 8:00 am", "from 2:00 pm until 8:00 pm", or null when NWS gave
 *  the alert no end. */
export function alertTimesText(alert: WeatherAlert, now: Date): string | null {
  const future = (time: Date) => {
    const days = -daysAgo(time, now)
    if (days <= 0) return clockText(time)
    if (days === 1) return `tomorrow ${clockText(time)}`
    return `${weekdayText(localDateKey(time))} ${clockText(time)}`
  }
  const from =
    alert.onset !== null && alert.onset.getTime() > now.getTime()
      ? `from ${future(alert.onset)} `
      : ''
  if (alert.until === null) return from === '' ? null : from.trim()
  return `${from}until ${future(alert.until)}`
}
