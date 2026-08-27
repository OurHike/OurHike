// Today's foot: report a problem, and say thanks, at equal width (#1133).
//
// The third screen this change touches, and the one where the argument is
// entirely visual. Reporting a problem and thanking a maintainer are two sides
// of one relationship with the crew - the volunteer card sits directly above
// this row - and until now Today had one button reading "Note something for
// the crew" while saying thanks was the seventh row inside the problem picker,
// under a list of hazards.
//
// WHAT TO LOOK AT IS THE SYMMETRY, and it is the kind of claim a sentence in a
// pull request body cannot make. Two solid fills, the same size, the same
// width: blaze orange and forest green. An outline "Say thanks" beside a
// filled "Report a problem" would say, in the only language a button has, that
// thanking is the afterthought - and that is what a picture settles and prose
// does not.
//
// The blaze orange is also #1132's, one rung darker than the brand hue,
// because the shipped one carried a label at 4.14:1. This row is what made
// somebody measure it.
//
// WHAT THIS FRAME WILL NOT SHOW is the outbox line under the buttons - "2
// notes waiting to send", tappable, opening the volunteer page. It renders
// only when something is queued, and it hides at zero on purpose (no "0 notes
// waiting to send" - an empty outbox is not news). Seeding a report to make it
// appear would mean filing one, which `report-filed.mjs` already photographs
// on its own terms. Said here so nobody reads its absence as a missing
// control.
//
// No trail data needed. No account, no location fix, and nothing anybody
// filed.

export const caption =
  'Today’s foot — both halves of the crew relationship, at equal weight (#1133)'
export const alt =
  'The foot of the Today screen: a two-button row of equal width, a solid blaze-orange “Report a problem” beside a solid forest-green “Say thanks”, above the line “Everything here works with no signal.”'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Today' }).click()

  // Scrolled to by the pair itself rather than by an offset: Today's column
  // grows and shrinks with what the phone knows - a download card, the places
  // passed today, the volunteer card - so how far down this row sits is not a
  // number this recipe can hold. `scrollIntoViewIfNeeded` waits for the
  // element too, so this is the settle as well as the scroll.
  await page.getByRole('button', { name: 'Say thanks' }).scrollIntoViewIfNeeded()
}
