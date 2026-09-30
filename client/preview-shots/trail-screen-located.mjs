// The trail screen with the hiker on it (#1581): the mark that replaced
// MapLibre's stock blue dot, photographed where it has to be found - among
// the pins at the seam.
//
// A SEPARATE RECIPE RATHER THAN A TOUCH ON trail-screen.mjs, against
// README.md's "reuse one by touching it", and for the reason that rule
// allows: the standing shot is the opening camera with nothing taken and no
// fix, and it must stay that - it answers "does the app still come up". This
// frame needs a fix, location switched on, and the camera brought in by the
// locate button, none of which the standing shot may do.
//
// THE FIX IS A FICTIONAL HIKER AT A REAL, PUBLIC PLACE - a vertex of the
// 1777 trail's published centerline in Harriman State Park, the same point
// following-a-day-hike.mjs stands its hiker on, whose header carries the
// measurement (0.8 ft off the published tread, 2026-09-04). Never a real
// location fix: .claude/skills/pr-screenshot/SKILL.md's list forbids one, and
// a published trail line is the app's own public geometry, nobody's position.
//
// LOCATION THROUGH THE SWITCH RATHER THAN THE STORE, for the reason
// today-desktop.mjs gives: the runner's skip-first-run init script rewrites
// the preferences record on every navigation, so a seeded
// `location_permission_requested` is gone by the time the app reads it. The
// switch is also the door a hiker uses.
//
// THE LOCATE BUTTON IS THE LAST TAP, and it is a claim this frame tests:
// Playwright resolves the button by its accessible name, which is "No GPS
// fix yet" until the watch delivers and LOCATE_LABEL after (map/mapChrome.ts
// renames it in setFixAvailable) - so the tap waits for the fix, and a build
// whose button never wakes up photographs the opening camera with no mark,
// which is the honest picture of that failure.

export const caption =
  'The hiker’s mark on the trail screen (#1581): a hollow reticle in the sheet’s own ink, a centre dot and four ticks, where MapLibre’s blue dot was — a fictional hiker on a real, public vertex of Harriman’s 1777 trail, the camera brought in to the pin seam by the locate button'
export const alt =
  'The map screen at the pin seam over Harriman State Park: a hollow dark ring with a centre dot and four short ticks marking the hiker on a trail line, waypoint pins around it, and the locate button in the bottom-right stack showing the same ring glyph'

/** The map at the seam has pins, lines and a badge to draw after the jump;
 *  following-a-day-hike.mjs measured six seconds as enough for this ground
 *  and twelve as no better. */
export const wait = 6000

/** A vertex of the 1777 edge - see the header. */
const FIX = { latitude: 41.27444, longitude: -73.9888 }

export default async function drive(page) {
  await page.context().grantPermissions(['geolocation'])
  await page.context().setGeolocation(FIX)

  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /safety & privacy/i }).click()
  const useMyLocation = page.getByRole('checkbox', { name: 'Use my location' })
  if (!(await useMyLocation.isChecked())) await useMyLocation.check()

  await page.getByRole('tab', { name: 'Map' }).click()
  // The name this button carries once there is a fix to centre on
  // (map/mapChrome.ts's LOCATE_LABEL); Playwright waits for it.
  await page.getByRole('button', { name: 'Center the map on me' }).click()
}
