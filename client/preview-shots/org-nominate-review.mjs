// A hiker deciding which of a club's published addresses we may write to.
//
// WHY THIS SCREEN. The nominate flow's whole argument turns on one condition
// the maintainer attached on 2026-09-17 when allowing a club's contacts to be
// harvested at all: the hiker keeps or abandons each one, and the backend
// stores nothing until they do. That is invisible in a diff and nearly
// invisible in prose - "the hiker can review it" is what a screen with an
// uneditable list would also claim. A picture of three checkboxes, each with
// the page the address came off printed under it, is the claim and the
// evidence in one frame.
//
// Look at the third contact: a role with NO NAME against it, rendered as the
// role rather than as a guess. Absent means nobody published one - the same
// rule the shelter capacity export follows, and the design's own example.
//
// And look at the button. It says how many people it is about to write to, by
// name of organization, because this is real mail to real volunteers who did
// not ask for it.
export const caption =
  'The hiker keeps or drops each address before anybody is written to — the button counts the people it is about to email'
export const alt =
  'The Put a club on the map for them screen on desktop, scrolled to WHO AT THE CLUB WE WOULD ASK. A paragraph says each of these was published on the page named beneath it and that only the ones left ticked are kept or written to. Three rows follow, each with a ticked checkbox: Dale Whitford, volunteers@demo.ourhike.org, listed on https://demo.ourhike.org/get-involved; Priya Raghavan, maps@demo.ourhike.org, listed on https://demo.ourhike.org/trail-maps; and a third reading Board president with no name, president@demo.ourhike.org, from https://demo.ourhike.org/contact. Below, a paragraph beginning "Nothing publishes because you submitted it" and a button reading "Write to 3 people at Blue Ridge Footpath Society".'

// Desktop for the same reason the other org shots are: this is reached from a
// marketing page people open on a laptop, and the review is a three-column
// reading task rather than a phone one.
export const desktop = true

export default async function drive(page) {
  await page.goto(new URL('nominate?website=https://demo.ourhike.org', page.url()).href, {
    waitUntil: 'load',
  })
  await page.getByRole('button', { name: /Read their site/ }).click()
  // Waits on the review heading rather than on the button, because the button
  // exists in the asking state too - waiting on it would photograph the form
  // before the reading arrived.
  await page.getByText('WHO AT THE CLUB WE WOULD ASK').waitFor()
  await page.getByRole('button', { name: /Write to 3 people/ }).scrollIntoViewIfNeeded()
}
