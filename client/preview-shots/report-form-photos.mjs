// The report form, rebuilt: several photos and a location a hiker can
// correct (#1439, D16/D17, frame 9f).
//
// WHAT THE PICTURE IS FOR. Two changes here are shape rather than text, and
// prose cannot make either claim.
//
// THE PHOTO FIELD IS A ROW OF TILES. It was one `<input type="file">` behind
// one `photo` state plus a `livePick` ref (#657) whose only job was to stop a
// slow first pick overwriting a fast second one - a correct fix for a shape
// that should not have existed. With a tile each, nothing can land on top of
// anything, and a failure costs its own tile while the rest stay attached.
// A blowdown is three trunks and one photo rarely shows it.
//
// THE LOCATION LINE HAS A WAY OUT OF ITSELF. `describeLocation` has exactly
// three answers and had no way to change any of them, so a hiker who walked
// on before filing could not say where the tree actually is. "Change" drops a
// crosshair on the map and names the mile before it is kept.
//
// Driven to "Something unsafe happened" because it is one of the two rows
// that open the form rather than filing on a tap (reporting/categories.ts's
// `filesOnTap`) - the six tiles file immediately, which is #1133's whole
// point and leaves nothing to photograph.
//
// WHAT THIS FRAME WILL NOT SHOW is an attached thumbnail: a file pick needs a
// file, and the four things that must never appear in a shot include anybody's
// photos. The empty dashed tile is the control; the summary line appears
// beside it once something is attached.
//
// No trail data needed. No account - the sign-in gate is at SEND, not here,
// which is itself the decision frame 9e records.

// TOUCHED BY #1563: the location line and the "Where was this?" field are the
// shared picker's now (reporting/LocationPicker.tsx). With no fix the line
// reads "No location yet" with Done beside it, because the picker is open
// under it - a named place to find by name, the map row, and the words field
// - and Send is refused until one of them has placed the report.

export const caption =
  'The report form — a tile per photo, and a place you can correct or give in words through the same picker the window uses (#1439, #1563)'
export const alt =
  'The report form headed “Something unsafe happened”: a Note textarea, then a “Photos” field showing a single dashed square tile with a plus and “Add a photo”, then a row reading “No location yet” with a “Done” control beside it and, under it, the location picker — a “Find a place by name” box, a “Mark it on the map ›” row, and “Or say where in words” over a text box with the hint “A landmark, a road, a shelter you passed — however you would say it to somebody. It travels as your words; nobody turns it into a pin.” — and “Save to outbox” and “Cancel” at the foot.'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Today' }).click()

  // The named door, by the words a hiker reads rather than a test id - a
  // prefix because the row's accessible name carries its own sub-line.
  await page.getByRole('button', { name: /^Report a problem/ }).click()
  await page.getByRole('dialog', { name: 'What did you find?' }).waitFor()

  // One of the two heavy rows, and the one that opens a form: a closure
  // leaves this flow for its own screen, and the six tiles file on a tap.
  await page.getByRole('button', { name: /Something unsafe/ }).click()

  // Waited on by the thing the shot is about rather than by a timeout.
  await page.getByRole('heading', { name: 'Something unsafe happened' }).waitFor()
  await page.getByLabel(/add a photo/i).scrollIntoViewIfNeeded()
}
