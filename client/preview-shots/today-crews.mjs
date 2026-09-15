// Today in volunteer mode: the crews screen (#1440, D22, frames 14g–14j).
//
// WHAT CHANGED. "Workdays in the next two weeks" was a flat column at the
// foot of More → Volunteer & report, two taps from anywhere, and Today
// carried a card whose whole job was to name the first one and send you
// there. In volunteer mode Today IS the crews screen now: the crews out
// today, then the switch, then the window, then the view - because this is
// the recruitment moment the feature exists for and it happens on a screen
// the hiker already opens.
//
// WHAT TO LOOK AT, AND WHAT THIS FRAME CANNOT SHOW, said plainly because the
// gap is the point. **#1402 — No workday artifact is published, so the
// volunteer pins and their sheet have nothing to draw** is still open, so the
// preview build has no crews and this shot is the screen's EMPTY state. That
// is worth photographing on its own terms: the switch, the three windows, and
// the honest-absence copy are exactly the parts that have to be right when
// there is nothing to show, and they are the parts #249's rule is about -
// "could not check" must never read as "no club has asked".
//
// TWO THINGS DELIBERATELY ABSENT FROM THE PICTURE. There is no kind-of-work
// chip row: `WorkProjectSummary` has no `work_type`, and until the field is in
// the bake the row renders nothing rather than being inferred from a club's
// own wording (D20). And there is no third "Map" segment: this app holds one
// MapLibre instance, so the map is a labelled door to the Map tab - a segment
// that navigated away would be a control lying about being a view.
//
// No trail data needed. No account, no location fix.

export const caption =
  'Today in volunteer mode — the crews screen, with nothing published to fill it yet (#1440, and #1402 for why it is empty)'
export const alt =
  'The Today screen in volunteer mode: a heading “Upcoming crews” above a two-segment List / Calendar switch with List selected, a row of three window chips reading “This weekend”, “Next 14 days” (selected) and “Next 30 days”, then the line “The workday list needs signal to load, and hasn’t yet.”, and beneath it a link reading “See the crews on the map ›”.'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByRole('radio', { name: 'Volunteer' }).click()

  // By the switch itself, which is the section's own landmark and the thing
  // this shot is about - and `scrollIntoViewIfNeeded` waits as well as
  // scrolls, so it is the settle too.
  await page.getByRole('group', { name: 'How to see the crews' }).scrollIntoViewIfNeeded()
}
