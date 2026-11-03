// A shelter's peek naming every part of its site (#1706).
//
// WHAT THIS FRAME IS EVIDENCE FOR. Since #941 the waypoint card opens as a
// peek, and the chip strip that reaches a site's privy, water and campsite
// (#526) had moved behind "Notes & details" - so a tapped shelter's peek named
// none of them, on a map where they ride the shelter's pin and have no pin of
// their own. The strip is on the peek now, under the meta line. Limestone
// Spring Shelter on the A.T. in Connecticut is the site: photographed in the
// agent sandbox against the UA bucket through scripts/data-proxy.mjs on
// 2026-09-28, its peek carried four chips - Shelter, Privy 74 ft, Water 83 ft,
// Campsite 173 ft - where `main` at da8b46a drew none.
//
// Reached by search rather than by camera and pin: a tap on the canvas needs
// pixel coordinates this recipe cannot know, and a search result opens the
// same card a pin does (waypoint-quick-answers.mjs drives it the same way).
//
// NOTHING HERE IS ANYBODY'S. An A.T. shelter and the public points around it;
// no account, no report, no photo and no location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear. The peek draws
// the category's silhouette, never a photograph.
//
// waypoint-site-parts-small.mjs is the same drive at 375x667, and that is the
// frame that found a bug: the peek there is capped to the room above its pin
// (#1374), and before chrome.css gave the peek's strip `flex-shrink: 0` the
// row shrank to zero height.
//
// WHEN IT SHOWS LESS. The search panel reading "Nothing here by that name"
// means this build has no POI artifacts; a peek with no chip row means the
// release stopped publishing this shelter's `site_id`, which is a claim about
// the publish rather than about this change.
export const caption =
  'A shelter’s peek naming its parts (#1706): Limestone Spring Shelter on the A.T. in Connecticut, the chip row under its name — shelter, privy, water, campsite — without pulling the card open'
export const alt =
  'Either a waypoint card peeking over the map for Limestone Spring Shelter, with a row of four round icons under its name and mile - a house, a privy, a water droplet and a tent - above the condition line and the Notes & details button; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

/** waypoint-quick-answers.mjs's settle. The drive already waits on the chip
 *  row itself, so this only covers the fly-to finishing under the card. */
export const wait = 5000

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()

  await page.getByRole('button', { name: 'Search' }).click()
  await page
    .getByRole('searchbox', { name: 'Search the downloaded map' })
    .fill('Limestone Spring Shelter')

  const result = page
    .getByRole('button')
    .filter({ hasText: /Limestone Spring Shelter/ })
    .first()
  await result.waitFor({ timeout: 40000 }).catch(() => {})
  if ((await result.count()) === 0) return

  await result.click()

  // The strip on the peek, which is the whole of what this frame is for.
  // Deliberately NOT opened: the opened card has had the strip since #526.
  await page
    .getByTestId('poi-card-peek')
    .getByTestId('poi-card-chip')
    .first()
    .waitFor({ timeout: 20000 })
    .catch(() => {})
}
