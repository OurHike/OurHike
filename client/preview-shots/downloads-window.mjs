// The downloads window — and since #1103 the account it keeps.
//
// The window gained two lists this recipe exists to photograph: each
// sheet's card breaks into its named archives, and the vector trail data —
// the line, the waypoints, the elevation, the nearby network — gets a
// stated row each, measured off the store. In the preview no release data
// and no archives exist (#1024), so every row honestly reads its absent
// state — "not here yet — arrives with signal", "not downloaded" — which is
// itself the behaviour worth a photograph: absence stated, never a blank.
// The in-flight states (the bar filling, "331 MB of 790 MB · arriving")
// need a real transfer no preview can run; the map's notice card needs the
// same, so this window is the one #1103 surface a camera can reach.
export const caption = 'The downloads window — every asset accounted for (#1103)'
export const alt =
  'The downloads window over the map: the hiking sheet card with its archive breakdown beneath it, and a "Trail data on this phone" list stating each artifact — trail line, waypoints, elevation profile, nearby trails network — with its measured size or a stated absence'

export default async function drive(page) {
  // The map first: the app opens on Today since #1054, and the legend —
  // whose foot holds the only door to the window from the map — floats
  // over the map screen.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()

  // The legend-foot link's accessible name is its state sentence
  // (chrome/DownloadsLink.tsx): "Choose what to download" on a phone with
  // nothing downloaded — which a preview always is.
  await page.getByRole('button', { name: /choose what to download/i }).click()

  // The trail-data account sits under the sheet cards; bring it into frame
  // by the thing that IS it, so the shot survives the cards above growing.
  await page.getByText('Trail data on this phone').scrollIntoViewIfNeeded()
}
