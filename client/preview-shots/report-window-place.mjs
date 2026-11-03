// The report window's location sheet with a GPS fix to offer (#1563) - the
// frame report-window.mjs cannot show, because that camera has no fix, and
// report-window-refused.mjs cannot either, because a refused tap has none.
//
// WHAT THE PICTURE IS FOR. Two of the picker's four answers exist only with a
// fix, and prose cannot make either claim:
//
//   - "Where you are", with the fix's RADIUS AND AGE printed beside it -
//     "±16 ft · just now" - so a hiker can see a poor fix for what it is
//     before filing under it, and so the row is read as a measurement with
//     a stated uncertainty rather than as a dot. That line is the visible
//     end of the wire's `location_accuracy_m` and `location_fix_age_s`.
//   - a NAMED PLACE first, above it, with how far away it is: the preferred
//     answer, because a report at a shelter is a report a moderator can act
//     on without a map. This half depends on the release's waypoints having
//     arrived, which they do in CI (the origin fix .claude/skills/pr-screenshot
//     records) and do not in a sandbox - so the frame is honest in both
//     states, and the caption names both.
//
// THE FIX IS SYNTHETIC. Playwright's own geolocation, set to a point on the
// A.T. that e2e/support/seed.ts already uses as ON_THE_TRAIL (near Clingmans
// Dome in the Smokies), and granted to the page before it boots. It is the
// same coordinate every run and belongs to nobody: the rule against a real
// location fix in a shot is about somebody's location, and this is a fixture.
//
// Driven from Today's own door. The header states the fix; "Change" opens the
// sheet over the window (reporting/LocationSheet.tsx, the maintainer's steer
// of 2026-09-17), which is the thing this frame is for.

import { IDB } from '../scripts/screenshot.mjs'

export const caption =
  'The location sheet with a fix (#1563), opened by Change over the report window: a named place nearby first (when the release’s waypoints are on the phone), then “Where you are” with the fix’s radius and age, then the map. A poor fix reads as a poor fix before anybody files under it.'
export const alt =
  'A second, smaller dialog centred over the dimmed report window, its dark header reading “Where is this?” with a “Done” button at the right. Inside: a small heading “A named place” over a “Find a place by name” box and, when the phone holds the waypoints, a short list of places nearest first, each with how far away it is and its mile; then a “Where you are” row reading “±16 ft · just now”; then a “Mark it on the map ›” row. Behind the sheet, the report window’s header states “Where you are” or a trail mile with a “Change” control, and its tiles are dimmed.'

export default async function drive(page) {
  await page.context().grantPermissions(['geolocation'])
  // A radius as well as a point: Playwright defaults `accuracy` to 0, and
  // ±0 ft is the one claim no phone has ever made. Five metres is an ordinary
  // clear-sky fix and reads as “±16 ft”.
  await page
    .context()
    .setGeolocation({ latitude: 35.6012, longitude: -83.4821, accuracy: 5 })

  // THE WATCH ONLY STARTS ONCE LOCATION IS ALLOWED. The runner's
  // `skipFirstRun` writes `onboarding_completed` alone, and the first-run
  // step that would have asked for location never ran - so the preference
  // the watch is gated on (`location_permission_requested`, App.tsx) is
  // written here the same way, and the page booted again to read it. An
  // init script registered after the runner's own, so on the reload it
  // writes last; a whole-record put, like the runner's, so the merge is
  // normalisePreferences()'s over DEFAULT_PREFERENCES rather than ours.
  await page.context().addInitScript(
    ({ database, store, key }) =>
      new Promise((done, fail) => {
        const open = indexedDB.open(database)
        open.onupgradeneeded = () => open.result.createObjectStore(store)
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const write = open.result
            .transaction(store, 'readwrite')
            .objectStore(store)
            .put(
              {
                onboarding_completed: true,
                download_choice_made: true,
                location_permission_requested: true,
              },
              key,
            )
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    IDB,
  )
  await page.reload()

  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByRole('button', { name: /^Report a problem/ }).click()
  await page.getByRole('dialog', { name: 'What did you find?' }).waitFor()

  // The fix has to have arrived for the frame to be the one described: the
  // place line stops saying "No location yet" the moment it does.
  await page
    .getByTestId('report-anchor')
    .filter({ hasNotText: 'No location yet' })
    .waitFor()

  await page.getByTestId('report-change-anchor').click()
  await page.getByTestId('location-fix').waitFor()
}
