// The "reported missing" mark on the pin's upper-left edge (#1687).
//
// WHAT THIS FRAME IS EVIDENCE FOR. The mark (map/disputeLayers.ts, #876) used
// to sit at a fixed offset from the waypoint's coordinate, which stopped
// matching the pin once pins stood on their point (2026-09-20) and were
// drawn 26 px across (#1684): it covered the glyph it was placed to leave
// readable. It now sits centred on the drawn pin's upper-left edge, at the
// pin's own size by zoom and tier - the position the maintainer chose from
// five real pins drawn two ways (poll, 2026-09-26). Three marks here, one for
// each case worth seeing:
//
//   - LIMESTONE SPRING SHELTER, a site pin carrying a privy, water and a
//     campsite as badges on its upper right. The mark on the upper left is
//     clear of all three, which is why it moved sides.
//   - A SPRING to the south-east (the verified A.T. water by John Bates), a
//     full-size pin: the mark on the edge, the droplet still whole.
//   - PROSPECT MTN SUMMIT VISTA, a quiet pin drawn at 0.72: the mark follows
//     the smaller pin in, and covers the vista's sun - the cost the
//     maintainer accepted over a mark pushed further off the pin.
//
// SEEDED, AND SAID SO. No dispute is live on the UA bucket (the published
// `conditions/disputes.json` held none on 2026-09-26), so this recipe answers
// both reads the app makes - the published file and the live `/disputes`
// endpoint - with three verdicts written here. They are nobody's reports: no
// account, no note, a count of one, and the places are three public A.T.
// waypoints picked for their pin types, not because anybody said anything
// about them. The frame shows the mark, never a claim about these places.
//
// NOTHING ELSE HERE IS ANYBODY'S. Public ground, no account signed in, no
// photo, no location fix - the four things .claude/skills/pr-screenshot/
// SKILL.md says must never appear. The shelter's campsite is folded onto its
// pin, so no campsite is drawn on its own.
//
// WHEN IT SHOWS LESS. No marks at all means the verdicts landed after the
// wait, or a read this recipe does not answer won; marks without pins under
// them would mean the pins had not placed yet.
export const caption =
  'The “reported missing” mark on the pin’s upper-left edge (#1687), Limestone Spring Shelter on the A.T. in Connecticut at zoom 12.6, with three SEEDED verdicts (nobody’s reports): on the shelter, clear of its member badges on the upper right; on a full-size spring; and on a pale vista, where it follows the smaller pin and covers the sun'
export const alt =
  'The map screen over the A.T. in Connecticut: a dark green shelter pin with three small badges on its upper right and a black circle-with-a-slash mark on its upper-left edge; a blue water pin to the south-east with the same mark on its upper-left edge; and a pale teal vista pin with a smaller-looking offset of the same mark over its top-left corner'

/** The site-badges recipe's wait and camera, since this is the same frame
 *  with marks added. */
export const wait = 35000

const DISPUTED = [
  'atc_shelters:fad31e22-ebca-4e0d-96cc-454bcfdfe339', // Limestone Spring Shelter
  'opentrail_at:4173', // the spring by John Bates SUP Vista
  'atc_viewpoints:74750c7a-3808-4270-ac59-b72b56ec45c8', // Prospect Mtn Summit Vista
].map((poiId) => ({
  poi_id: poiId,
  accounts: 1,
  latest_at: '2026-09-26T12:00:00Z',
  maintainer_said: false,
}))

export default async function drive(page) {
  // The published tier (lib/publishedConditions.ts) and the live one
  // (lib/api.ts's fetchDisputes), which wins whenever it lands - both, so
  // neither an empty bucket nor an empty backend can take the marks away.
  await page.route(/conditions\/disputes\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        generated_at: new Date().toISOString(),
        disputes: DISPUTED,
      }),
    }),
  )
  await page.route(/\/disputes(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(DISPUTED),
    }),
  )

  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-73.3935, 41.976], zoom: 12.6 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
}
