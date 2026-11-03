// What an organization's own website visitors would see (#1542).
//
// THE LIVE PREVIEW IS THE EVIDENCE AND THE PASTE IS THE CLAIM. An embed is a
// line of HTML somebody copies onto a page we will never see, so the only
// thing that can be photographed here is the preview beside it - which is
// drawn with the same components the app uses, from the same registry the
// console loaded. A reviewer can then judge the promise under it ("no
// cookies, no tracking, no branding you cannot remove") against something
// rather than against nothing.
//
// The caveat under the table is deliberately in frame. The preview offers a
// difficulty filter that the real embed does not, because a registry section
// carries no difficulty - and saying so on the screen is cheaper than an
// organization finding out on their own homepage.
export const caption =
  'The embed an organization pastes onto their own site, and the live preview under it'
// WHAT IS ACTUALLY IN THE FRAME. The four tabs are above the fold and the
// caveat under the table is below it, so neither is claimed.
export const alt =
  'The embeds screen of the demo organization, on desktop and scrolled to the preview: a dark paste block containing a div with id ourhike-hikes, the org slug and a filter list, followed by a script tag; under it a "what it will not do" note promising no cookies, no tracking, no OurHike branding that cannot be removed, and a page that still renders when our servers are down; then a line explaining that data-credit="off" removes the attribution; then a Live preview panel captioned "this is what visitors see" holding region, difficulty and length filters and a table of the org\'s hikes with park, length, time, route and difficulty columns.'

// DESKTOP, because the console IS a desktop surface: the wireframes are
// 1440px, the rail is a fixed 348px column, and a 390px capture of it is a
// photograph of a layout nobody uses. The volunteer's own screens work at
// both widths - they are shot wide here so the three org shots read as one
// set beside each other in the comment.
export const desktop = true

export default async function drive(page) {
  await page.goto(
    new URL('org/central-park-throughikers/setup?page=embeds', page.url()).href,
    {
      waitUntil: 'load',
    },
  )
  await page.getByText('Paste this where it should appear').waitFor()
  await page.getByText('Live preview').scrollIntoViewIfNeeded()
}
