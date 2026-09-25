// The Nominate page's one field, on a phone (#1663 - The /for-orgs/ pages
// are unreadable in dark mode and misaligned on a phone).
//
// From 53cfedc7 until #1663 the field carried `org-field__label` and
// `org-field__input`, which no stylesheet defines: a bare browser input with
// a thin grey edge, then a 220px blank box under it, because `.org-field`'s
// `flex: 1 1 220px` was written for a row and this field sits in a column.
// The button under it wore the browser's own dark bevel. What to look for:
// the field matches every other org form field, the help text follows it
// directly, and "Read their site" is a flat green button.
import { openSitePage, serveMarketingSite } from './fixtures/marketingSite.mjs'

export const caption =
  'Nominate on a phone: the website field styled like every other org field, with no blank box under it, and a flat "Read their site" button'
export const alt =
  'The Nominate an org page at phone width: a white rounded form card with the eyebrow "STEP 1 · THEIR WEBSITE", the bold label "Club website" over a rounded cream input showing the placeholder https://carolinamountainclub.org, two paragraphs of grey help text directly beneath, a flat dark-green "Read their site" button and a centred line "This gives you no standing at their org, and asks nothing of them."'

export const before = serveMarketingSite

export default async function drive(page) {
  await openSitePage(page, '/for-orgs/nominate/')
  const label = page.getByText('STEP 1 · THEIR WEBSITE')
  await label.waitFor()
  await label.evaluate((node) => node.closest('form').scrollIntoView({ block: 'start' }))
}
