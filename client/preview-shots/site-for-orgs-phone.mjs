// The first screen of ourhike.org/for-orgs/ on a phone in dark mode - what
// the maintainer saw on 2026-09-24 and called "just everything seems off"
// (#1663 - The /for-orgs/ pages are unreadable in dark mode and misaligned
// on a phone).
//
// WHAT TO LOOK FOR, against the frame before #1663:
// - the mark and "Add your trails" share the first row, 24px in from the
//   edge like everything under them (the mark used to touch the edge: `.nav`
//   zeroed the gutter `.wrap` gives it);
// - the org doors are one row that scrolls sideways, "Claim your…" cut at
//   the edge (they wrapped to two rows and stranded "Claim your org");
// - no moss contour lines across the headline (they painted over the photo);
// - the tagline in full-strength ink over a scrim (3.18:1 before, measured).
//
// DARK, because that is the phone this was reported from and the scheme the
// org pages had never been looked at in. The first screen reads much the same
// in light; the dark-only damage is lower down, in
// site-for-orgs-reasons-dark.mjs.
import { openSitePage, serveMarketingSite } from './fixtures/marketingSite.mjs'

export const caption =
  'ourhike.org/for-orgs/ on a phone, dark mode: the nav back on the 24px gutter, the org doors in one scrolling row, and the hero copy on a scrim with no contour lines across it'
export const alt =
  'The top of the For orgs page at phone width in dark mode. A dark header with the OurHike mark at the left and an outlined "Add your trails" button at the right on one row, then "Get the app", "For orgs" and "About" on a second row, then a thin row of four links - For orgs (underlined), Demo org, Nominate an org, and "Claim your" cut off at the right edge. Below, a photograph of blue ridgelines under a cloudy sky, darkened at the top, carrying a small white blaze and the eyebrow "FOR THE PEOPLE WHO CUT THE TREAD", the headline "Your trails, drawn from your own data." in large white serif type, a paragraph in white, a filled pale-green "Add your trails" button and an outlined "See the demo org" button.'

export const before = serveMarketingSite

export default async function drive(page) {
  await page.emulateMedia({ colorScheme: 'dark' })
  await openSitePage(page, '/for-orgs/')
  await page
    .getByRole('heading', { name: 'Your trails, drawn from your own data.' })
    .waitFor()
}
