// ourhike.org/Privacy/'s first screen on a phone: the "short version" box
// the shorter policy opens with (the maintainer's poll of 2026-10-29, "B ·
// Shorter + summary", over the same text without the box and over cutting
// harder).
//
// WHAT TO LOOK FOR: under the title, the date (October 29, 2026) and a
// two-sentence opening, a green-edged box headed "The short version" with
// four bullets - the map needs no account; location stays on the phone
// except in a report you send or sealed inside usage counts while Share
// usage statistics is on; usage counts carry no ID unless linked, are
// deleted within seven months, and switch off in More → Safety & privacy;
// no notifications, no ads, nothing sold. Before, this box was one line
// about using the map without an account, and the page ran 2,123 words
// where it now runs 1,426 (counted 2026-10-29 over its <main>).
import { openSitePage, serveMarketingSite } from './fixtures/marketingSite.mjs'

export const caption =
  'ourhike.org/Privacy/ on a phone, first screen: the shorter policy opens with a four-line "short version" box'
export const alt =
  'The Privacy Policy at phone width, at the top of the page: the OurHike header, the title "Privacy Policy", "Last updated October 29, 2026", and a two-sentence opening saying what the page covers and to open an issue if anything is unclear. Below it a box with a green left edge, headed "The short version", with four bullets: "You can use the map, even offline, with no account and no personal information." "Your location stays on your phone, except in a report you send, or sealed inside usage counts while Share usage statistics is on." "Usage counts carry no ID unless you choose to link them to your account, and are deleted within seven months. Turn them off in More → Safety & privacy." "No notifications, no ads, and nothing sold."'

export const before = serveMarketingSite

export default async function drive(page) {
  await openSitePage(page, '/Privacy/')
  await page.getByText('The short version').waitFor()
}
