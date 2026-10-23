// ourhike.org/organizations/ on a phone (#1877 - The homepage names five
// organizations while pipeline/sources.json registers 150): the A-Z index of
// every organization with data that ships, which the maintainer chose by
// poll on 2026-10-23 over groups by what each shares and a sortable table.
//
// WHAT TO LOOK FOR, against mock A (an index, as a guidebook has one): the
// heading and the line linking to /for-orgs/; the search box, shown because
// the page's script ran; the letter strip, with letters nobody files under
// (D, H, J, Q, X, Y, Z on 2026-10-23) faded; and the start of A, each name
// with a dotted leader to its count of datasets, sitting on a wrapped name's
// last line. Every name and count is the registry's, read when the site was
// built - nothing here is invented, and nothing here is anybody's account.
import { openSitePage, serveMarketingSite } from './fixtures/marketingSite.mjs'

export const caption =
  'ourhike.org/organizations/ on a phone: every organization with data that ships, A to Z, with a search box, a letter strip and each one’s count of datasets'
export const alt =
  'The "Whose data is on the map" page at phone width. Under the site nav, a large serif heading and a grey paragraph saying the map is drawn from data the organizations publish themselves, ending in a green link "add your trail data". Below, a white search field with a magnifier and the placeholder "Find an organization", then a row of serif capital letters A to J running off the right edge, D, H and J faded. A small grey line reads "The number after each name is how many of its datasets reach the app." Then a large green serif "A" over a rule, and organization names - Alaska Division of Parks and Outdoor Recreation, Alaska Trails, Appalachian Mountain Club, Appalachian Trail Conservancy - each followed by a dotted line to a grey number at the right edge.'

export const before = serveMarketingSite

export default async function drive(page) {
  await openSitePage(page, '/organizations/')
  await page.getByRole('heading', { name: 'Whose data is on the map' }).waitFor()
  await page.getByRole('searchbox', { name: 'Find an organization' }).waitFor()
}
