// "The view that matters most" on /for-orgs/demo/, on a phone, with the view
// in it (#1663 - The /for-orgs/ pages are unreadable in dark mode and
// misaligned on a phone).
//
// Until #1663 this section was a heading promising the volunteer's view and a
// paragraph and a button under it - no view. What to look for: the Tread card
// right under the lede, drawn from the app's own demo volunteer
// (client/src/org/demoVolunteer.ts), so the name, the 3.3 miles and the four
// open reports are the ones "Open the full volunteer view" lands on.
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'

export const caption =
  'The demo org’s “view that matters most” on a phone: the volunteer’s Tread card under the lede, from the same demo data the full volunteer view opens on'
export const alt =
  'A section of the demo organization page at phone width headed "The view that matters most", with a paragraph naming Alex as the Throughiker who looks after the Ramble, then a white rounded card: the eyebrow "YOUR TREAD · MM 1.0 → 4.3 · 3.3 MI", the heading "The Ramble", "Alex Mercer · Maintainer since March 2025 · supervised by the trails chair", a green-edged block "4 thanks on your paths" with a quoted thank-you, an amber block "4 open reports" naming "Blowdown across the path · MM 2.4" with a "Mark resolved" pill, a short list of points of interest, and two buttons, "Report something" and "Log hours".'

export const before = serveMarketingSite

export default async function drive(page) {
  await openSitePage(page, '/for-orgs/demo/')
  const heading = page.getByRole('heading', { name: 'The view that matters most' })
  await heading.waitFor()
  await scrollToTop(heading)
}
