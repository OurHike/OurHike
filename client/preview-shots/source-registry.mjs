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
export const caption =
  'The source registry — every registration, including the ones no hiker sees (#929)'
export const alt =
  'A read-only table of the source registry, grouped by organization. Each group has a heading, a stable id such as org:nynjtc, an empty dashed square where a licensed mark would go, and a table of that organization’s sources with columns for key, layer, kind, trust, what the licence rests on, whether it reaches a hiker, and freshness. Rows that ship on the maintainer’s own authorisation are tinted and read “Your call”; rows on the organization’s stated terms read “Their terms”. A note at the top says nothing on the screen changes what is on a hiker’s phone.'

export default async function drive(page) {
  // Settings, where the registry sits directly under "Where this map comes
  // from" — the same question one level down.
  await page.getByRole('tab', { name: 'Settings' }).click()

  // By its accessible name rather than by position: the section it sits in is
  // reordered by whatever else Settings gains, and a recipe pinned to an index
  // photographs the wrong screen silently.
  const open = page.getByRole('button', { name: 'The source registry' })
  await open.scrollIntoViewIfNeeded()
  await open.click()

  // Wait on the table itself rather than on a delay. The registry is FETCHED
  // rather than carried offline — it is an admin screen read at a desk, and
  // adding it to the download would spend a hiker's bytes on a table they will
  // never open — so there is a real round trip between the tap and the rows.
  //
  // On the organization heading rather than on the dialog: the dialog appears
  // as soon as the screen mounts, while it still says "Reading the registry…",
  // and a shot taken then is a picture of a spinner.
  await page
    .getByRole('heading', { name: /Appalachian Trail Conservancy/, level: 3 })
    .waitFor()
}
