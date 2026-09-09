// The legend sheet — and the worked example of pointing the camera.
//
// A recipe exports a caption and, when the screen is not the one the app
// opens on, a default-export drive that takes a Playwright page the rest of
// the way. The runner (scripts/photograph-preview.mjs) has already loaded
// the built app, skipped first run (export `entry = true` to keep it), and
// let it settle; the drive does only the taps a hiker would.
//
// CI photographs every recipe a pull request adds or changes and leads the
// preview comment with it, so changing a screen and pointing the camera at
// it are the same pull request — .claude/skills/pr-screenshot/SKILL.md.
// Re-pointed 2026-08-25: the blaze rows came off the top of this panel, so
// the shot this recipe already reached is the evidence for their removal —
// what the caption has to say is which absence to look for, since a reviewer
// cannot see a row that is not there without being told it used to be.
//
// Re-pointed again 2026-08-26 (#1047): the panel gained an Alerts switch
// under the grid, beside "Verified?" and the drought row. This time the shot
// is evidence for something PRESENT, so the drive scrolls it into frame
// rather than stopping at the top of the sheet — the switch sits below the
// controls a phone-height sheet shows at rest, and a photograph of the grid
// says nothing about a control under the fold.
//
// Re-pointed again 2026-08-27 (#1051): the closure and serious-warning rows
// reach a hiker for the first time. They had rendered in Legend.test.tsx and
// nowhere else for as long as they had existed, so this is the first
// photograph of either — which makes the shot the whole evidence, and makes
// the row rather than the switch what the camera has to reach. Both sit at
// the foot of the grid, immediately above the switch the last re-pointing
// framed, so this scrolls further down the same sheet rather than anywhere
// new. What the caption has to name is what is NOT on them: no number.
// Re-pointed again 2026-09-02 (#1197): a ninth waypoint category, and the
// scroll target moves one element further down, to the "Showing" control.
//
// THE COUNT IS THE EVIDENCE. "4 of 9 types" where it read "4 of 8" is the
// whole change in one string, and it is the only part of this screen that
// says the category arrived rather than merely showing a row somebody has to
// count. The Trailhead row comes with it - it sits three rows above, alone in
// the last grid row because nine is odd against two columns - and so do the
// Closure and Serious warning rows the previous pointing was for, because
// `scrollIntoViewIfNeeded` scrolls the MINIMUM and this is one element past
// where it already stopped.
//
// A PREVIOUS VERSION OF THIS CAPTION CLAIMED THE COUNT WITHOUT REACHING IT.
// The camera did not move and the alt text named "4 of 9 types" anyway, on
// the strength of a frame shot in the agent sandbox where it WAS visible.
// CI's build is not that build: it loads real trail data, so the sheet
// carries an extra paragraph ("Other trails are dimmed...") that the empty
// one does not, and 74 px of it pushed the control under the fold. Measured
// on PR #1217's own preview render rather than reasoned about. A caption
// describing something outside the frame is the same failure as a comment
// asserting something nobody checked - and this one was published to a
// reviewer, which is worse.
//
// So anything this caption claims has to survive BOTH builds, and the target
// is now the element carrying the claim rather than the element beside it.
//
// WHAT IT SHOWS IS A STRUCK-THROUGH ROW, and that is the shot rather than a
// flaw in it. `trailhead` is not in DEFAULT_SHOWN_TYPES, so it arrives hidden
// - correct for this screen (a trailhead is how a hiker REACHED the trail, and
// map/labelLadder.ts ranks it first on the planning map for the same reason it
// ranks last here) but arrived at by omission rather than by decision, which
// is #1214. The grey row is therefore evidence for two things at once, and the
// caption names the second because nobody would read it off the picture.
//
// The violet is not in this frame either - a hidden row desaturates its pin,
// and that is a true thing the caption does not claim. For the colour,
// `npx vite-node scripts/preview-poi-pins.ts` writes the contact sheet.
export const caption =
  'The legend — a ninth waypoint category, and it arrives switched off (#1197)'
export const alt =
  'The legend sheet over the trail screen, scrolled to the foot: a ninth waypoint row labelled Trailhead sits alone in the last grid row, its signpost pin and label greyed and struck through like Resupply, Crossing, Viewpoint and Parking above it, and below the Closure and Serious warning rows the Showing control reads 4 of 9 types'

export default async function drive(page) {
  // The map first: the app opens on Today since #1054, and the legend's
  // button floats over the map screen.
  await page.getByRole('tab', { name: 'Map' }).click()

  // The header's icon button. Its accessible name is the visually-hidden
  // span inside it (chrome/Header.tsx), which is what a screen reader — and
  // therefore this locator — sees.
  await page.getByRole('button', { name: 'Legend' }).click()

  // The count, brought into view by the thing that IS the change rather than
  // by a pixel offset into the sheet: everything above it is the hideable
  // category grid (#723), so how far down it sits moves whenever that list
  // does — as it just did. `scrollIntoViewIfNeeded` also waits for the
  // element, so this is the settle as well as the scroll.
  //
  // ONE ELEMENT PAST WHERE THIS USED TO STOP, deliberately and no further.
  // The previous target was the Serious warning row, and it stays in frame:
  // `scrollIntoViewIfNeeded` scrolls the minimum, and the control sits
  // directly under it. The Alerts switch is the NEXT element down and is
  // still not reached — checked on PR #1094 and unchanged: scrolling far
  // enough for it pushes the Closure row off the top, and that row is still
  // part of what this shot carries.
  //
  // WAIT FOR THE SHEET TO STOP GROWING BEFORE SCROLLING IT, which is the whole
  // reason this drive is longer than a tap.
  //
  // The runner settles once after load, runs this, then settles AGAIN before
  // the shutter (screenshot.mjs). In the sandbox the app has no trail data and
  // the sheet is finished by the time we arrive. In CI it is not: the data is
  // still landing, lib/legendContents.ts's GHOSTED_TRAILS_NOTE appears once a
  // dimmed trail is actually drawn, and the counts fill in. All of that
  // happened during the SECOND settle - after this drive had already scrolled
  // - so the sheet grew past its `max-height: 60%` with `scrollTop` still 0,
  // and the shutter caught the top of a sheet whose foot had just gone under
  // the fold.
  //
  // That is what the first attempt at this got wrong, and the obvious
  // diagnosis was wrong with it: the scroll was not failing. Measured on this
  // build against a deliberately shortened viewport, which reproduces the
  // overflow the sandbox otherwise never has - `scrollIntoViewIfNeeded` moved
  // the sheet 0 -> 292 px and put the control fully inside it. There was
  // simply nothing to scroll yet.
  //
  // So: poll `scrollHeight` until it stops changing, then scroll. A settle on
  // something observable rather than a longer fixed wait, which is what
  // CLAUDE.md asks of anything awaiting an effect - and it is the only version
  // that suits both builds, since the sandbox breaks out on the first
  // comparison and pays nothing for the loop.
  const sheet = page.locator('.legend')
  let previous = -1
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const height = await sheet.evaluate((element) => element.scrollHeight)
    if (height === previous) break
    previous = height
    await page.waitForTimeout(500)
  }

  // By its accessible name, which is spelt out in full on the `select`
  // (chrome/Legend.tsx explains why it is not assembled from the visible
  // "Showing" plus a hidden continuation).
  await page
    .getByRole('combobox', { name: 'Showing waypoint types' })
    .scrollIntoViewIfNeeded()
}
