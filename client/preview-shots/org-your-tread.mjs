// The volunteer's half of the same organization (#1541).
//
// WHAT THIS ANSWERS THAT THE CONSOLE SHOT DOES NOT. The console is what an
// org admin sees; this is what the person who actually walks the miles sees,
// and the two are different products sharing one login. A reviewer reading
// the diff has no way to tell from the file list that the volunteer screens
// are not just the admin ones with fewer buttons.
//
// THE ALERTS ARE THE PART TO LOOK AT. Three of them, from a park, a managing
// partner and a county, and none of them closeable here - that rule is the
// one thing on this screen a hiker's safety turns on, and it is invisible in
// a diff because it is an absence: there is no dismiss button to see.
//
// Invented organization, real ground, nobody signed in. Same as the registry
// shot beside it.
export const caption =
  "A volunteer's own miles — three land-manager alerts, and no way to close any of them"
export const alt =
  "The Your Tread screen of the demo organization: a section header reading The Ramble with its mile markers and length, a points-of-interest list with two entries marked 'needs a look', and an Alerts on your miles panel carrying three notices from a park, a managing partner and a county, each stating its source and date and none of them carrying a dismiss control"

// DESKTOP, because the console IS a desktop surface: the wireframes are
// 1440px, the rail is a fixed 348px column, and a 390px capture of it is a
// photograph of a layout nobody uses. The volunteer's own screens work at
// both widths - they are shot wide here so the three org shots read as one
// set beside each other in the comment.
export const desktop = true

export default async function drive(page) {
  await page.goto(new URL('my/tread?org=central-park-throughikers', page.url()).href, {
    waitUntil: 'load',
  })
  await page.getByText('Alerts on your miles').waitFor()
  await page.getByText('Alerts on your miles').scrollIntoViewIfNeeded()
}
