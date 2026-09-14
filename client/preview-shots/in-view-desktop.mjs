// In view on a laptop (#1374 review): the legend rail's second face.
//
// WHY THIS IS A SECOND RECIPE AND NOT A SECOND WAIT IN THE FIRST ONE - the
// argument day-hike-builder-desktop.mjs makes. Above desktop.css's 900px
// breakpoint the list is not the phone's sheet reflowed; it is a different
// arrangement. The phone opens a sheet from the header's "In view · N" door
// over the lower third of the map. The desktop has no such door: the
// persistent legend's 17rem column carries a Legend / In view switch at its
// head, and In view is that column's other face - the same rows, the same
// card on a tap, the map keeping every pixel it had.
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the list lives in the rail and not
// over the sidebar, the journal or the legend - which is where the phone's
// sheet sat on a desktop before the review - and that switching faces
// changes nothing about the map beside it.
//
// GUARDED like in-view.mjs: the switch reads a count, and a preview whose
// opening view draws no waypoint shows "In view · 0" and the honest empty
// sentence, which is the design rather than a failure.
//
// Nobody's data is in the frame: no account, no saved hikes, no fix.
export const caption =
  'In view on a laptop — the legend rail’s second face, switched at the column’s head, the map untouched beside it (#1374 review)'
export const alt =
  'A wide browser window with the OurHike sidebar down the left, the map filling the middle, and a column down the right headed by a two-way switch reading Legend and In view with In view selected, listing the waypoints the map is drawing as rows with a pin glyph, a name and a mono line reading type and mile - or the same column with "In view · 0" and a sentence saying nothing the map draws is in view'

// The wide layout is the entire subject.
export const desktop = true

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
  const face = page.getByRole('tab', { name: /^In view · \d+/ })
  await face.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await face.count()) === 0) return
  await face.click()
  await page.getByRole('region', { name: 'In view' }).waitFor()
}
