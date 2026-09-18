// What a spec seeds before its first navigation, or reload, to land on a
// screen without clicking through everything in front of it -
// features/FLOW_TESTING.md's IndexedDB-seed-and-reload idiom, applied to
// this app's actual keys.

import type { Page } from '@playwright/test'
import { writeIDBEntries } from './idb'

const PREFERENCES_KEY = 'ourhike:preferences'
const TAKEN_TRAIL_KEY = 'ourhike:taken-trail'
const HIKER_MODE_KEY = 'ourhike:hiker-mode'

/** Mirrors client/src/lib/hikerMode.ts's HIKER_MODE_VALUES. Not imported -
 *  these three keys are the wire contract with idb-keyval, which nothing
 *  here needs the rest of that module's logic to write. */
export type HikerMode = 'day' | 'long' | 'volunteer'

/**
 * Past first run and the download question - the state nearly every spec
 * wants to start from, since neither screen is usually the one under test.
 * Partial on purpose: `normalisePreferences()` (client/src/lib/preferences.ts)
 * merges whatever is stored over `DEFAULT_PREFERENCES`, so naming three keys
 * here cannot drift out of date with the forty-odd others - the same
 * reasoning client/src/test/appHarness.ts's `onboard()` and
 * client/scripts/screenshot.mjs's `skipFirstRun()` both already rely on.
 */
export async function seedPreferences(
  page: Page,
  overrides: Record<string, unknown> = {},
): Promise<void> {
  await writeIDBEntries(page, [
    [
      PREFERENCES_KEY,
      {
        onboarding_completed: true,
        download_choice_made: true,
        location_permission_requested: true,
        ...overrides,
      },
    ],
  ])
}

/** Sets the mode without going through the switch. The vitest equivalent
 *  (client/src/test/appHarness.ts) is `app.store.set(HIKER_MODE_KEY, 'long')`. */
export async function seedHikerMode(page: Page, mode: HikerMode): Promise<void> {
  await writeIDBEntries(page, [[HIKER_MODE_KEY, mode]])
}

/** A trail already taken from the map (client/src/lib/takenTrail.ts) - the
 *  plate, the profile and the chosen system all read it. Leave unseeded for
 *  the honest default: nothing taken, as on a fresh install. */
export async function seedTakenTrail(page: Page, trailId: string): Promise<void> {
  await writeIDBEntries(page, [[TAKEN_TRAIL_KEY, trailId]])
}

/**
 * A mile of latitude, near enough that a vertex index IS a mile marker on
 * the due-north synthetic centerline client/src/test/appHarness.ts also
 * builds (`centerlineGeoJSON`) - the same constant, so a fix seeded here
 * and a centerline seeded from that fixture agree on what "mile 5" means.
 */
export const MILE_LAT = 1 / 69.05

export function latOfMile(mile: number): number {
  return 39 + mile * MILE_LAT
}

/**
 * A real GPS fix, through Playwright's own geolocation - `context.setGeolocation`
 * and `context.grantPermissions`, not a stub. Unlike appHarness.ts's mocked
 * `navigator.geolocation.watchPosition`, a real browser context has no seam
 * to mock; this is the actual API, and it is what the app actually calls.
 */
export async function seedFixAtMile(
  page: Page,
  mile: number,
  longitude = -77,
): Promise<void> {
  await page.context().grantPermissions(['geolocation'])
  await page.context().setGeolocation({ latitude: latOfMile(mile), longitude })
}

/**
 * A second page in the same browser context, booted from nothing.
 *
 * THE RELOAD TRAP THIS EXISTS FOR. `writeIDBEntries` registers its seed
 * through `page.addInitScript`, which Playwright re-runs on every future
 * navigation of that page - and each entry is a whole-record `put`, not a
 * merge. So `page.reload()` rewrites the seeded preferences object over
 * whatever the app has saved since, and a spec asserting that a choice
 * survived a restart would be asserting that the seed survived instead: it
 * would fail with the feature working, which is the worst kind of test.
 *
 * A sibling page shares the context's origin and therefore its IndexedDB,
 * and carries none of this page's init scripts - so it is the app booting
 * cold onto the store as the hiker left it, which is the thing a "survives a
 * restart" claim is actually about. The caller closes it, or the context
 * does at the end of the test.
 */
