// The downloads window — since #1103 the account it keeps, and since #558
// the stretch under the hike.
//
// The window gained two lists in #1103 this recipe exists to photograph: each
// sheet's card breaks into its named archives, and the vector trail data —
// the line, the waypoints, the elevation, the nearby network — gets a
// stated row each, measured off the store. In the preview no archives exist
// (#1024), so every row honestly reads its absent state — "not here yet —
// arrives with signal", "not downloaded" — which is itself the behaviour
// worth a photograph: absence stated, never a blank.
//
// Under the hiking sheet's card now sits the second decision this window
// carries (#558): just the stretch under the hiker's planned hike, priced
// against the pieces not yet here, with the whole trail still the button
// above it. In the preview no hike is set, so the card says where a hike
// gets set instead of pricing one — and on a build whose bucket carries no
// cells (production holds none while they are UA-only) that is the honest
// frame too, since there would be nothing to price. The priced offer, the
// transfer, and the dashed seam the map draws past a held cell all need a
// stretch on the phone, which no preview can hold; the in-flight sheet
// states need a real transfer for the same reason.
export const caption =
  'The downloads window — every asset accounted for, and the stretch under the hike (#1103, #558)'
export const alt =
  'The downloads window over the map: a "Trail data on this phone" list stating each artifact — trail line, waypoints, elevation profile, nearby trails network — with its measured size or a stated absence, then the hiking sheet card with its archive breakdown, and beneath it a "Just the stretch you’re walking" section saying where the hike is set'

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

  // The stretch card is the last thing on the hiking sheet's panel; bring the
  // whole section into frame by the region that IS it - not its title, which
  // scrolled to the bottom edge leaves the sentence under it below the fold -
  // so the shot survives the card above it growing and the frame ends on this
  // pull request's subject, said in full.
  await page
    .getByRole('region', { name: /stretch you’re walking/i })
    .scrollIntoViewIfNeeded()
}
