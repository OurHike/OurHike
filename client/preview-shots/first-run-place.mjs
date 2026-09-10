// First run's new second card, "Where do you hike?" (#1373, the design's
// frame 1b): the one step the rebuild adds to first run, so the shot is the
// whole evidence that it exists and reads as the design drew it - the
// question, the reason under it ("So we can put a trail in front of you
// before you turn location on"), a search field, and the sentence beneath
// saying where the answer is kept - with the hiker's settings, so it follows
// the account to a second device (the maintainer's decision of 2026-09-10,
// #1374). That sentence used to promise the phone and nothing else; a caption
// that still said so would describe a privacy promise the screen no longer
// makes, which is why this recipe changed when the copy did.
//
// WHAT THE FIELD RESOLVES AGAINST DECIDES WHAT THIS FRAME SHOWS. The rows
// come from `places.json`, which #1372 publishes; until that lands on the
// preview's bucket the field says so in words ("The list of places has not
// been published yet") and the skip is the way on. Either frame is the
// true one for the build being photographed, and the caption says which to
// expect rather than promising rows that may not be there.
//
// Driven from the first card's own primary, "Get set up", which is also the
// evidence that the card's buttons moved from Continue / Skip to the pair
// the design names.
export const caption =
  'First run, card 2 of 4 — "Where do you hike?", a place the hiker names, kept with their settings so a second device opens on it too — never a location fix (#1373, frame 1b; synced since #1374)'
export const alt =
  'The second first-run card over the hero photo: "Where do you hike?" with the sentence "So we can put a trail in front of you before you turn location on — and fall back to it whenever GPS cannot get a fix", a search field placeholder reading Town, park, or trailhead with "harr" typed into it and, where the places index is on the bucket, rows such as Harriman State Park, NY with the miles of trail held; under the field, "Kept with your settings — on this phone, and with your account once you sign in, so another device opens here too. Change it any time in More → You." and a Skip link'

// First run is the subject, so the runner must not skip it.
export const entry = true

export default async function drive(page) {
  await page.getByRole('button', { name: 'Get set up' }).click()
  await page.getByRole('heading', { name: 'Where do you hike?' }).waitFor()
  // The field is enabled only once the index has answered; typing into a
  // disabled field is a no-op, and the frame then shows the honest empty
  // sentence instead of rows.
  const field = page.getByRole('searchbox', { name: 'Where do you hike' })
  if (await field.isEnabled()) await field.fill('harr')
}
