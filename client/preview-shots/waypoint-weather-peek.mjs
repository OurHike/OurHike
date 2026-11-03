// NOAA's forecast on a waypoint's peek (#1056 build step 3).
//
// One line under the chips - a sun or moon and cloud, today's high and low,
// the chance of rain or snow and how old the forecast is - which is frame A of
// the mock the maintainer chose over a peek without it (poll, 2026-09-30), and
// the pull renamed "Notes, weather & details". The opened band is
// waypoint-weather.mjs, which explains the fixture: real NOAA numbers for the
// Lakes of the Clouds square, served for whichever shelter the search opens,
// because production publishes no weather yet.
//
// Reached as waypoint-quick-answers.mjs reaches the peek, and deliberately not
// opened.

import { serveWeather } from './fixtures/weather.mjs'

export const caption =
  'A waypoint’s peek with its forecast line (#1056) — the forecast is a fixture: real NOAA numbers, served for whichever waypoint the search opens'
export const alt =
  'Either a waypoint card peeking over the map, with a forecast under its name - a sun-and-cloud icon beside “Today” with a high, a low and a chance of rain, and under them “NOAA forecast from” and the time - above a “Weather & details” or “Notes, weather & details” expander; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

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

  await page
    .getByTestId('poi-card-weather-line')
    .waitFor({ timeout: 15000 })
    .catch(() => {})
}
