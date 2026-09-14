// Step 1 of the planning spine (#1373, the design's frame 3e): "Where do
// you want to go?" - the screen where "What are you planning?"
// (chrome/PlanKindSheet.tsx, retired by D6) and Find a hike's front door
// both stood. What the shot is evidence for: the rail with the mode's own
// answer on its first stop, the question, the field, the three doors (or
// the refusal sentence where this build holds no junction graph - a true
// frame either way, and the caption says which to expect), and the
// published shelf as a doorway.
//
// Driven from Today's pinned bar rather than the Plan tab's primary: the
// bar's Plan is on every state of Today, and the Plan tab's own primary
// changes with the room the tab is in.
export const caption =
  'Step 1 — "Where do you want to go?", the kind read off the mode and never asked (#1373, frame 3e)'
export const alt =
  'The Plan tab showing step 1 of the planning spine: a three-stop rail reading Day hike, Route and Details with the first stop lit; the heading "Where do you want to go?"; a search field placeholder reading a shelter, a summit, a town, or “mi 500”; three round doors, Where I am, Pick on the map and Draw it myself - or, on a build with no junction graph, the sentence saying the trail network is not on the phone and a Try again button; then "or start from one of these" with a count into the finder, chips, and a shelf of published hike cards; Cancel at the foot, and the four tabs with Plan selected'

export default async function drive(page) {
  await page
    .getByRole('group', { name: 'Find or plan a hike' })
    .getByRole('button', { name: 'Plan a hike' })
    .click()
  await page.getByRole('heading', { name: 'Where do you want to go?' }).waitFor()
}
