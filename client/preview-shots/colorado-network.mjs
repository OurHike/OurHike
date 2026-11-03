// Colorado at zoom 7, which is where this batch is largest.
//
// WHY THIS FRAME AND NOT A STANDING ONE. The trail screen photographs the
// opening camera over the whole lower 48, where a state's worth of new trail
// is a few pixels; network-above-the-seam.mjs and network-at-the-corridor-
// camera.mjs are both in the Hudson valley, two thousand miles from anything
// #1785 flips. Nothing in the set looks at ground the bulk load changes.
//
// WHAT IS ALREADY HERE, because the first version of this comment got it
// wrong and the frame said so. This does NOT open on empty ground. usfs_trails
// is nationwide and has shipped for a long time - it is the very source #1776
// is about, "one organization covering the country" - and usfs_rec_sites
// carries its waypoints, so Colorado's national forests already draw densely
// and the first shot of this recipe counted 563 waypoints in view. The
// Continental Divide runs through it. An earlier draft of this header
// predicted "the Continental Divide and little else", which was written from
// the flip's diff rather than from the map, and is the kind of guess a
// recipe exists to catch.
//
// SO THE QUESTION THIS FRAME ASKS IS NOT "DID ANYTHING ARRIVE". It is whether
// the map stays legible when a SECOND source at national scale lands on a
// state that already carries one. COTREX publishes 96,897 trail features in
// Colorado alone - 71% of the entire network that shipped before this batch,
// from one state - with Utah UGRC's 48,132 next door and BLM's 19,532 across
// the West (measured by the UA publish of 2026-09-30, which fetched each at
// exactly the count #1778's probe predicted).
//
// ON THIS PULL REQUEST THIS IS THE BEFORE, and that part was right: the
// preview reads the bucket, and the bucket carries what `reaches_hikers`
// allowed at the last publish. Until this merges AND a publish runs, what is
// drawn here is USFS's Colorado and nothing else the flip adds.
//
// WHAT WOULD BE WRONG AFTERWARDS:
//
//   - A SOLID MAT OF COLOUR rather than legible lines. This is the real risk
//     and it is why this frame matters more than a sparser one would: the
//     ground is already busy, and the width taper has never been asked to
//     draw two nationwide sources over each other. If the mountains west of
//     Denver read as a wash, that is the finding.
//   - A trail at through-route weight whose name belongs to several unrelated
//     trails. That was #1776, fixed in #1784 before this flip was allowed to
//     happen, and this is the first frame where a national source's naming is
//     visible on real ground rather than in a record count.
//
// z7 rather than z8: one pixel is about 470 m at this latitude, so a segment
// is a line rather than a dot. A phone at z7 spans roughly Fort Collins to
// Alamosa - the length of the state and not its width, which is the trade for
// segments being legible at all. Public land at a scale where nothing of
// anybody's is readable - no campsite, no report, no fix (the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear).
//
// The camera is seeded through lib/cameraMemory.ts's session-storage key, as
// network-above-the-seam.mjs does and for its reasons.

export const caption =
  'Colorado at zoom 7 — where this batch is largest. The ground is already busy: usfs_trails is nationwide and has shipped for a long time, so the national forests draw densely before this change touches anything. What #1785 adds here is COTREX\u2019s 96,897 trail features in this one state, 71% of the entire network that shipped before it, with Utah\u2019s 48,132 next door. On this pull request the frame is the BEFORE — the preview reads the bucket, and no publish has carried the flip yet. The question afterwards is not whether anything arrived but whether the map stayed legible when a second nationwide source landed on a state that already had one.'
export const alt =
  'The map screen over Colorado at zoom 7: a shaded-relief basemap from Fort Collins down to Alamosa, with dense red trail lines threaded through the mountain ranges west of Denver, and many purple and green waypoint pins across them — a counter reading “in view · 563”.'

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
