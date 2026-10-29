// ourhike.org/about/'s "Where the data comes from" on a phone (#1877 - The
// homepage names five organizations while pipeline/sources.json registers
// 150).
//
// WHAT TO LOOK FOR: the paragraph counts the organizations from the
// registry when the site is built - "come from 111 organizations' own
// published data" on 2026-10-24, and "All 150 registered organizations ...
// are on Whose data is on the map", a link to /organizations/. Until then it
// said the data came from "five organizations' published GIS layers" and
// named them. The "What this is" paragraph at the top of the page carries
// the same count and is not in this frame.
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'

export const caption =
  'ourhike.org/about/ on a phone: "Where the data comes from" counts the organizations from the registry and links to the list of every one'
export const alt =
  'The About page at phone width, scrolled to the section headed "Where the data comes from" beside a small white blaze. Its first paragraph reads that trails, shelters, closures and alerts come from 111 organizations\' own published data, from the Appalachian Trail Conservancy\'s centerline to state parks, national forests and volunteer clubs, and that all 150 registered organizations are on a green underlined link, "Whose data is on the map". It goes on to the USGS topo and elevation sources and the OpenStreetMap water credit, then a second paragraph about sources being labelled by how certain they are.'

export const before = serveMarketingSite

export default async function drive(page) {
  await openSitePage(page, '/about/')
  const heading = page.getByRole('heading', { name: 'Where the data comes from' })
  await heading.waitFor()
  await scrollToTop(heading)
}
