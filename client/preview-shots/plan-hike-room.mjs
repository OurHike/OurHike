// Plan, in the long-hike state — handoff §4, built by #1329.
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the Plan tab is now about the hike a
// hiker is ON. #1317 bound the tab to the app's mode and stopped there: the
// band still read "Sections" and the room was the same generic "Your hikes /
// Recent sections" list, so nothing on the screen said which hike. The
// report that produced this issue was "when I save a long hike, it is not
// displaying anywhere", and this room is half the answer (the other half is
// a contrast bug on the desktop journal, which has no recipe of its own —
// see the PR body's before-and-after).
//
// WHAT TO LOOK FOR: the hike's NAME as the band's h1, "Switch hike ›" beside
// it, the blaze-bordered "Carry on with" card, and "This hike, end to end"
// carrying `mi walked · mi to go` over a two-band bar.
//
// TWO BANDS, AND COUNT THEM. There is no third. The handoff overrides
// features/SEGMENTS.md's derived-gap idea for these screens in as many words
// — "no gap rows, no gap arithmetic, no dashed gap band" — and no percentage
// appears anywhere on the screen, which is OurHikeValues.md #1 and what
// PlanHome.test.tsx's standing guard holds.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'Plan, in the long-hike state — the room the hike is about (#1329)'
export const alt =
  'The Plan tab headed "you’re planning / Springer → Katahdin" with a "Switch hike" button, a blaze-bordered card to carry on with, a "This hike, end to end" card printing miles walked and miles to go over a two-colour bar, and a list of the sections on the hike'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('heading', { level: 1, name: 'Springer → Katahdin' }).waitFor()
}
