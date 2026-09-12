// The one door onto a live day-hike draft, and the one budget it needs.
//
// WHY THIS IS A MODULE AND NOT A HELPER IN EACH SPEC. Three drives across two
// files reach step 2 the same way — "Edit the route" on a saved walk's card —
// and each carried its own copy of the wait. The copies agreed on 60_000,
// which was never a measurement: it came from e2e/data/longSpine.spec.ts,
// whose drives do not wait on the junction graph resolving a saved walk at
// all. When the whole data suite runs, they do not agree with reality.
//
// MEASURED 2026-09-11 against release 2026-09-10, the identical drive:
//
//   one file alone, one worker          the door inside a few seconds
//   the whole data suite, two workers   past 60_000, twice, in different
//                                       files on different runs
//
// Both failures were timeouts on the wait rather than red assertions — the
// worst kind of CI red, because it reports nothing about the app and
// everything about how many tests were sharing one origin.
//
// So the budget lives here, once, and every drive that needs this door takes
// it from here. That is the same "one home" argument the rest of this suite
// makes about fixtures: a number copied into three files is three numbers.

import { expect, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode } from './seed'
import { writeIDBEntries } from './idb'
// Untyped on purpose: a shot fixture is plain JavaScript, and its shape is the
// app's contract with IndexedDB rather than a type this module restates.
import { FOLLOWED_HIKE_STORE } from '../../preview-shots/following-a-day-hike.mjs'

/** Where the day-hike store lives in IndexedDB. */
export const DAY_HIKES_KEY = 'ourhike:day-hikes'

/**
 * How long the junction graph may take to resolve a saved walk before the
 * wait is a real failure rather than a busy machine.
 *
 * 150_000 against the measurements above: comfortably past what contention
 * costs, and still short enough that a graph which never arrives fails inside
 * a file's own budget rather than at the runner's. A file using this needs
 * `test.describe.configure({ timeout: 300_000 })` or more, because
 * playwright.config.ts's data-mode per-test ceiling is 90_000.
 *
 * `@unvalidated` as a claim about what a HIKER waits for — it is a budget for
 * a test runner, not a finding about the app's load time, which nothing here
 * has measured.
 */
export const GRAPH_READY_MS = 150_000

/**
 * Boot in day mode with the saved walk on the phone, open its card, and take
 * "Edit the route" — which loads the walk's legs into step 2 and puts the
 * builder in the state a hiker reaches by tapping.
 *
 * WAITED ON RATHER THAN COUNTED: the card prints its cached figures long
 * before the graph lands, and the door appears only once the walk has been
 * placed on live tread — the same trap
 * preview-shots/following-a-day-hike.mjs records for its own Follow door.
 *
 * The walk is e2e/data/followMode.spec.ts's, for the reason that spec imports
 * it rather than inventing one: its ends were measured against published
 * tread, and a second fixture would be a second answer to which walk
 * resolves. Callers assert whatever step 2 owes them next.
 */
export async function editTheSavedRoute(page: Page): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, 'day')
  await writeIDBEntries(page, [[DAY_HIKES_KEY, FOLLOWED_HIKE_STORE]])
  await page.goto('/')
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: /Ramapo-Dunderberg to Timp-Torne/ }).click()
  const edit = page.getByRole('button', { name: 'Edit the route' })
  await edit.waitFor({ timeout: GRAPH_READY_MS })
  await edit.click()
  await expect(page.getByRole('button', { name: /Use this route/ })).toBeVisible({
    timeout: GRAPH_READY_MS,
  })
}

/** The saved walk's stops, read off the fixture rather than copied beside it. */
const SAVED_WALK_STOPS: ReadonlyArray<readonly [number, number]> = (
  FOLLOWED_HIKE_STORE as unknown as {
    hikes: Array<{ segments: Array<Array<{ coord: [number, number] }>> }>
  }
).hikes[0].segments
  .flat()
  .map((stop) => stop.coord)

/**
 * A camera on the walk itself, for a spec that has to touch the drawn line.
 *
 * WHY THIS EXISTS, and it is the interesting part. The builder does not open
 * on the route it is editing — it opens on the camera the map already had,
 * which is the whole corridor. A 2.9 mi walk drawn at corridor zoom is a mark
 * a few tens of pixels long, and whether a sweep of the frame lands on it is
 * luck rather than a property of the app.
 *
 * MEASURED 2026-09-11 against release 2026-09-10, the same 17-by-17 sweep of
 * the map's own box, one run each:
 *
 *   the camera the builder opens on   0, 0, 0, and once 1, of 289 points
 *   seeded here at z13 / z14 / z15    16 / 20 / 22 of 289
 *
 * So the fix for "the sweep found nothing" was never a denser grid or a
 * longer wait — a 16 px scan of 1,974 points found nothing either, because
 * nothing was there to find. It was putting the camera where the line is.
 *
 * The centre is the midpoint of the stops' own bounding box, so a fixture
 * whose ends move takes the camera with it. z14 rather than a rounder number:
 * web mercator at this latitude is 156543.03 × cos(41.28°) / 2^z ≈ 117,700 /
 * 2^z m/px, so z14 is 7.2 m/px and the stops' 2.9 km separation draws about
 * 400 px across the 682 px frame this project gives the map — the whole walk
 * inside the frame, with room for the tread to wander off the straight line
 * between its ends, which it does.
 *
 * `@unvalidated` as anything about a hiker: this is where a TEST looks, not a
 * claim that the builder should open here. Whether it should is
 * #1404 — The route builder opens on the corridor rather than on the route it
 * is editing.
 */
export const SAVED_WALK_CENTER: readonly [number, number] = [
  (Math.min(...SAVED_WALK_STOPS.map((c) => c[0])) +
    Math.max(...SAVED_WALK_STOPS.map((c) => c[0]))) /
    2,
  (Math.min(...SAVED_WALK_STOPS.map((c) => c[1])) +
    Math.max(...SAVED_WALK_STOPS.map((c) => c[1]))) /
    2,
]

/** @see SAVED_WALK_CENTER for why 14. */
export const SAVED_WALK_ZOOM = 14
