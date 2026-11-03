// The coverage badge an organization pastes onto their own site (#1542).
//
// THIS FRAME IS THE EVIDENCE FOR A BADGE THAT USED TO DRAW NOTHING. The
// embed's `mountCoverage` read `GET /clubs/{slug}/coverage`, which depends on
// a signed-in caller, so an anonymous visitor got a 401 and the badge rendered
// NOTHING - on every real site, always. It only ever appeared to work on
// /for-orgs/demo/, where a fixture answers without auth. "Draws nothing" is
// not a thing a diff shows and not a thing the old screenshot showed either,
// because the console's preview was drawn from the app's own data rather than
// from the endpoint the embed actually calls.
//
// So what is worth looking at here is the agreement: the three figures in the
// preview are the three the badge draws from the public `/scoreboard`, and
// the sentence under the paste block above them now describes those three
// rather than the gap count it described until 2026-09-18.
//
// AND WHAT IS DELIBERATELY ABSENT. No section is named and no gap is counted.
// The coverage report stays gated because a public list of which miles nobody
// is looking after is a list of miles to avoid, and this is the screen that
// would otherwise teach an organization to expect one in public.
export const caption =
  'The coverage badge: three counts for a donate page, and no list of which miles are unheld'
export const alt =
  'The embeds screen of the demo organization on desktop, with the Coverage badge tab selected: a dark paste block containing a div with id ourhike-coverage and the org slug followed by a script tag; above it a sentence describing three counts - miles maintained, people holding them, hours confirmed this season - and stating that no visitor is shown which miles have nobody on them; below, a Live preview panel captioned "this is what visitors see" holding a tile with Miles maintained, Active volunteers and Hours this season each over its figure, and the line "Counted from their own registry when this page loaded"; under the panel, "Published by Central Park Throughikers · drawn by OurHike".'

// DESKTOP, for the reason org-embed-preview.mjs gives: the console is a
// desktop surface, its rail is a fixed 348px column, and a 390px capture is a
// photograph of a layout nobody uses.
export const desktop = true

export default async function drive(page) {
  await page.goto(
    new URL('org/central-park-throughikers/setup?page=embeds', page.url()).href,
    { waitUntil: 'load' },
  )
  await page.getByRole('button', { name: 'Coverage badge' }).click()
  // Wait on the figure rather than the heading: the heading is on the panel
  // before the tab's own content has rendered into it, and a frame taken then
  // is a photograph of the previous tab.
  await page.getByText('Hours this season').waitFor()
  await page.getByText('Live preview').scrollIntoViewIfNeeded()
}
