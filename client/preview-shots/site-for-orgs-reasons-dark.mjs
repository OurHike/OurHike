// The four reasons on /for-orgs/ in dark mode - the frame that would have
// caught #1663 (The /for-orgs/ pages are unreadable in dark mode and
// misaligned on a phone) before a maintainer did.
//
// site.css mirrors the tokens' dark block by hand and had left out the
// surfaces these cards sit on, so each card stayed paper while its text went
// to bone: four headings at 1.21:1, measured at 390px on 2026-09-24. What to
// look for is simply that they can be read - dark cards, light headings,
// the same on the registration form further down.
import { openSitePage, serveMarketingSite } from './fixtures/marketingSite.mjs'

export const caption =
  'The four reasons on /for-orgs/ in dark mode: ink cards with bone headings, where each card used to stay paper under bone text at 1.21:1'
export const alt =
  'The "Four reasons orgs register" band of the For orgs page at phone width in dark mode: a near-black band with the heading in light serif type beside a small white blaze, a light grey line of introduction, then dark rounded cards one above another, each with a thin green line icon, a light serif heading - "Beautiful maps, free to every hiker", "Crowd-source trail problems" - and a paragraph in lighter grey.'

export const before = serveMarketingSite

export default async function drive(page) {
  await page.emulateMedia({ colorScheme: 'dark' })
  await openSitePage(page, '/for-orgs/')
  const band = page.getByRole('heading', { name: 'Four reasons orgs register' })
  await band.waitFor()
  await band.evaluate((heading) => {
    heading.scrollIntoView({ block: 'start' })
    window.scrollBy(0, -24)
  })
}
