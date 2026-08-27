// The opened card's "Say something back" band (#1122).
//
// THE SECOND STATE, AND IT IS GENUINELY A SECOND ONE. waypoint-quick-answers.mjs
// photographs the peek, which carries two answers; this carries the other half
// of the change, none of which is reachable from that shot:
//
//   - four answers rather than two, with Trash where Full used to be
//   - the report entry at a control's weight, asking "Something wrong here?"
//     over a hint line, where it was a 12px grey hairline pill before
//
// The report entry is the part that most needs a picture. "More visible" is a
// claim about weight against everything beside it, and weight is exactly what
// a sentence in a pull request body cannot convey.
//
// Reached the same way as the peek and for the same reasons - see that recipe
// for why this searches a category rather than naming a shelter, and why a
// canvas tap is not an option. It then does the one thing that recipe
// deliberately does not: pulls the card open.
//
// TWO HONEST FRAMES, as there too. Where the POI artifacts arrive, the picture
// is the opened card; where they do not, it is Search saying "Nothing here by
// that name". The caption names both, because photograph-preview.mjs reads it
// before the drive runs (#1058).
//
// Nobody's data is in the frame: no account, no notes seeded, no location fix.
// The history list above the band renders whatever conditions/notes.json holds
// for this shelter, which is the same anonymous published artifact every hiker
// reads - reporter_type and a date, never a name (FIELD_NOTES.md §6).

export const caption =
  'The opened card — four answers, and a report entry that stopped whispering (#1122)'
export const alt =
  'Either a waypoint card pulled open for a shelter, scrolled to a “Say something back” band with four answer buttons — a green rotating good word, an orange “Damaged”, “Trash” and “Not here” — above a full-width bordered control reading “Something wrong here?” over “Blowdown, damage, trash — report it”; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

export const wait = 5000

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByRole('searchbox', { name: 'Search the downloaded map' }).fill('Shelter')

  const first = page
    .getByRole('button')
    .filter({ hasText: /Shelter/ })
    .first()
  await first.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await first.count()) === 0) return

  await first.click()

  // The pull that opens the card, by its test id rather than by the label -
  // the expander reads "Notes & details" only where the type carries
  // conditions and plain "Details" otherwise (chrome/PoiCard.tsx), and a
  // locator that encoded the promise would break on the first waypoint that
  // does not make it.
  const expand = page.getByTestId('poi-card-expand')
  await expand.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await expand.count()) === 0) return
  await expand.click()

  // Scroll the band into frame rather than photographing the top of the sheet.
  // The opened card leads with its heading, the photograph and the history, so
  // at 390x844 the answers and the report entry are under the fold - and a
  // picture of the card's head says nothing about either.
  //
  // By the report entry rather than by the answers: it is the LOWER of the two
  // and they are stacked, so reaching it brings the answer grid with it. Same
  // rule legend.mjs follows for its two rows, and the same reason -
  // `scrollIntoViewIfNeeded` waits for the element, so this is the settle as
  // well as the scroll.
  await page
    .getByTestId('poi-card-report-here')
    .scrollIntoViewIfNeeded()
    .catch(() => {})
}
