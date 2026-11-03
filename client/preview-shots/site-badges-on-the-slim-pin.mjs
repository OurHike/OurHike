// A shelter carrying its privy, water and campsite, on the slim pin (#1682).
//
// WHAT THIS FRAME IS EVIDENCE FOR. The maintainer chose the slim pin from
// drawings and then from frames of the built app, and three of its parts
// only show together at a site: the 17 px member badges (the member's own
// glyph on its colour, a paper ring, tangent to the 26 px pin - "make it the
// icon, not just the pin"), the ATC's notice at 30 px just clearing that pin,
// and a hollow spring with no invite ring round it. Limestone Spring Shelter
// on the A.T. in Connecticut has all three in one phone frame at z12.6: the
// shelter's site carries a privy, a water source and a campsite, the ATC has
// a notice posted just north of it, and Billy's View water to the west is
// `confidence: low`.
//
// Photographed in the agent sandbox against the UA bucket through
// scripts/data-proxy.mjs on 2026-09-26, the frame this recipe was written
// from: the shelter pin with its three badges, the red triangle notice above
// it, the hollow spring, a pale vista and pale parking. The same camera on
// `main` drew the shelter as a dot - its 72 px site image lost the collision -
// and a dashed water pin with a faint ring in its place.
//
// NOTHING HERE IS ANYBODY'S. An A.T. shelter and its designated campsite
// (folded onto the shelter's pin, so no campsite is drawn on its own), a
// spring, vistas and parking, all public ground; no account, no report, no
// photo and no location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear.
//
// WHEN IT SHOWS LESS. A dot where the shelter should be means the camera
// settled a hair further out and a neighbour won; no pins at all means the
// waypoints had not landed by the wait. No red triangle means the ATC has
// taken its notice down, which is the notice's own lifecycle and not this
// change.
export const caption =
  'The slim pin at a site (#1682): Limestone Spring Shelter on the A.T. in Connecticut at zoom 12.6 — the shelter drawn 26 px across with its privy, water and campsite as 17 px badges in their own glyphs, the ATC notice above it at 30 px, a hollow unverified spring to the west with no invite ring, and pale vistas and parking'
export const alt =
  'The map screen over the A.T. in Connecticut: a red trail line, a dark green shelter pin with three small badges on its upper right - a plum privy, a blue droplet and a green tent - a red hazard triangle just above it, a hollow blue water pin to the west, a pale teal vista pin and a pale parking pin'

/** Vector tiles from the bucket plus the waypoint source landing take longer
 *  than chrome - 22000 for the reason waypoints-at-the-carry-zoom.mjs gives,
 *  and more here: in the sandbox a first attempt at z13 with a 22 s wait
 *  photographed a blank map, and this camera at 35 s drew everything. Which
 *  of the two changes mattered was not isolated. */
export const wait = 35000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, seeded then
  // reloaded, as waypoints-at-the-carry-zoom.mjs does and for its reasons.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-73.3935, 41.976], zoom: 12.6 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the CONTEXT (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
}
