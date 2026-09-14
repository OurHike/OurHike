// In view (#1373, frame 12a): what the map is drawing, as a list.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The header's "In view · N" door and the
// sheet it opens over the map: the same points the legend counts, named one
// PoiRow each in mile order, with "N away" only where the hiker's own mile
// and the waypoint's are both known - the preview has no fix, so no row
// says "away" here, honestly. A tap on a row opens the waypoint card a pin
// would.
//
// GUARDED, because the door exists only once the map is drawing waypoints:
// the preview's bucket may or may not serve them at the opening view, and
// a door that is absent is the design rather than a failure - so the drive
// waits for it and stops on the bare map if it never comes, which the
// caption says.
export const caption =
  'In view, from the map’s header — the waypoints the map is drawing, named and in mile order; or the map with no waypoints drawn, and no door (#1373, frame 12a)'
export const alt =
  'Either the map with a sheet over its lower third headed "In view · N of M", listing waypoints as rows with the map’s own pin glyph, a name and a mono line reading type and mile; or the bare map with the header’s Legend and Search buttons and no In view door'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
  const door = page.getByRole('button', { name: /^In view, \d+/ })
  await door.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await door.count()) === 0) return
  await door.click()
  await page.getByRole('dialog', { name: 'In view' }).waitFor()
}
