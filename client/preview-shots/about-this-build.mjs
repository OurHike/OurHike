// About this build, and how long THIS launch took (#1299).
//
// WHY THIS SCREEN NEEDS A PICTURE. features/LAUNCH_BUDGET.md was written
// because the maintainer reported the app taking about six seconds to open and
// nothing on the phone could say where the six seconds went. The rows this
// recipe photographs are the answer to that: five moments of the launch a
// hiker is holding, in milliseconds from when the browser began loading the
// page — which is the half of the number a throttled profile on a laptop
// cannot see, because it starts counting after the process is already up.
//
// The numbers in the frame are the PREVIEW's own launch on a CI runner, so
// they are not a budget verdict and the caption does not read as one. What the
// shot is evidence of is that the rows exist, are reachable, carry units, and
// say "not reached" out loud for a moment the launch never got to — an omitted
// row reads as "instant" to whoever is looking, which is the display
// outrunning its source.
//
// WHAT THE FRAME WILL SHOW, AND WHAT IT WILL NOT. The preview carries no
// downloaded release (the corridor archive lives in IndexedDB and nothing
// fetches it here), so "Waypoints ready" and "Trail index ready" will read
// "not reached" — which is the honest state of this build rather than a
// broken screen, and is exactly the case the rows are written to admit to.
// The first three are reached on every launch and will carry numbers.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix — the four things a shot must never contain
// (.claude/skills/pr-screenshot/SKILL.md). The build version and commit are
// public, and the timings are facts about this app's own startup.
export const caption = 'About this build — how long this launch took (#1299)'
export const alt =
  'The About this build section of the More tab’s "Where this map comes from" page: rows for Version, Commit and Built, then a "This launch" heading over five rows — App code started, Tab bar rendered, Your settings read, Waypoints ready, Trail index ready — each with a time in milliseconds from when the page began loading, and "not reached" against the two a preview build with no downloaded release never gets to. Under them, a note saying the times are measured from when the page started loading, are about the app rather than the person or their phone, and that nothing sends them anywhere on its own.'

export default async function drive(page) {
  // Two taps, and the tab is called "More" rather than "Settings" — the same
  // route source-registry.mjs takes, and the same two things its own header
  // records getting wrong the first time (chrome/tabs.ts, MORE_TAB.md).
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /Where this map comes from/ }).click()

  // By its accessible name rather than by position: this section sits under
  // whatever else that page gains, and a recipe pinned to an index
  // photographs the wrong screen silently.
  //
  // Scrolled to the NOTE at the foot of the block rather than to the heading
  // at its top, which is what the first version of this recipe did: the
  // heading came into view and the five rows under it did not, so the frame
  // was a picture of a section title. Anchoring on the last thing in the
  // section puts the whole of it above the fold.
  const note = page.getByText(/nothing sends them anywhere on its own/i)
  await note.scrollIntoViewIfNeeded()

  // Settle on something observable rather than on a delay: the rows render
  // from marks already recorded, so the last row being in the DOM is the
  // whole of "the readout is up". A fixed wait here would photograph whatever
  // the scroll happened to have reached.
  await page.getByText('Trail index ready').waitFor()
}
