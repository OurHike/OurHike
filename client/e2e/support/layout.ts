// Does the map actually have room, or does it merely have a box?
//
// WHY A BOX IS NOT AN ANSWER, measured rather than argued (2026-09-11, this
// suite's own probe at 390x844, sampling the map container directly):
//
//   map tab, nothing open   box 0.915 of viewport height   88% reachable
//   legend open             box 0.915                      28% reachable
//   Today tab               box 0.915                       0% reachable
//
// The box never moves. `toBeVisible()` passes in the first two, and so would
// any assertion on width or height - the map screen stays mounted at full
// size under whatever is covering it. So a test written that way cannot see
// the failure this exists to catch: the map still there, and a hiker unable
// to see or touch any of it.
//
// The third row is the one this helper cannot reach, and that is the app
// being right rather than a hole: on the Today tab the map is taken out of
// the accessibility tree altogether, so the role query below finds nothing to
// sample. mapRoom.spec.ts asserts that absence directly instead, which is a
// stronger statement than "covered" anyway.
//
// WHAT THIS MEASURES INSTEAD. A grid of points over the map's own box, each
// asked `document.elementFromPoint` - "if a finger landed here, what would it
// hit?" - and counted as reach when the answer is the map or something inside
// it. That is the hiker's question rather than the layout engine's, it needs
// no list of what might be covering the map, and it is immune to the gap
// between a box and what is painted in it.
//
// The map is located by role, not by class (features/FLOW_TESTING.md), and
// the node is taken from that locator so the sampling and the query cannot
// drift apart.

import { expect, type Page } from '@playwright/test'

/** The reachable fraction of the map region, 0 to 1, and the box it was
 *  measured over. */
export async function mapReach(
  page: Page,
): Promise<{ reach: number; boxHeightFraction: number }> {
  return await page
    .getByRole('region', { name: 'Map' })
    .first()
    .evaluate((region) => {
      const box = region.getBoundingClientRect()
      let hit = 0
      let total = 0
      // 10x10 inset from the edges: a point exactly on the boundary belongs to
      // whichever neighbour rounds its way, and the map's own controls live in
      // the corners (rule R8), so the interior is what "room" means.
      for (let i = 1; i <= 10; i += 1) {
        for (let j = 1; j <= 10; j += 1) {
          const x = box.x + (box.width * i) / 11
          const y = box.y + (box.height * j) / 11
          if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) continue
          total += 1
          const at = document.elementFromPoint(x, y)
          if (at !== null && region.contains(at)) hit += 1
        }
      }
      return {
        reach: total === 0 ? 0 : hit / total,
        boxHeightFraction: box.height / window.innerHeight,
      }
    })
}

/**
 * The map has at least `floor` of itself reachable.
 *
 * Always stated per state, never globally: a map covered by Today on a phone
 * is the design (PATHWAY.md's R2 - "side by side on a desktop, stacked on a
 * phone"), and a rule that forbade it would be asserting the wrong thing
 * everywhere but the map tab.
 */
export async function expectMapReach(page: Page, floor: number, what: string) {
  const { reach } = await mapReach(page)
  expect(
    reach,
    `${what}: ${(reach * 100).toFixed(0)}% of the map is reachable, under the ` +
      `${(floor * 100).toFixed(0)}% floor. The map keeps its box when something ` +
      `covers it, so this is the assertion that can tell - see support/layout.ts.`,
  ).toBeGreaterThanOrEqual(floor)
}
