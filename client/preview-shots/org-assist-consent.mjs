// The switch an organization throws before a model reads anything of theirs.
//
// WHY THIS SCREEN AND NOT THE PANEL. The three assist panels are already
// photographed where they live, and what a picture of one cannot show is the
// thing that decides whether it works at all: `Club.assist_opted_in`, off for
// every organization until an admin turns it on here. The panel's own refused
// state is an absence - no box, no button - and an absence is what a
// screenshot is worst at. So the camera points at the decision instead.
//
// The demo organization has agreed, so this is the ON state: the date, the
// name of the admin who agreed, and the sentence naming exactly what leaves
// and where it goes. A reviewer can judge that sentence against the endpoint
// (`POST /clubs/:slug/assist`) rather than against a promise.
export const caption =
  'The assistant is off for every organization until one of its admins turns it on, on the screen that says what would leave'
export const alt =
  'The Settings and leaving screen of the demo organization, on desktop and scrolled to The assistant panel: the heading with a small "on" beside it, then a paragraph saying that turned on, the three assistant panels — on Hike registry, Add a trail and Coverage — send what is already on those screens (the section names, the trail names, the mileages and the coverage gap lists) plus whatever an admin types into the box, that this goes to Anthropic\'s API at api.anthropic.com, that OurHike stores neither the question nor the answer but only a token count, a date and which panel spent them, and that it is off until you turn it on. Under it a monospaced line reading "Turned on 8/19/2026 by Sam Ortiz." and a Turn the assistant off button. The console rail is down the left and the Remove an admin panel begins below.'

// DESKTOP, for the reason the other three org shots are: the console is a
// 1440px surface with a fixed rail, and a 390px capture of it photographs a
// layout nobody uses.
export const desktop = true

export default async function drive(page) {
  await page.goto(
    new URL('org/central-park-throughikers/setup?page=leaving', page.url()).href,
    { waitUntil: 'load' },
  )
  await page.getByRole('heading', { name: 'The assistant' }).waitFor()
  // Scrolled to the BUTTON rather than the heading, because the heading is
  // the top of a tall panel: bringing it into view leaves the sentence about
  // what is sent, the date, the name and the switch itself all below the fold
  // - which is a photograph of a heading rather than of a decision.
  await page.getByRole('button', { name: /Turn the assistant/ }).scrollIntoViewIfNeeded()
}
