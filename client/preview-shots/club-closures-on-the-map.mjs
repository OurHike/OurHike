// Every club closure on the map (the maintainer's polls of 2026-10-11: Q2
// "Build the map file now", and standard S6 as drawn in s6-map.html), from
// conditions/trail_closures.json, read at launch with no hike planned.
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, against S6's "the standard,
// drawn" and lib/closureStyle.ts's crossed-out mark (a band of the sheet's
// paper, a dotted trace on it, a chain of small dark crosses along it):
//
//  1. Top: "Example Ridge Trail fire closure", a line closure, crossed out
//     along its own line.
//  2. Middle right: "Example Lake State Park closed", an area closure, drawn
//     as the two trail stretches cut inside the park, each crossed out. The
//     park's edge is not drawn: S6's mock drew it, and said "mock only".
//  3. Lower left: "Bridge out at Example Creek", a point closure, one larger
//     cross - the far mark, at the point.
//  4. Bottom: "Example Canyon Trail closed", a closure the list greys (its
//     source gives no date), crossed out at the SAME full strength as the
//     others - the maintainer's "B: same mark", not faded.
//
// No sheet is left open: the drive taps the point's cross until its sheet
// opens - the proof the file, its reader and map/clubClosureTaps.ts have all
// landed, since nothing else on screen says so - and closes it again.
// club-closure-sheet.mjs is the same map with the greyed closure's sheet
// left open.
//
// EVERY CLOSURE AND ORGANIZATION IS INVENTED (fixtures/clubClosures.mjs),
// over Kansas farmland, and the file is answered on the wire before the app
// loads (`before`), whatever the bucket serves. Nothing here reaches an
// account, a hiker's own report, a dispersed campsite or a real location fix
// (.claude/skills/pr-screenshot/SKILL.md): nothing is seeded but the camera,
// and a CI browser has no location fix.
import {
  openClosureSheet,
  routeTrailClosures,
  trailClosureRows,
} from './fixtures/clubClosures.mjs'

export const caption =
  'Every club closure crossed out on the map, from conditions/trail_closures.json read at launch with no hike planned (the maintainer’s S6, 2026-10-11): a line closure along its own line, an area closure’s two trail stretches inside the park, one cross for a bridge out, and a closure the list greys drawn at the same full strength. Every closure and organization is an invented example, over farmland.'

export const alt =
  'The map screen at zoom 13 over farmland. Four invented closures are drawn with the crossed-out mark: near the top a long line drawn as a pale band carrying a dotted dark line with a chain of small dark x marks along it; to the right of the middle two short stretches meeting at a point, drawn the same way; lower left a single larger dark x with a pale edge; and near the bottom another long line, drawn exactly as the first. No sheet is open.'

/** Vector basemap tiles at z13, the allowance long-term-closures.mjs makes
 *  for a frame at this zoom. */
export const wait = 22000

export const before = routeTrailClosures

export default async function drive(page) {
  // The bridge's cross, until its sheet opens; then put the sheet away.
  const { point } = trailClosureRows()
  const sheet = await openClosureSheet(
    page,
    point.place.geometry.coordinates,
    point.title,
  )
  await sheet.getByRole('button', { name: 'Close' }).click()
  await sheet.waitFor({ state: 'hidden' })
}
