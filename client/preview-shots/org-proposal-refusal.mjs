// What a club sees when a stranger has offered their data, and how they say no.
//
// WHY THIS SCREEN AND WHY SCROLLED HERE. Everything about this flow that could
// go wrong for an organization ends at this frame: three people who never
// heard of us are asked about their own trail data, and the question is
// whether refusing is as easy as agreeing. A screen that buries "no thank you"
// under a paragraph collects consent from people who gave up.
//
// So the camera points at the two buttons side by side, with the stronger
// refusal - never ask again, for any hiker, ever - in plain words underneath
// rather than behind a preference. `nomination_refusals` is keyed by the
// club's own domain, so that sentence is true for every future hiker and not
// only this one.
//
// Note the count above it: one of three has answered. Three approvals are
// needed to proceed and ONE refusal ends it, which is the asymmetry this
// project applies to anything reaching a hiker.
export const caption =
  'Refusing is one button beside approving, and "never ask again" is in plain words rather than behind a preference'
export const alt =
  'The club-facing proposal screen on desktop, headed "A hiker wants to put your trails on the map." and saying a hiker on OurHike has proposed adding Blue Ridge Footpath Society\'s trails, that they are not affiliated with the organization and nothing has been published. Scrolled to the decision panel: a line reading "Nothing goes live unless 3 of you approve it", then two buttons side by side — "This is ours — go ahead" and "No thank you" — and under them a sentence offering "Tell us never to ask again", which it says will be honoured for good including for any other hiker who tries later, and that whoever proposed this is not told who declined. Above, a section headed WHO WE ASKED · 1 OF 3 HAVE AGREED lists three published addresses with the page each came from.'

export const desktop = true

export default async function drive(page) {
  await page.goto(new URL('n/demo', page.url()).href, { waitUntil: 'load' })
  await page.getByRole('button', { name: /No thank you/ }).waitFor()
  await page.getByRole('button', { name: /never to ask again/ }).scrollIntoViewIfNeeded()
}
