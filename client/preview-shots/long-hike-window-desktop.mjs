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
// WHAT TO LOOK FOR: the sidebar and the map are still there, dimmed by the
// scrim, on all four sides of the window. That is the whole change. The
// phone's own shapes are unmoved and long-hike-pick.mjs still photographs
// them - desktop.css is where every rule here lives, so it cannot reach a
// phone at all (WEBSITE.md §8).
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'The long hike on a desktop — a window, not a takeover (#1329)'
export const alt =
  'A centred dialog headed "Which hike are you on?" floating over a dimmed wide browser window, with the OurHike sidebar down the left and the trail map behind it still visible on every side'

// The wide layout, which is the entire subject.
export const desktop = true

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  // The switch, which is the other half of #1329: `activeHikeId` could be
  // set exactly once before it, so a hiker with two hikes was stuck on
  // whichever they picked first.
  await page.getByRole('button', { name: /Switch hike/ }).click()
  await page.getByRole('dialog', { name: 'Which hike are you on?' }).waitFor()
}
