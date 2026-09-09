// The source registry, read-only — the org console's first screen (#929).
//
// A recipe exports a caption and, when the screen is not the one the app opens
// on, a default-export drive that takes a Playwright page the rest of the way.
// The runner (scripts/photograph-preview.mjs) has already loaded the built
// app, skipped first run, and let it settle; the drive does only the taps a
// person would.
//
// WHY IT NEEDS A PICTURE MORE THAN MOST. This screen exists so a maintainer
// can look at the whole registry and decide what to build next — the
// maintainer's own words, 2026-08-27: "I just want to be able to see this now,
// so I can think about what features to build out later." A design that has to
// be read from a test file cannot do that job. The shot IS the deliverable.
//
// WHAT IT SHOWS THAT NO OTHER SURFACE DOES:
//
//  1. Registrations that reach no hiker — GATC's water PDF, OPRHP's park
//     polygons. `stewards.json` may only name what ships, so those two have
//     never appeared anywhere in this app.
//  2. What each licence actually rests on. Twenty-six of the thirty-three
//     sources ship on the maintainer's own authorisation rather than the
//     organization's stated terms, including all thirteen ATC layers.
//  3. The twelve registrations that declare no `kind`, rendered as a visible
//     gap rather than filled in from the fetcher's default.
//  4. An empty mark slot on every organization, because none has licensed one
//     (#933).
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix — the four things a shot must never contain
// (.claude/skills/pr-screenshot/SKILL.md). Every row is a public registration
// already in `pipeline/sources.json`.
// WHAT THIS SHOT WILL AND WILL NOT SHOW UNTIL A PUBLISH RUN HAPPENS, said
// here because a reviewer will otherwise read an honest empty state as a
// broken screen. The console reads `registry.json`, which
// `pipeline/export_sources.py` writes and `publish.py` uploads — and which no
// release has ever carried, because this pull request is the one that adds it.
// Until a `publish-vector-data` run completes, this screen renders "OurHike
// couldn't read the registry", which is its honest three-state answer (asking
// / could not ask / here it is) rather than a failure.
//
// So the picture below is evidence that the screen exists, is reachable in two
// taps from the More tab, and refuses to render "0 sources" for a phone that
// simply could not ask. It is NOT yet evidence of the table. That arrives with
// the next publish run and this recipe photographs it then, unchanged.
export const caption =
  'The source registry — reachable, and honest that it has nothing to read yet (#929)'
export const alt =
  'The source registry screen, read-only. A heading reading Sources, a note saying nothing on this screen changes what is on a hiker’s phone and that a source reaches one by a change to pipeline/sources.json that somebody merges, and — until a publish run carries registry.json — a line saying OurHike could not read the registry because it is fetched rather than carried offline. Once the artifact ships, the same screen fills with one section per organization: a stable id such as org:nynjtc, an empty dashed square where a licensed mark would go, and a table of that organization’s sources with columns for key, layer, kind, trust, what the licence rests on, whether it reaches a hiker, and freshness.'

export default async function drive(page) {
  // "More", then its "Where this map comes from" page. TWO TAPS AND THE TAB
  // IS NOT CALLED SETTINGS, both of which the first version of this recipe got
  // wrong and the camera reported as a 30 s timeout — which is exactly the
  // failure a recipe is supposed to make loud rather than a picture of the
  // wrong screen.
  //
  // The tab reads "More": MORE_TAB.md (#795) argued for "Settings" and the
  // argument was settled the other way, so the label is the one thing here not
  // to guess at (chrome/tabs.ts). And the tab is five destination rows over a
  // storage card since #796, so the sources card and the registry link live on
  // a sub-page rather than on the tab itself.
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /Where this map comes from/ }).click()

  // By its accessible name rather than by position: the section it sits in is
  // reordered by whatever else Settings gains, and a recipe pinned to an index
  // photographs the wrong screen silently.
  const open = page.getByRole('button', { name: 'The source registry' })
  await open.scrollIntoViewIfNeeded()
  await open.click()

  // Wait on a SETTLED state rather than on a delay, and accept either of the
  // two the screen can honestly reach. The registry is FETCHED rather than
  // carried offline — it is an admin screen read at a desk, and adding it to
  // the download would spend a hiker's bytes on a table they will never open —
  // so there is a real round trip between the tap and the answer.
  //
  // Either arm ends the wait; neither is "Reading the registry…", which is
  // the third state and the one a shot must never catch, because a picture of
  // a spinner says nothing about anything.
  //
  // WHY NOT JUST THE TABLE. Waiting only on the organization heading is what
  // the first version of this recipe did, and it timed out for a reason that
  // is not a defect: `registry.json` is not in the bucket yet. A recipe that
  // can only photograph the happy path reports "the pull request moved the
  // screen" when what actually happened is that the artifact has not shipped.
  await Promise.race([
    page
      .getByRole('heading', { name: /Appalachian Trail Conservancy/, level: 3 })
      .waitFor(),
    page.getByText(/couldn’t read the registry/).waitFor(),
  ])
}
