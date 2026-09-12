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
// SINCE #1344 IT ALSO CARRIES THE TWO CONTROLS THE ROOM WAS MISSING: a
// "Rename ›" beside "Carry on with" - `renameHike` had been in the store
// since #788 with nothing calling it, so every hike kept the "A new long
// hike" it was created with - and a primary that reads "Plan a section" and
// opens the planner in place (plan-section-inline.mjs is that frame).
//
// SINCE #1367 EACH SECTION ROW CARRIES ITS MOVE. `unassignTrip` had been in
// the store since #788 with no caller, so a section could join a hike and
// never leave one — the only escape being "Forget this hike", which ungroups
// every section in it. "Take out" on a row in the hike, "Add" on one in
// "Your other sections", and the two shelves become two halves of one
// control rather than a division a hiker can see and cannot change.
//
// WHAT TO LOOK FOR: the hike's NAME as the band's h1, "Switch hike ›" beside
// it, the blaze-bordered "Carry on with" card, and "This hike, end to end"
// carrying `mi walked · mi to go` over a two-band bar.
//
// 2026-09-10, re-photographed for #1373 (frame 8a): "What's left ›" now sits
// beside "This hike, end to end", on the figures it is about - it used to be
// at the foot of the hike zoom, two taps down. The day-hike shelves under
// the sections carry "All N ›" doors and walked walks get a shelf of their
// own (D5); the preview seeds no day hikes, so neither shows here, and
// PlanHome.test.tsx holds both. whats-left.mjs is the screen the new door
// opens.
//
// TWO BANDS, AND COUNT THEM. There is no third. The handoff overrides
// features/SEGMENTS.md's derived-gap idea for these screens in as many words
// — "no gap rows, no gap arithmetic, no dashed gap band" — and no percentage
// appears anywhere on the screen, which is OurHikeValues.md #1 and what
// PlanHome.test.tsx's standing guard holds.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'Plan, in the long-hike state — the room the hike is about (#1329)'
export const alt =
  'The Plan tab headed "you’re planning / Springer → Katahdin" with a "Switch hike" button, a "Rename" link beside "Carry on with", a blaze-bordered card to carry on with, a "This hike, end to end" card with a "What’s left" link beside its title, printing miles walked and miles to go over a two-colour bar, a list of the sections on the hike, and a primary button reading "Plan a section"'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('heading', { level: 1, name: 'Springer → Katahdin' }).waitFor()
}
