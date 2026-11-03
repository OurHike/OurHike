// Today's foot: the named door for reporting, and the one beside it (#1438,
// D15; the pair is #1133's).
//
// WHAT CHANGED, AND WHY A PICTURE SETTLES IT. Reporting was reachable three
// ways and the review's audit counted none of them as a door: a long press
// nobody is told about, two taps into More, and a button that the day-hike
// home did not draw at all. Frame 9b gives it a named row with a line saying
// what a report is for and that it works with no signal - which is the
// commonest reason somebody on a ridge does not file one.
//
// WHAT TO LOOK AT IS THAT THE TWO ARE STILL THE SAME ROW. features/
// SAYING_THANKS.md commits this screen to "the same width and the same
// weight", because "an outline button beside a filled one would say, in the
// only language a button has, which of the two is the afterthought". Giving
// Report an eyebrow and a sub-line is exactly the change that could have
// broken that quietly, and a sentence in a pull request body cannot make the
// claim. Two rows, one chip, one chevron each; only the words differ.
//
// Photographed in long-hike mode because that is where both rows draw. The
// report row is in EVERY mode since #1438; the thanks row keeps the day-hike
// exception the maintainer set on 2026-09-10, on the argument that a day
// hiker's home should not accumulate crew sections.
//
// WHAT THIS FRAME WILL NOT SHOW is the outbox line under the rows - it
// renders only when something is queued and hides at zero on purpose, and
// `report-filed.mjs` photographs it on its own terms. Said here so nobody
// reads its absence as a missing control.
//
// No trail data needed. No account, no location fix, and nothing anybody
// filed.

export const caption =
  'Today’s foot — a named door for reporting, and saying thanks at the same weight (#1438)'
export const alt =
  'The foot of the Today screen: a small heading “found something out here?” above two stacked rows of the same width and weight, each a card with a chevron — “Report a problem / A dry spring, a blowdown, a trail that is shut. Works with no signal.” and “Say thanks / Say thanks to whoever keeps it up. It reaches the crew, never a scoreboard.” — above the line “Everything here works with no signal.”'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByRole('radio', { name: 'Long hike' }).click()

  // Scrolled to by the pair itself rather than by an offset: Today's column
  // grows and shrinks with what the phone knows - a download card, the places
  // passed today, the crews out today - so how far down these rows sit is not
  // a number this recipe can hold. `scrollIntoViewIfNeeded` waits for the
  // element too, so this is the settle as well as the scroll.
  await page.getByRole('button', { name: /^Say thanks/ }).scrollIntoViewIfNeeded()
}
