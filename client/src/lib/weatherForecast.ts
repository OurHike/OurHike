// What the waypoint card's weather says, worked out from the published files
// (#1056 build step 3; features/WEATHER.md §5 and §7).
//
// Pure: a cell file, the alerts file and the time in, the numbers the card
// shows out. Nothing here fetches, formats a unit or writes a sentence -
// lib/weatherData.ts fetches, chrome/WeatherBand.tsx words it, lib/units.ts
// converts it. What IS here is every rule that decides what a hiker may be
// shown, because those are the ones a test has to be able to reach without a
// card.
//
// THE FORECAST IS NBM AS NOAA PUBLISHED IT, in NBM's units (°F, %, knots),
// with no elevation correction (the maintainer's call of 2026-09-30, after
// build step 2 scored the correction and it did not reliably beat NBM).
//
// THE RULES, each from WEATHER.md §5 as the maintainer approved it 2026-09-24:
//
// - Days are keyed by the calendar, never by position: a forecast made on
//   Wednesday and read on Friday shows Friday's forecast as Friday's, and says
//   how many days ahead it was made.
// - Past the last day the phone holds, a day is `none`. It is never copied from
//   the day before and never filled in.
// - The hour-by-hour row goes stale once NOAA's run is older than
//   `HOURLY_TRUST_HOURS`, whether or not the phone has signal - WEATHER.md §4
//   says why that is the rule working rather than a bug.
// - A value NBM left empty is `null` and stays `null`. "No chance published"
//   is not "0% chance".

/** The bucket keys, which are URLs deployed phones request and can never be
 *  renamed (pipeline/R2_LAYOUT.md). Written by `pipeline/export_weather.py`
 *  and `pipeline/export_weather_alerts.py`. */
export function weatherCellKey(cell: string): string {
  return `conditions/weather/${cell}.json`
}
export const WEATHER_ALERTS_KEY = 'conditions/weather_alerts.json'

/**
 * How old NOAA's run may be before the hour-by-hour row greys.
 *
 * @unvalidated 6 hours is half the 12 hours the maintainer named for "no
 * signal", picked in WEATHER.md §5 with nothing behind it. The reasoning that
 * the hourly row should go first is that the timing of showers and storms is
 * where a forecast is least trustworthy; the number is not measured. What
 * would settle it: scoring NBM's hourly precipitation chance against observed
 * precipitation by lead time, over a season with convective storms.
 */
export const HOURLY_TRUST_HOURS = 6

/** Six hours in the strip - the approved drawing's width, which is what fits
 *  six 37 px boxes in the 240 px inside a 264 px card. */
export const HOURLY_SLOTS = 6

/** Five days, as #1056 asks for. The file holds seven; the card shows five. */
export const FORECAST_DAYS = 5

const HOUR_MS = 60 * 60 * 1000
const DAY_MS = 24 * HOUR_MS

// ---------------------------------------------------------------------------
// The cell file.

/** Each field's unit as `export_weather.py` declares it. A file declaring any
 *  other unit is refused: a changed unit would print every number wrong and
 *  every one of them plausible. */
const EXPECTED_UNITS: Record<string, string> = {
  temp: 'F',
  pop01: '%',
  sky: '%',
  windspd: 'kt',
  windgust: 'kt',
  tstm01: '%',
  maxt: 'F',
  mint: 'F',
  pop12: '%',
}

type FieldName = keyof typeof EXPECTED_UNITS

interface RawField {
  times: number[]
  values: (number | null)[][]
}

export interface WeatherCell {
  /** NOAA's run - the forecast's own age, and the one the card prints. */
  cycle: Date
  /** When our job baked the file. Never shown: it is younger than the
   *  forecast, and showing it would make the forecast look fresher. */
  generatedAt: Date
  squares: Map<string, number>
  borrowed: Set<number>
  fields: Partial<Record<FieldName, RawField>>
}

/** One square's forecast: each field's `[validTime, value]` pairs, in time
 *  order. A window field's time is when its window ENDS. */
export interface SquareForecast {
  cycle: Date
  /** True when the square's centre is water and its numbers were read from
   *  the nearest land square (WEATHER.md §6). */
  borrowed: boolean
  series: Record<FieldName, [number, number | null][]>
}

