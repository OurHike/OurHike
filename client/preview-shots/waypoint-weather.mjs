// NOAA's forecast on a waypoint's card, pulled open (#1056 build step 3).
//
// THE BAND THIS CHANGE ADDS: "Weather here", between Conditions and About -
// the forecast's age, the NWS warnings line, six hours with sun or moon and
// cloud, and five days as rows with each day's low and high drawn against the
// week's. The peek's one line is waypoint-weather-peek.mjs.
//
// THE FORECAST IN THE FRAME IS A FIXTURE, AND THE CAPTION SAYS SO. The preview
// builds against production's data, which publishes no weather until the
// release train promotes it (features/WEATHER.md §7), so the card there would
// correctly show none. `serveWeather` answers the app's weather requests with
// NOAA's real 2026-09-30 forecast for the Lakes of the Clouds square, laid on
// every square of whichever cell is asked for and dated two hours before the
// camera runs. So the numbers are real weather, at the wrong place.
//
// Reached the way waypoint-conditions.mjs reaches the opened card, for its
// reasons: a search for the category rather than a named shelter, and a
// pull by test id. TWO HONEST FRAMES, as there: where the POI artifacts
// arrive, the card; where they do not, Search saying "Nothing here by that
// name".
//
// Nobody's data is in the frame: no account, no notes seeded, no location
// fix, and a forecast is NOAA's.

import { serveWeather } from './fixtures/weather.mjs'

export const caption =
  'The opened card’s “Weather here” band (#1056) — the forecast is a fixture: real NOAA numbers, served for whichever shelter the search opens'
export const alt =
  'Either a waypoint card pulled open for a shelter and scrolled to a “Weather here” band: a line saying when the forecast is from and when it was checked, a line saying NWS had no alerts for the spot, six hourly columns with a sun-and-cloud icon, a temperature and a chance of rain, a wind line, and five day rows each with a chance of rain, a low, a bar and a high; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

export const wait = 5000

export default async function drive(page) {
  await serveWeather(page)

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByRole('searchbox', { name: 'Search the downloaded map' }).fill('Shelter')

  const first = page
    .getByRole('button')
    .filter({ hasText: /Shelter/ })
    .first()
  await first.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await first.count()) === 0) return
  await first.click()

  const expand = page.getByTestId('poi-card-expand')
  await expand.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await expand.count()) === 0) return
  await expand.click()

  // The band is under the photograph and Conditions at 390x844, so scroll it
  // into frame - which waits for it, and so is the settle as well.
  await page
    .getByTestId('poi-card-weather')
    .scrollIntoViewIfNeeded()
    .catch(() => {})
}
