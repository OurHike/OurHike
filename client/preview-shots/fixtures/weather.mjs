// A NOAA forecast for the recipes and tests that show the waypoint card's
// weather (#1056 build step 3).
//
// THE NUMBERS ARE REAL, THE TIMES ARE MOVED. Every value below is the Lakes of
// the Clouds square, NBM square (563, 2073), from NOAA's 08Z run of 2026-09-30
// as the UA publish wrote it to `conditions/weather/n44w072.json` - typed in
// rather than committed as a file. `weatherCellDocument`
// lays them onto whatever run time it is given, so a recipe can show a
// forecast made two hours before the camera runs.
//
// WHY A RECIPE HAS TO SERVE THIS. The preview builds against production's
// data, which publishes no weather until the release train promotes it
// (features/WEATHER.md §7), so every weather read there 404s and the card
// shows no weather - correctly. The recipe routes the cell file to this.
//
// Not a recipe: shared fixtures live one directory down, where the runner's
// recipe glob does not reach (fixtures/suggestedHikes.mjs explains).
// Nobody's data: a forecast is NOAA's and public domain.

/** Hours 1-48 of the run, from 09Z; thunder stops at 36, where NBM stops. */
export const LAKES_HOURLY = {
  temp: [
    46, 46, 45, 46, 49, 50, 52, 53, 55, 55, 55, 55, 54, 52, 50, 49, 49, 49, 48, 48, 48,
    48, 49, 49, 49, 49, 49, 51, 54, 57, 59, 60, 60, 60, 60, 58, 57, 56, 55, 55, 55, 55,
    55, 55, 55, 55, 55, 55,
  ],
  sky: [
    62, 70, 57, 37, 39, 51, 61, 82, 86, 83, 81, 76, 83, 80, 81, 76, 72, 76, 60, 49, 51,
    64, 58, 73, 62, 50, 37, 23, 20, 19, 26, 32, 58, 28, 42, 49, 56, 74, 75, 66, 40, 40,
    53, 47, 40, 37, 39, 56,
  ],
  pop01: [
    1, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 1, 1, 1, 1, 1, 1, 2, 3, 2, 3, 4, 2,
    2, 2, 3, 3, 4, 4, 4, 10, 15, 13, 9, 0, 0, 0, 0, 0, 0, 0, 0,
  ],
  windspd: [
    7, 7, 6, 5, 3, 3, 3, 3, 3, 4, 5, 5, 5, 4, 4, 5, 5, 5, 6, 7, 7, 8, 8, 8, 8, 7, 7, 7, 7,
    7, 8, 10, 11, 13, 13, 13, 12, 12, 13, 15, 16, 17, 18, 19, 19, 19, 18, 18,
  ],
  windgust: [
    10, 9, 8, 7, 5, 4, 4, 4, 5, 6, 7, 7, 7, 6, 7, 8, 8, 8, 9, 9, 10, 10, 10, 10, 10, 10,
    9, 9, 9, 10, 11, 14, 16, 18, 18, 18, 17, 17, 18, 20, 22, 23, 25, 26, 26, 25, 25, 25,
  ],
  tstm01: [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0,
  ],
}

/** Highs by the 06Z each window ends on, from the run's next date. */
export const LAKES_MAXT = [56, 61, 56, 48, 48, 45, 35]
/** Lows by the 18Z each window ends on, from the run's next date. */
export const LAKES_MINT = [47, 53, 41, 34, 38, 28]
/** 12-hour chances every six hours from 00Z on the run's next date. */
export const LAKES_POP12 = [
  0, 1, 2, 4, 17, 19, 36, 54, 84, 78, 30, 1, 0, 0, 0, 1, 3, 10, 23, 30, 34, 34, 22, 8, 4,
  2,
]

const HOUR_MS = 3_600_000

function stamp(ms) {
  return new Date(ms).toISOString().slice(0, 16) + 'Z'
}

/**
 * The cell file `pipeline/export_weather.py` writes, carrying the Lakes of the
 * Clouds forecast at every square in `squares`, from a run at `cycle` (a Date
 * on the hour).
 */
export function weatherCellDocument({ cycle, squares, cell = 'n44w072' }) {
  const start = cycle.getTime()
  const nextDate = Date.UTC(
    cycle.getUTCFullYear(),
    cycle.getUTCMonth(),
    cycle.getUTCDate() + 1,
  )
  const each = (values) => squares.map(() => values)
  const fields = {}
  for (const [name, values] of Object.entries(LAKES_HOURLY)) {
    fields[name] = {
      times: values.map((_, i) => stamp(start + (i + 1) * HOUR_MS)),
      values: each(values),
    }
  }
  fields.maxt = {
    times: LAKES_MAXT.map((_, i) => stamp(nextDate + (i * 24 + 6) * HOUR_MS)),
    values: each(LAKES_MAXT),
  }
  fields.mint = {
    times: LAKES_MINT.map((_, i) => stamp(nextDate + (i * 24 + 18) * HOUR_MS)),
    values: each(LAKES_MINT),
  }
  fields.pop12 = {
    times: LAKES_POP12.map((_, i) => stamp(nextDate + i * 6 * HOUR_MS)),
    values: each(LAKES_POP12),
  }
  return {
    payload: 'weather',
    schema: 1,
    source: 'NOAA National Blend of Models (NBM) v5.0',
    credit: 'NOAA forecast',
    cycle: stamp(start),
    generated_at: new Date(start + 59 * 60_000).toISOString().slice(0, 19) + 'Z',
    release: 'fixture',
    cell,
    units: {
      temp: 'F',
      pop01: '%',
      sky: '%',
      windspd: 'kt',
      windgust: 'kt',
      tstm01: '%',
      maxt: 'F',
      mint: 'F',
      pop12: '%',
    },
    squares,
    zones: squares.map(() => []),
    borrowed: [],
    fields,
  }
}

