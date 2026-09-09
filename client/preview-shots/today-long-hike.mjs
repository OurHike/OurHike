// Today, in the long-hike state (#1317).
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the mode re-ranks without hiding
// anything: the pine chrome carries the hike's name and its two figures
// under the readout, the eyebrow says which day of the walk it is, and the
// hike's own day leads the paper column in a card with the blaze border -
// with the rest of the column still there below it. The figures are `miles
// walked · miles to go` and nothing else, which is the rule this screen is
// most likely to break and the reason the shot is worth taking.
//
// WHAT IT IS NOT EVIDENCE FOR. The day's mileage or resupply line, which
// come from the seeded plan rather than from anything measured, and the map
// thumbnail, which is a labelled door rather than the map's own canvas -
// see screens/Today.tsx on why, and what would settle it.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'Today, on a long hike — the hike’s day leads the column (#1317)'
export const alt =
  'The Today screen in long-hike mode: a pine header carrying the hike name "Springer → Katahdin" and a figures line reading miles walked and miles to go, with a card below headed "Today on your hike" showing the day’s two ends, a map door and two actions'

export default async function drive(page) {
  await seedLongHike(page)
}
