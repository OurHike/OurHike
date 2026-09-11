// Today's shelf on the phone a hiker actually has: published routes with no
// measured climb, and therefore no honest time filter to offer.
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the "Have less time?" row carries only
// the chip that has something behind it. lib/suggestedHikes.ts states the
// rule for the whole feature — "a facet no route on the phone can answer (a
// time bucket when nothing can be priced…) is not offered" — and names
// `availableFacets` as "the one place that is decided". screens/FindHike.tsx
// asked it and screens/Today.tsx did not, so the two time chips rendered
// unconditionally and opened the finder on "0 hikes".
//
// WHY THIS FIXTURE AND NOT THE OTHER ONE. suggested-hikes.mjs seeds the
// design handoff's routes, five of which carry a climb, and photographs the
// chips PRESENT — which is the right frame for the card's two shapes and the
// wrong one for this. Measured 2026-09-11 against release 2026-09-10: not one
// of the nine published routes carries a climb, so the withheld state is what
// every hiker sees today, and the fixture here is that document with the
// climbs taken out.
//
// Look at the row under "Have less time?": one chip, "Easy only", because
// difficulty is the one facet these routes can answer. Compare with
// suggested-hikes.mjs, where three chips sit under the same rule.

import { seedUnpricedHikes } from './fixtures/suggestedHikes.mjs'

export const caption = 'Today — the time chips withheld when nothing can be priced'
export const alt =
  'The Today column in day mode with a Suggested hikes rule and three route cards each reading no time, climb unmeasured, then a Have less time? rule with a single Easy only chip under it'

export default async function drive(page) {
  await seedUnpricedHikes(page)
  await page.getByRole('radio', { name: 'Day hike' }).click()
  await page.getByRole('button', { name: 'Easy only' }).waitFor()
}