/**
 * The alerts file `pipeline/export_weather_alerts.py` writes - with no alert
 * on anywhere unless `alerts` says otherwise, the quiet state being the
 * ordinary one.
 *
 * @param {{ fetchedAt: Date, alerts?: Record<string, unknown>[] }} options
 */
export function weatherAlertsDocument({ fetchedAt, alerts = [] }) {
  return {
    payload: 'weather_alerts',
    schema: 1,
    source: 'National Weather Service, api.weather.gov/alerts/active',
    credit: 'National Weather Service',
    fetched_at: fetchedAt.toISOString().slice(0, 19) + 'Z',
    generated_at: fetchedAt.toISOString().slice(0, 19) + 'Z',
    release: 'fixture',
    alerts,
    unknown_zones: [],
  }
}

// Which square a point is in: client/src/lib/nbmGrid.ts's arithmetic, copied
// because a recipe runs in Node and cannot import TypeScript.
// src/test/weatherFixture.test.ts holds the two to the same answers.
const DEG = Math.PI / 180
const N = Math.sin(25 * DEG)
const F = (Math.cos(25 * DEG) * Math.tan(Math.PI / 4 + (25 * DEG) / 2) ** N) / N
const R = 6371200
const RHO0 = (R * F) / Math.tan(Math.PI / 4 + (25 * DEG) / 2) ** N

export function nbmSquare(lon, lat) {
  const rho = (R * F) / Math.tan(Math.PI / 4 + (lat * DEG) / 2) ** N
  const theta = N * (lon + 95) * DEG
  const col = Math.floor((rho * Math.sin(theta) + 3272421.4573371694) / 2539.703)
  const row = Math.floor((3790842.106035436 - (RHO0 - rho * Math.cos(theta))) / 2539.703)
  return [row, col]
}

/** Every square a point inside the 1° cell named `cell` can fall in: the
 *  row and column range the cell's edges project to, sampled every
 *  hundredth of a degree so the curved parallels are followed. */
export function squaresCovering(cell) {
  const match = /^([ns])(\d{2})([ew])(\d{3})$/.exec(cell)
  if (match === null) return []
  const south = Number(match[2]) * (match[1] === 'n' ? 1 : -1)
  const west = Number(match[4]) * (match[3] === 'e' ? 1 : -1)
  let rowMin = Infinity
  let rowMax = -Infinity
  let colMin = Infinity
  let colMax = -Infinity
  for (let i = 0; i <= 100; i++) {
    const f = i / 100
    for (const [lon, lat] of [
      [west + f, south],
      [west + f, south + 1],
      [west, south + f],
      [west + 1, south + f],
    ]) {
      const [row, col] = nbmSquare(lon, lat)
      rowMin = Math.min(rowMin, row)
      rowMax = Math.max(rowMax, row)
      colMin = Math.min(colMin, col)
      colMax = Math.max(colMax, col)
    }
  }
  const squares = []
  for (let row = rowMin; row <= rowMax; row++) {
    for (let col = colMin; col <= colMax; col++) squares.push([row, col])
  }
  return squares
}

const HOUR_MS_ = 3_600_000

/**
 * Serve this fixture for every weather file the app asks for, for a recipe.
 *
 * The cell file carries the Lakes of the Clouds forecast at every square of
 * whichever cell is asked for, so the card shows weather at whatever
 * waypoint the recipe opens, and NOAA's run is two hours before the camera
 * runs - the typical age WEATHER.md §4 reasons a hiker in signal will see.
 * The alerts file is the quiet one, asked an hour ago.
 *
 * A fixture, so the forecast in the frame is not that waypoint's: the
 * recipe's caption has to say so.
 */
export async function serveWeather(page) {
  const now = Date.now()
  const cycle = new Date(Math.floor(now / HOUR_MS_) * HOUR_MS_ - 2 * HOUR_MS_)
  await page.route(/conditions\/weather\/([ns]\d{2}[ew]\d{3})\.json(\?|$)/, (route) => {
    const cell = /conditions\/weather\/([ns]\d{2}[ew]\d{3})\.json/.exec(
      route.request().url(),
    )[1]
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        weatherCellDocument({ cycle, squares: squaresCovering(cell), cell }),
      ),
    })
  })
  await page.route(/conditions\/weather_alerts\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        weatherAlertsDocument({ fetchedAt: new Date(now - HOUR_MS_) }),
      ),
    }),
  )
}
