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
