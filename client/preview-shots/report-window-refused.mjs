// The refused tap, and the sheet it opens (#1563) - the state that answers
// "what happens to a one-tap report from a phone with no fix", which used to
// be "it files with no location of any kind".
//
// WHAT THE PICTURE IS FOR. Two claims here are shape rather than text:
//
//   - THE SHEET IS A WINDOW OF ITS OWN over the report window (the
//     maintainer's steer of 2026-09-17: "the location should be exposed as a
//     2nd emergent window"), not a drawer inside the tile frame. The tiles
//     are dimmed behind it and the frame they sit in has not moved, which is
//     what keeps #1480's small-phone measurement true; report-window-small
//     photographs that frame, and this photographs what covers it.
//   - THE REFUSAL SAYS WHY. The sheet opens with the line "Say where this is
//     first" as an alert, not merely open: a tap that did nothing would be a
//     control that looks broken, which is the failure D10 forbids.
//
// What else is in it: the three answers a fixless phone can still give - a
// named place to find by name (the list is empty in a sandbox and short in
// CI, where the release's waypoints are on the phone), "Mark it on the map",
// and "Or say where in words" with its line about never becoming a pin.
// There is no "Where you are" row: a row that cannot do anything is not
// drawn. report-window-place.mjs is the same sheet with a fix.
//
// No trail data needed and nobody's data in it, for report-window.mjs's
// reasons: no account, no fix, no report seeded - the tap here is refused,
// so nothing is even written.

export const caption =
  'A tap with nothing to place the report at is refused, and the location sheet opens over the window saying so (#1563): a named place, the map, or your own words — and the tile files once one is given.'
export const alt =
  'A second, smaller dialog centred over the dimmed report window, its dark header reading “Where is this?” with a “Done” button at the right. Inside, an alert line reads “Say where this is first”, then a small heading “A named place” over a “Find a place by name” box, a “Mark it on the map ›” row, and “Or say where in words” over an empty text box with the hint “A landmark, a road, a shelter you passed — however you would say it to somebody. It travels as your words; nobody turns it into a pin.” Behind the sheet, the report window’s header reads “No location yet” and its six category tiles are dimmed.'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByRole('button', { name: /^Report a problem/ }).click()
  await page.getByRole('dialog', { name: 'What did you find?' }).waitFor()

  // No fix, so the tap is refused and opens the sheet instead of filing.
  await page.getByTestId('report-tile-blowdown').click()
  await page.getByRole('dialog', { name: 'Where is this?' }).waitFor()
  await page.getByRole('alert').waitFor()
}