function parseStamp(value: unknown): Date | null {
  if (typeof value !== 'string') return null
  // `2026-09-30T08:00Z` - valid ISO 8601 that every engine this app supports
  // parses, though it has no seconds.
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function squareKey(row: number, col: number): string {
  return `${row},${col}`
}

/**
 * A cell file, validated, or null. Refused rather than repaired: a document
 * this build cannot read is a forecast it cannot vouch for, and the card then
 * shows no weather rather than a guess.
 */
export function parseWeatherCell(document: unknown): WeatherCell | null {
  if (typeof document !== 'object' || document === null) return null
  const doc = document as Record<string, unknown>
  if (doc.payload !== 'weather' || doc.schema !== 1) return null
  const cycle = parseStamp(doc.cycle)
  const generatedAt = parseStamp(doc.generated_at)
  if (cycle === null || generatedAt === null) return null
  if (
    !Array.isArray(doc.squares) ||
    typeof doc.fields !== 'object' ||
    doc.fields === null
  ) {
    return null
  }
  const units = (doc.units ?? {}) as Record<string, unknown>

  const squares = new Map<string, number>()
  doc.squares.forEach((square: unknown, index) => {
    if (Array.isArray(square) && square.length === 2) {
      squares.set(squareKey(Number(square[0]), Number(square[1])), index)
    }
  })

  const fields: Partial<Record<FieldName, RawField>> = {}
  for (const [name, raw] of Object.entries(doc.fields as Record<string, unknown>)) {
    if (!(name in EXPECTED_UNITS)) continue
    if (units[name] !== EXPECTED_UNITS[name]) return null
    const field = raw as { times?: unknown; values?: unknown }
    if (!Array.isArray(field.times) || !Array.isArray(field.values)) return null
    const times = field.times.map(parseStamp)
    if (times.some((t) => t === null)) return null
    fields[name as FieldName] = {
      times: times.map((t) => (t as Date).getTime()),
      values: field.values as (number | null)[][],
    }
  }

  const borrowed = new Set<number>()
  if (Array.isArray(doc.borrowed)) {
    for (const entry of doc.borrowed)
      if (Array.isArray(entry)) borrowed.add(Number(entry[0]))
  }
  return { cycle, generatedAt, squares, borrowed, fields }
}

/** The forecast for one square, or null when the file does not list it. */
export function forecastForSquare(
  cell: WeatherCell,
  [row, col]: [number, number],
): SquareForecast | null {
  const index = cell.squares.get(squareKey(row, col))
  if (index === undefined) return null
  const series = {} as Record<FieldName, [number, number | null][]>
  for (const name of Object.keys(EXPECTED_UNITS) as FieldName[]) {
    const field = cell.fields[name]
    const values = field?.values[index]
    series[name] =
      field === undefined || !Array.isArray(values)
        ? []
        : field.times.map((t, i) => [t, typeof values[i] === 'number' ? values[i] : null])
  }
  return { cycle: cell.cycle, borrowed: cell.borrowed.has(index), series }
}

// ---------------------------------------------------------------------------
// Sky cover, in NWS's own words.

export type SkyCover =
  'clear' | 'mostly-clear' | 'partly-cloudy' | 'mostly-cloudy' | 'cloudy'

/**
 * NWS's sky-condition categories, by eighths of the sky covered by opaque
 * cloud: 1/8 or less clear or sunny, to 3/8 mostly clear or mostly sunny, to
 * 5/8 partly cloudy or partly sunny, to 7/8 mostly cloudy, then cloudy - the
 * table NWS publishes for its own forecast wording (weather.gov/bgm/
 * forecast_terms, read 2026-09-30). NBM's sky field is that same percentage.
 * The names are the night words; chrome/WeatherBand.tsx says the day ones by
 * day.
 */
export function skyCover(percent: number): SkyCover {
  if (percent < 12.5) return 'clear'
  if (percent < 37.5) return 'mostly-clear'
  if (percent < 62.5) return 'partly-cloudy'
  if (percent < 87.5) return 'mostly-cloudy'
  return 'cloudy'
}

// ---------------------------------------------------------------------------
// The card's numbers.

export interface HourSlot {
  at: Date
  tempF: number | null
  sky: SkyCover | null
  /** Chance of rain or snow in the hour ending at `at`. */
  chance: number | null
}

export interface HourlyView {
  slots: HourSlot[]
  /** NOAA's run is older than HOURLY_TRUST_HOURS. */
  stale: boolean
  windKt: { min: number; max: number } | null
  gustKt: number | null
  /** The strip's highest thunder chance, when there is one above zero. NBM's
   *  thunder field stops at hour 36, so a strip past it has none to show,
   *  which is not the same as a 0% chance and is not shown as one. */
  thunder: { chance: number; at: Date } | null
  /** The last hour the phone holds, for "ran out at" once the strip is
   *  empty; null when the file carried no hours at all. */
  lastHour: Date | null
}

export interface ForecastDay {
  /** `YYYY-MM-DD`, the calendar day. */
  date: string
  isToday: boolean
  highF: number | null
  /** The high is the rest of today's, from the hourly temperatures, because
   *  NOAA's afternoon runs no longer carry today's high. */
  highIsRestOfDay: boolean
  /** The night after this day - NWS's "Wednesday / Wednesday night" pairing. */
  lowF: number | null
  /** The higher of the day's and that night's 12-hour chance of rain or snow. */
  chance: number | null
  /** How many days before this day NOAA's run was made, when the run is from
   *  an earlier day than today; null for a forecast made today. */
  madeDaysBefore: number | null
  /** Nothing in the file covers this day. */
  none: boolean
}

export interface ForecastView {
  cycle: Date
  /** Calendar days between the run and today: 0 today, 1 yesterday. */
  ageDays: number
  borrowed: boolean
  hourly: HourlyView
  days: ForecastDay[]
}

/** The phone's own calendar date, which is what "today" means to a hiker. */
export function localDateKey(time: Date): string {
  const month = String(time.getMonth() + 1).padStart(2, '0')
  const day = String(time.getDate()).padStart(2, '0')
  return `${time.getFullYear()}-${month}-${day}`
}

function utcDateKey(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

function daysBetween(fromKey: string, toKey: string): number {
  return Math.round(
    (Date.parse(`${toKey}T00:00Z`) - Date.parse(`${fromKey}T00:00Z`)) / DAY_MS,
  )
}

function addDays(key: string, days: number): string {
  return utcDateKey(Date.parse(`${key}T00:00Z`) + days * DAY_MS)
}

// WHICH DAY A WINDOW BELONGS TO. NBM names each window by when it ends:
// the day's high by 06Z on the next date, the night's low by 18Z on the next
// date, and 12-hour rain chances every six hours (fetch_weather.py's
// docstring). 06Z is 10 pm to 2 am across the US zones on this grid (Pacific
// standard to Eastern daylight time), and 18Z is 10 am to 2 pm the morning
// after, so stepping back 30 and 42 hours lands on 00Z of the day each belongs
// to in every one of them. Rain chances are read only from the two windows
// that do not overlap: 12Z to 00Z (the day - 4 am to 4 pm in Pacific winter,
// 8 am to 8 pm in Eastern summer) and 00Z to 12Z (the night after).
const MAXT_BACK_MS = 30 * HOUR_MS
const MINT_BACK_MS = 42 * HOUR_MS
const DAY_CHANCE_BACK_MS = 24 * HOUR_MS
const NIGHT_CHANCE_BACK_MS = 36 * HOUR_MS

function byDay(
  series: [number, number | null][],
  dayOf: (end: number) => string | null,
): Map<string, number> {
  const out = new Map<string, number>()
  for (const [end, value] of series) {
    if (value === null) continue
    const key = dayOf(end)
    if (key === null) continue
    const prior = out.get(key)
    out.set(key, prior === undefined ? value : Math.max(prior, value))
  }
  return out
}

function hourlyView(forecast: SquareForecast, now: Date): HourlyView {
  const { temp, sky, pop01, windspd, windgust, tstm01 } = forecast.series
  const at = (series: [number, number | null][], t: number) =>
    series.find(([time]) => time === t)?.[1] ?? null

  const future = temp.filter(([t]) => t > now.getTime()).slice(0, HOURLY_SLOTS)
  const slots = future.map(([t, tempF]) => {
    const cover = at(sky, t)
    return {
      at: new Date(t),
      tempF,
      sky: cover === null ? null : skyCover(cover),
      chance: at(pop01, t),
    }
  })
  const times = slots.map((s) => s.at.getTime())
  const pick = (series: [number, number | null][]) =>
    times.map((t) => at(series, t)).filter((v): v is number => v !== null)

  const speeds = pick(windspd)
  const gusts = pick(windgust)
  let thunder: HourlyView['thunder'] = null
  for (const t of times) {
    const chance = at(tstm01, t)
    if (chance !== null && chance > 0 && (thunder === null || chance > thunder.chance)) {
      thunder = { chance, at: new Date(t) }
    }
  }
  const last = temp.at(-1)
  return {
    slots,
    stale: now.getTime() - forecast.cycle.getTime() > HOURLY_TRUST_HOURS * HOUR_MS,
    windKt:
      speeds.length === 0 ? null : { min: Math.min(...speeds), max: Math.max(...speeds) },
    gustKt: gusts.length === 0 ? null : Math.max(...gusts),
    thunder,
    lastHour: last === undefined ? null : new Date(last[0]),
  }
}

/** Everything the card shows about one square at one moment. */
export function forecastView(forecast: SquareForecast, now: Date): ForecastView {
  const today = localDateKey(now)
  const madeOn = localDateKey(forecast.cycle)
  const { maxt, mint, pop12, temp } = forecast.series

  const highs = byDay(maxt, (end) => utcDateKey(end - MAXT_BACK_MS))
  const lows = byDay(mint, (end) => utcDateKey(end - MINT_BACK_MS))
  const chances = byDay(pop12, (end) => {
    const hour = new Date(end).getUTCHours()
    if (hour === 0) return utcDateKey(end - DAY_CHANCE_BACK_MS)
    if (hour === 12) return utcDateKey(end - NIGHT_CHANCE_BACK_MS)
    return null
  })

  const days: ForecastDay[] = []
  for (let offset = 0; offset < FORECAST_DAYS; offset++) {
    const date = addDays(today, offset)
    let highF = highs.get(date) ?? null
    let highIsRestOfDay = false
    if (highF === null && offset === 0) {
      const rest = temp
        .filter(
          ([t, v]) =>
            v !== null && t > now.getTime() && localDateKey(new Date(t)) === today,
        )
        .map(([, v]) => v as number)
      if (rest.length > 0) {
        highF = Math.max(...rest)
        highIsRestOfDay = true
      }
    }
    const lowF = lows.get(date) ?? null
    const chance = chances.get(date) ?? null
    days.push({
      date,
      isToday: offset === 0,
      highF,
      highIsRestOfDay,
      lowF,
      chance,
      madeDaysBefore: madeOn < today ? daysBetween(madeOn, date) : null,
      none: highF === null && lowF === null && chance === null,
    })
  }

  return {
    cycle: forecast.cycle,
    ageDays: Math.max(0, daysBetween(madeOn, today)),
    borrowed: forecast.borrowed,
    hourly: hourlyView(forecast, now),
    days,
  }
}

// ---------------------------------------------------------------------------
// NWS's alerts.

export interface WeatherAlert {
  id: string
  /** NWS's own words, relayed (HIKER_SAFETY.md §3): "Wind Advisory". */
  event: string
  headline: string | null
  description: string | null
  instruction: string | null
  senderName: string | null
  onset: Date | null
  /** When the hazard ends, or failing that when the message expires. */
  until: Date | null
}

export interface WeatherAlerts {
  /** When the job asked NWS - the age the warnings line has to show. */
  fetchedAt: Date
  bySquare: Map<string, WeatherAlert[]>
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value : null
}

/** The alerts file, validated, or null. A file with no `fetched_at` is
 *  refused: the warnings line cannot say how old its answer is without it. */
export function parseWeatherAlerts(document: unknown): WeatherAlerts | null {
  if (typeof document !== 'object' || document === null) return null
  const doc = document as Record<string, unknown>
  if (doc.payload !== 'weather_alerts' || doc.schema !== 1) return null
  const fetchedAt = parseStamp(doc.fetched_at)
  if (fetchedAt === null || !Array.isArray(doc.alerts)) return null

  const bySquare = new Map<string, WeatherAlert[]>()
  for (const raw of doc.alerts as Record<string, unknown>[]) {
    const event = text(raw?.event)
    if (event === null || !Array.isArray(raw.squares)) continue
    const alert: WeatherAlert = {
      id: String(raw.id),
      event,
      headline: text(raw.headline),
      description: text(raw.description),
      instruction: text(raw.instruction),
      senderName: text(raw.sender_name),
      onset: parseStamp(raw.onset),
      until: parseStamp(raw.ends) ?? parseStamp(raw.expires),
    }
    for (const square of raw.squares as unknown[]) {
      if (!Array.isArray(square)) continue
      const key = squareKey(Number(square[0]), Number(square[1]))
      bySquare.set(key, [...(bySquare.get(key) ?? []), alert])
    }
  }
  return { fetchedAt, bySquare }
}

/**
 * The alerts reaching one square that NWS has not yet said are over.
 *
 * An alert past its own end is dropped because NWS's schedule says it is
 * over, not because OurHike judged it minor - every alert that is still on
 * is shown, whatever its kind (the maintainer's "relay all", 2026-09-26).
 */
export function alertsForSquare(
  alerts: WeatherAlerts,
  [row, col]: [number, number],
  now: Date,
): WeatherAlert[] {
  return (alerts.bySquare.get(squareKey(row, col)) ?? []).filter(
    (alert) => alert.until === null || alert.until.getTime() > now.getTime(),
  )
}
