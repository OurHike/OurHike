// The long hike on a laptop, as a window (#1329).
//
// WHAT THIS SHOT IS EVIDENCE FOR. That "Which long hike?" is a window in the
// middle of the screen with the app still visible around it, rather than a
// sheet welded to the bottom edge of a 1440px browser. The handoff asked for
// exactly this - "above the desktop breakpoint ... the frames here become
// the content column" - and #1317 shipped the phone's answer at every width.
// A maintainer's report of it was "I don't like the screen being at the
// bottom, can you make that an emergent window in the centre instead", and
// the second half of the same message says why it matters for the four
// full-screen flows too: "having them full screen makes it hard for me to
// remember where I am."
//
// SINCE #1344 IT IS ALSO THE SHOT FOR THE SWITCH BEING EVERYWHERE. The
// sidebar's "On the hike" block is on all four screens by construction, and
// it sits under its own rule with its own eyebrow for a reason the first
// attempt earned: dropped straight under the mode segments it read as a
// FOURTH mode, which is what splitting the prop was supposed to prevent and
// did not, because a prop split changes no pixels.
//
// WHAT TO LOOK FOR: the sidebar and the map are still there, dimmed by the
// scrim, on all four sides of the window. That is the whole change. The
// phone's own shapes are unmoved and long-hike-pick.mjs still photographs
// them - desktop.css is where every rule here lives, so it cannot reach a
// phone at all (WEBSITE.md §8).
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'The long hike on a desktop — a window, not a takeover (#1329)'
export const alt =
  'A centred dialog headed "Which hike are you on?" floating over a dimmed wide browser window, with the OurHike sidebar down the left \u2014 carrying the tabs, a "Today I\u2019m" block of three mode pills, and under its own rule an "On the hike" block naming Springer to Katahdin \u2014 and the Plan tab behind the dialog still visible on every side'

// The wide layout, which is the entire subject.
export const desktop = true

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()

  // WAIT FOR THE ROOM BEFORE REACHING FOR ITS SWITCH, and the wait is not
  // decoration. This is the only recipe that CLICKS at desktop width, and a
  // desktop builds the map from launch (App.tsx's `mapNeededNow` is true on
  // `isDesktop` alone) - so on a CI runner's software renderer the main
  // thread can still be inside that build when the tab opens.
  //
  // `click()` cannot spend that time usefully: past finding the element it
  // waits for STABILITY, the same bounding box across two animation frames,
  // which a starved frame loop never delivers - so the whole 30s budget goes
  // on an actionability check the page cannot answer, and the log says
  // "locator.click: Timeout" without saying which locator. That is how this
  // recipe failed on its second CI run having passed on its first and 3/3
  // locally.
  //
  // `waitFor()` asks only for visibility, so the settle happens where it can
  // actually be spent, and a failure afterwards names the room rather than
  // the button. CLAUDE.md's ordering rule with a camera instead of a test:
  // wait on something observable that proves the sequence completed.
  await page.getByRole('heading', { level: 1, name: 'Springer → Katahdin' }).waitFor()

  // The switch, which is the other half of #1329: `activeHikeId` could be
  // set exactly once before it, so a hiker with two hikes was stuck on
  // whichever they picked first.
  await page.getByRole('button', { name: /Switch hike/ }).click()
  await page.getByRole('dialog', { name: 'Which hike are you on?' }).waitFor()
}