export async function bootFreshPage(page: Page): Promise<Page> {
  const second = await page.context().newPage()
  await second.goto('/')
  return second
}

/**
 * The view the hiker last had, which is the app's own memory of it -
 * lib/cameraMemory.ts's `ourhike:camera`, in sessionStorage rather than
 * IndexedDB because it is "a memory of what the hiker is LOOKING AT, not a
 * preference".
 *
 * WHY A SPEC WRITES IT. The opening camera is the whole corridor, which sits
 * below map/poiLayers.ts's POI_PIN_MIN_ZOOM - and down there the app declines
 * to draw pins, no trail line is thick enough to tap, and the legend's
 * below-the-seam half never renders. Reaching any of that means a closer
 * camera, and the honest ways to get one are a wheel-zoom loop (measured
 * while writing e2e/mapChrome.spec.ts: twelve steps of -240 moved the scale
 * bar from 100 mi to 30 mi and never crossed the seam) or this, which is the
 * state a hiker is in on any reload while looking at a place.
 *
 * Seeded state, not an injected route: the entrance is still a tab tap, and
 * no navigator state is written (features/FLOW_TESTING.md, "Not a router").
 */
export async function seedCamera(
  page: Page,
  center: readonly [number, number],
  zoom: number,
): Promise<void> {
  await page.addInitScript(
    ([seenCenter, seenZoom]) => {
      sessionStorage.setItem(
        'ourhike:camera',
        JSON.stringify({ center: seenCenter, zoom: seenZoom }),
      )
    },
    [center, zoom] as const,
  )
}

/**
 * A window onto the A.T. near the Smokies, above the pin seam - nobody's
 * location, and a stretch every release since the first has carried.
 *
 * NEAR the trail rather than ON it, which is worth the word: measured
 * 2026-09-11 against release 2026-09-10, the centerline crosses this frame
 * about nine tenths of the way across it rather than through its middle, so a
 * spec that wants to touch the line has to look for it (e2e/data/mapSheets.ts
 * carries that measurement and the sweep built on it). The point was picked
 * for the pin seam, not for the geometry.
 *
 * Shared because two specs want the same window onto the same data and a
 * second copy would be two answers to "where does the suite look".
 */
export const ON_THE_TRAIL: readonly [number, number] = [-83.4821, 35.6012]
export const ABOVE_THE_SEAM_ZOOM = 12.5

/**
 * The same window, BELOW the pin seam — where a tap on the A.T. asks who
 * maintains it instead of what the line is (chrome/tappedLinePanel.tsx: "one
 * tap asks one question, and which question depends on the zoom").
 *
 * NOT "where the map stops drawing waypoints" any more (#1585 — A hundred-mile
 * resupply carry fits a phone at z8, and the map draws no waypoint until z9):
 * z8 is inside the planning band, so the A.T.'s shelters, water and resupply
 * towns draw here as pins and dots, and the legend's sentence here is the
 * band's ("Shelters, water and resupply towns show at this zoom; the rest
 * appear from a closer zoom."). The seam and the club-sheet rule are exactly
 * where they were, which is why the camera stays at 8 rather than dropping
 * under the band's 7.5 floor: the sweep in e2e/data/mapSheets.spec.ts now
 * proves a line tap still finds the club with band pins around it, and it
 * closes a waypoint card it opens on the way. A camera below the band would
 * have kept the old sentence true and the measurement below valid at the cost
 * of never testing that.
 *
 * 8 rather than 8.9: `map/poiLayers.ts`'s `POI_PIN_MIN_ZOOM` is 9 and
 * `belowSeam` is `zoom < POI_PIN_MIN_ZOOM`, so anything under 9 is below the
 * seam — but a value that sits on the boundary would turn a one-line change to
 * that constant into a mystifying spec failure rather than an obvious one.
 *
 * Measured 2026-09-11 against release 2026-09-10, sweeping the whole frame
 * below the header at this camera: 21 of 247 taps open the club sheet and 28
 * open a side trail's line sheet, so the A.T. is comfortably findable here —
 * far more so than at ABOVE_THE_SEAM_ZOOM, where the same sweep finds the line
 * at one point only. (Measured before the band drew here; some of those 247
 * taps now open a waypoint card first, which the sweep closes and passes
 * over, so the club count still holds as a floor and not as the exact
 * figure.)
 */
export const BELOW_THE_SEAM_ZOOM = 8
