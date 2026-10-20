// A synthesized water point's card, printing a steward's estimate as one
// (#1728).
//
// WHAT THIS FRAME IS EVIDENCE FOR. ATC's Campsite Sustainability Index states
// how far water is from each shelter and, beside the figure, how it arrived
// at it - and 42 of the 305 distances the pipeline publishes are a steward's
// round number (`OSA_Field_Estimate`) rather than a measurement against a
// mapped point. Until #1728 the card printed both in one voice, "150 ft
// away", and this point's own sentence said "ATC measured" over all of them.
// The provenance now rides the artifact as `water_distance_source`, and the
// card prints an estimate with a tilde - "~150 ft away" on the meta line,
// "Water ~150 ft" on the chip, "water ~150 ft" in the shelter's nearby
// sentence - and words the sentence by it: "An ATC steward estimated how far
// water is from Ethan Pond Shelter". The maintainer chose the tilde by poll,
// 2026-09-30, over the word "about" and over changing the sentence alone.
//
// Ethan Pond Shelter on the A.T. in New Hampshire is the site: its 150 ft is
// an `OSA_Field_Estimate` row in pipeline/reference/water_distance.json
// (read 2026-09-30), and no real water point folds into its site, so the
// export synthesizes the member this frame opens. Photographed in the agent
// sandbox on 2026-09-30 against the pinned UA release with this branch's
// column applied through scripts/data-proxy.mjs: the meta line read
// "~150 ft away" and the sentence began "An ATC steward estimated".
//
// Reached by search rather than by camera and pin, for the reason
// waypoint-site-parts.mjs gives: a tap on the canvas needs pixel coordinates
// a recipe cannot know, and a search result opens the same card a pin does.
// Then the card is pulled open and the water chip tapped, which swaps the
// card to the member's own detail - the meta line and the sentence are both
// on that view.
//
// NOTHING HERE IS ANYBODY'S. An A.T. shelter and the point the export
// synthesizes onto it; no account, no report, no location fix, and the only
// photograph is ATC's own of the shelter, published by the pipeline - the
// four things .claude/skills/pr-screenshot/SKILL.md says must never appear.
//
// WHEN IT SHOWS LESS. Until publish-vector-data.yml reruns after the merge,
// the UA bucket carries no `water_distance_source`, and this frame shows the
// previous voice - "150 ft away" and "ATC measured how far water is from
// Ethan Pond Shelter" - which is the publish being stale rather than this
// change being absent; the PR's `## Data pipelines` section carries that
// handoff. The search panel reading "Nothing here by that name" means this
// build has no POI artifacts (a fork's pull request gets no secrets). A card
// with no water chip means the release stopped synthesizing this shelter's
// member - a real water point folded in, or the row left the reference
// file - which is a claim about the publish rather than about this change.
export const caption =
  'A steward’s estimate printed as one (#1728): Ethan Pond Shelter’s water point on the A.T. in New Hampshire, “~150 ft away” on the meta line and “An ATC steward estimated” in the sentence, where a measurement prints bare'
export const alt =
  'Either an opened waypoint card for “Water near Ethan Pond Shelter”: a row of round icons under the name, a meta line reading Water · mi 1,849.4 · ~150 ft away, and a sentence beginning “An ATC steward estimated how far water is from Ethan Pond Shelter”; or the same card in the previous voice, “150 ft away” and “ATC measured”, where the data has not been republished yet; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

/** waypoint-site-parts.mjs's settle: the drive waits on the card itself, so
 *  this only covers the fly-to finishing under it. */
export const wait = 5000

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()

  await page.getByRole('button', { name: 'Search' }).click()
  await page
    .getByRole('searchbox', { name: 'Search the downloaded map' })
    .fill('Ethan Pond Shelter')

  const result = page
    .getByRole('button')
    .filter({ hasText: /Ethan Pond Shelter/ })
    .first()
  await result.waitFor({ timeout: 40000 }).catch(() => {})
  if ((await result.count()) === 0) return

  await result.click()

  // Pulled open, unlike waypoint-site-parts.mjs: the sentence this frame is
  // for lives behind "Notes & details".
  const expand = page.getByTestId('poi-card-expand')
  await expand.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await expand.count()) === 0) return
  await expand.click()

  // The water chip swaps the card to the synthesized member's own detail.
  const water = page.getByRole('button', { name: /^Water / }).first()
  await water.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await water.count()) === 0) return
  await water.click()
}
