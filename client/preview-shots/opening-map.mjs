// The opening camera, now that it is the trails and not the waypoints (#1135).
//
// Two halves of one decision are photographable here. The dot rank stopping
// at the pin seam is unconditional: the whole-corridor view carries no
// waypoint stipple, and the legend's below-seam sentence reads "Waypoints
// appear from a closer zoom" over the counted grid. The other organizations'
// trails appearing AROUND the A.T. depends on the bucket this preview is
// built against serving `network_overview.geojson` — a 404 there is the
// older-release state and draws the A.T. alone, so which of the two maps
// this shot shows is itself evidence of whether the publish has run. The
// caption cannot know which; the alt text describes the artifact-present
// frame, which is the one this change exists to produce.
export const caption =
  'The opening map — every mapped trail and no waypoints below the seam (#1135); the NY network appears once network_overview.geojson is in the bucket this preview reads'
export const alt =
  'The whole-corridor opening view: the A.T. as a cased white line from Georgia to Maine with the other organizations’ trails ghosted around its New York miles, no waypoint dots anywhere, and the legend sheet reading “Waypoints appear from a closer zoom” above the waypoint grid'

export default async function drive(page) {
  // The map tab — the app opens on Today (#1054), and the camera this shot is
  // about is the one the map screen opens on: CORRIDOR_BOUNDS, no fix, no
  // stored camera in a fresh preview session.
  await page.getByRole('tab', { name: 'Map' }).click()

  // The legend over it, because the sentence is half the change: the panel
  // that used to say "show as dots at this zoom" now says the dots' absence
  // is the zoom's doing. The sheet opens at its top, where the sentence sits,
  // so no scroll is needed.
  await page.getByRole('button', { name: 'Legend' }).click()
}
