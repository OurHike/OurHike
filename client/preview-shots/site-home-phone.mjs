// ourhike.org's homepage hero on a phone (#1877 - The homepage names five
// organizations while pipeline/sources.json registers 150).
//
// WHAT TO LOOK FOR: the headline counts every organization with data that
// ships - "Trail data from 111 organizations, offline." on 2026-10-23, where
// it said "5 organizations sharing all their trails and paths" - read from
// the registry when the site is built, and under it the link "See all 111
// organizations" to /organizations/. The list itself is not on this page:
// the maintainer rejected it there on sight and chose a page of its own.
//
// HELD ON THE COUNT LINE. The headline rotates every four seconds through
// lines about the organizations, nearest first; under reduced motion it
// does not start, which is how this frame stays on the line that changed.
// The IP lookup that orders the rotation is refused, so the frame never
// depends on where CI's runner is.
import { openSitePage, serveMarketingSite } from './fixtures/marketingSite.mjs'

export const caption =
  'ourhike.org on a phone: the headline counts every organization with data that ships, with a link under it to the new A-to-Z page'
export const alt =
  'The top of the OurHike homepage at phone width, over faint green contour lines. Under the site nav, a small white blaze and the eyebrow "HIKE YOUR OWN HIKE", then the large serif headline "Trail data from 111 organizations, offline." and directly under it a green underlined link, "See all 111 organizations". Below, the grey tagline about downloading once over wifi, a filled green "Get the app" button and an outlined "Open it in the browser" button.'

export async function before(page) {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('https://get.geojs.io/**', (route) => route.abort())
  await serveMarketingSite(page)
}

export default async function drive(page) {
  await openSitePage(page, '/')
  await page.getByRole('link', { name: /^See all \d+ organizations$/ }).waitFor()
}
