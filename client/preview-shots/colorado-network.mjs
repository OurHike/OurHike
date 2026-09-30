// Colorado at zoom 7, which is where this batch is largest.
//
// WHY THIS FRAME AND NOT A STANDING ONE. The trail screen photographs the
// opening camera over the whole lower 48, where a state's worth of new trail
// is a few pixels; network-above-the-seam.mjs and network-at-the-corridor-
// camera.mjs are both in the Hudson valley, two thousand miles from anything
// #1785 flips. Nothing in the set looks at ground the bulk load actually
// changes.
//
// COTREX IS 96,897 FEATURES IN ONE STATE - 71% of the entire network that
// shipped before this batch, from Colorado alone (measured by the UA publish
// of 2026-09-30, which fetched it at exactly the count #1778's probe
// predicted). Utah UGRC's 48,132 and BLM's 19,532 are next door. So this is
// the frame where "seventeen organizations reach a hiker" either happened or
// did not, and it is legible at a glance rather than by counting.
//
// WHAT THIS SHOT SHOWS ON THIS PULL REQUEST, and it is the honest answer
// rather than a failure: NOT MUCH. The preview reads the bucket, and the
// bucket carries what `reaches_hikers` allowed when it was last published -
// so until this branch merges AND a publish runs, Colorado draws the
// Continental Divide and little else. This frame is the BEFORE. What should
// be different afterwards is a state filled with fine trail lines in their
// blaze hues, the Colorado Trail and the Continental Divide among them at
// through-route weight.
//
// WHAT WOULD BE WRONG AFTERWARDS:
//
//   - A trail drawn at through-route weight whose name belongs to several
//     unrelated trails. That was #1776, fixed in #1784 before this flip was
//     allowed to happen, and this is the first frame where a national
//     source's naming is visible on real ground.
//   - The state a solid mat of colour rather than legible lines, which would
//     mean the width taper is not reaching a density nothing has drawn
//     before - 96,897 features in one state is an order more than any
//     previous frame in this set.
//
// z7 rather than z8: one pixel is about 470 m at this latitude, so a segment
// is a line rather than a dot, and the whole state is not in frame at z8.
// Public land at a scale where nothing of anybody's is readable - no
// campsite, no report, no fix (the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear).
//
// The camera is seeded through lib/cameraMemory.ts's session-storage key, as
// network-above-the-seam.mjs does and for its reasons.

export const caption =
  'Colorado at zoom 7 — where this batch is largest. COTREX publishes 96,897 trail features in this one state, 71% of the entire network that shipped before #1785. On this pull request the frame is the BEFORE: the preview reads the bucket, and the bucket carries what `reaches_hikers` allowed at the last publish, so Colorado is nearly bare. After the flip merges and a publish runs, this is where seventeen organizations arriving is visible at a glance.'
export const alt =
  'The map screen over Colorado at zoom 7: a pale basemap of the state with the Continental Divide Trail running north to south through the Rockies as a fine line, and very little else drawn — the state largely empty of trail lines.'

/** A state's worth of vector tiles at a coarse zoom reads several leaf
 *  directories before the first tile draws. */
export const wait = 6000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, validated
  // field by field and null on anything that does not convince. Centred on
  // the state so the Front Range, the San Juans and the Divide are all in.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-105.8, 39.0], zoom: 7 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the CONTEXT (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
}
