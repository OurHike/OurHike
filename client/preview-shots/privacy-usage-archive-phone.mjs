// ourhike.org/Privacy/'s usage-statistics list on a phone, at the bullet
// saying how long counts are kept (#1923 - Move each closed month's unlinked
// usage rows out of Postgres into a Parquet file in a private R2 bucket).
//
// WHAT TO LOOK FOR: the bullet opening "Counts and positions are kept for
// the six whole months after the month they were recorded, then deleted."
// now goes on "Counts not linked to an account move to private files at
// Cloudflare about two weeks after their month ends, and are deleted on the
// same schedule." - the one line the maintainer chose by poll on 2026-10-29,
// over two sentences that also named sealed positions and the lifecycle
// backstop. The rest of the bullet is the shorter page's (the maintainer's
// second poll that day, privacy-short-version-phone.mjs): backups, an opened
// position's file, collection stopping within three days, and no figure for
// fewer than 25 people, in the same five sentences with fewer words.
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'

export const caption =
  'ourhike.org/Privacy/ on a phone: the bullet on how long usage counts are kept now says counts not linked to an account move to private files at Cloudflare about two weeks after their month ends'
export const alt =
  'The Privacy Policy at phone width, scrolled to a bullet in the list about usage statistics. It begins "Counts and positions are kept for the six whole months after the month they were recorded, then deleted. Counts not linked to an account move to private files at Cloudflare about two weeks after their month ends, and are deleted on the same schedule." It goes on: "A database backup can hold them until the backup expires, and a position the maintainer has opened stays in a file on their own computer until they delete it. If the deletion job stops, we stop collecting within three days. Monthly totals are kept, and no figure for fewer than 25 people is ever shown."'

export const before = serveMarketingSite

export default async function drive(page) {
  await openSitePage(page, '/Privacy/')
  const bullet = page.locator('li', {
    hasText: 'Counts not linked to an account move to private files',
  })
  await bullet.waitFor()
  await scrollToTop(bullet)
}
