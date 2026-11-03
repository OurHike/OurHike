// The waypoint card's weather, fetched and kept (#1056 build step 3).
//
// Two published files: the forecast for the waypoint's 1° cell
// (`conditions/weather/<cell>.json`) and every NWS alert over a trail square
// (`conditions/weather_alerts.json`). Both are read the way
// lib/publishedConditions.ts reads the other conditions - from the bucket with
// signal, from the copy this phone kept without it (lib/conditionsCache.ts,
// #447) - so a forecast opened once in a town is still on the card three days
// into a stretch, labelled with how old it is.
//
// NOTHING SHOWS UNTIL THERE IS A FORECAST. A cell with no file, a square the
// file does not list, a waypoint off NOAA's CONUS grid, no signal and nothing
// kept: all of them leave the card exactly as it was before weather existed.
// That is "omit rather than guess" (CLAUDE.md) and it is also what keeps this
// safe to ship ahead of the data - production publishes no weather until the
// release train promotes it (WEATHER.md §7), and until then every read here
// 404s and the card is unchanged.
//
// WHAT THIS DOES NOT DO YET: fetch the cells under a planned hike ahead of
// time (WEATHER.md §7's plan). A phone holds the forecast for the cells whose
// waypoints it opened with signal. Pre-fetching belongs with Today and the
// plan, build steps 4 and 5.

import { useEffect, useMemo, useState } from 'react'
import { DATA_CONFIGURED, dataUrl } from './config'
import { recallPublished, rememberPublished } from './conditionsCache'
import { nbmSquare, weatherCellName } from './nbmGrid'
import { useOnline } from './useOnline'
import { CONDITIONS_REFRESH_MS } from './useConditions'
import {
  WEATHER_ALERTS_KEY,
  forecastForSquare,
  parseWeatherAlerts,
  parseWeatherCell,
  weatherCellKey,
  type SquareForecast,
  type WeatherAlerts,
  type WeatherCell,
} from './weatherForecast'

/** One read of one file, and how it arrived. */
export interface WeatherRead<T> {
  value: T
  /** When this phone last received the file from the bucket - the "checked"
   *  on the card. For a kept copy, when it was stored. */
  checkedAt: Date
  /** True when this read reached the bucket; false for the kept copy. */
  live: boolean
}

async function readDocument<T>(
  key: string,
  parse: (document: unknown) => T | null,
  online: boolean,
): Promise<WeatherRead<T> | null> {
  if (!DATA_CONFIGURED) return null
  if (online) {
    try {
      const response = await fetch(dataUrl(key))
      if (response.ok) {
        const document = (await response.json()) as Record<string, unknown>
        const value = parse(document)
        if (value !== null) {
          void rememberPublished(key, document)
          return { value, checkedAt: new Date(), live: true }
        }
      }
    } catch {
      // A dead spot mid-transfer is exactly when the kept copy is for.
    }
  }
  const kept = await recallPublished(key)
  if (kept === null) return null
  const value = parse(kept.document)
  if (value === null) return null
  const storedAt = new Date(kept.storedAt)
  return {
    value,
    checkedAt: Number.isNaN(storedAt.getTime()) ? new Date(0) : storedAt,
    live: false,
  }
}

// One read per file shared by every card, so tapping from shelter to spring in
// the same cell does not fetch the cell twice. A live read is reused for
// CONDITIONS_REFRESH_MS, the clock every other conditions file keeps; a kept
// copy is re-asked for as soon as a card wants it and the phone is online.
const reads = new Map<
  string,
  { at: number; read: Promise<WeatherRead<unknown> | null> }
>()

function sharedRead<T>(
  key: string,
  parse: (document: unknown) => T | null,
  online: boolean,
): Promise<WeatherRead<T> | null> {
  const prior = reads.get(key)
  const now = Date.now()
  if (prior !== undefined && now - prior.at < CONDITIONS_REFRESH_MS) {
    const reuse = prior.read.then((read) => (read?.live || !online ? read : undefined))
    return reuse.then((read) =>
      read === undefined
        ? freshRead(key, parse, online)
        : (read as WeatherRead<T> | null),
    )
  }
  return freshRead(key, parse, online)
}

function freshRead<T>(
  key: string,
  parse: (document: unknown) => T | null,
  online: boolean,
): Promise<WeatherRead<T> | null> {
  const read = readDocument(key, parse, online)
  reads.set(key, { at: Date.now(), read })
  return read
}

/** For tests: forget every shared read. */
export function resetWeatherReads(): void {
  reads.clear()
}

export type WaypointWeather =
  | { kind: 'none' }
  | {
      kind: 'forecast'
      square: [number, number]
      forecast: SquareForecast
      checkedAt: Date
      live: boolean
      /** Null when the alerts file has never reached this phone. */
      alerts: WeatherRead<WeatherAlerts> | null
    }

const NONE: WaypointWeather = { kind: 'none' }

/** The forecast at a waypoint's NOAA square, or `none` while there is not one
 *  to show. */
export function useWaypointWeather(lon: number, lat: number): WaypointWeather {
  const online = useOnline()
  const square = useMemo(() => nbmSquare(lon, lat), [lon, lat])
  const cell = weatherCellName(lon, lat)
  const [cellRead, setCellRead] = useState<{
    key: string
    read: WeatherRead<WeatherCell> | null
  } | null>(null)
  const [alertsRead, setAlertsRead] = useState<WeatherRead<WeatherAlerts> | null>(null)
  const cellKey = weatherCellKey(cell)

  useEffect(() => {
    if (square === null) return
    let current = true
    void sharedRead(cellKey, parseWeatherCell, online).then((read) => {
      if (current) setCellRead({ key: cellKey, read })
    })
    void sharedRead(WEATHER_ALERTS_KEY, parseWeatherAlerts, online).then((read) => {
      if (current) setAlertsRead(read)
    })
    return () => {
      current = false
    }
  }, [cellKey, square, online])

  return useMemo(() => {
    if (
      square === null ||
      cellRead === null ||
      cellRead.key !== cellKey ||
      cellRead.read === null
    ) {
      return NONE
    }
    const forecast = forecastForSquare(cellRead.read.value, square)
    if (forecast === null) return NONE
    return {
      kind: 'forecast',
      square,
      forecast,
      checkedAt: cellRead.read.checkedAt,
      live: cellRead.read.live && online,
      alerts:
        alertsRead === null ? null : { ...alertsRead, live: alertsRead.live && online },
    }
  }, [square, cellRead, cellKey, alertsRead, online])
}
