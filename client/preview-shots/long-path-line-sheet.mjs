// The Long Path's line sheet, with the trail's own mark beside its name
// (#1288).
//
// THE SCREEN THIS CHANGE IS ABOUT. Tapping any line opens the sheet that
// names the blaze and the trail (WIREFRAMES.md §3, features/NEARBY_TRAILS.md
// §2). Since #1288 the sheet also draws the trail's mark beside its name
// where lib/trails.ts knows one, and the Long Path is the first nearby trail
// that does - NYNJTC's logo, on the maintainer's authorisation recorded in
// pipeline/sources.json's org_marks. Nothing photographed a nearby trail's
// sheet before this recipe existed.
//
// A TAP AT THE CAMERA'S OWN CENTRE, because a drive cannot aim a canvas
// click at a line unless it knows what is under the pixel - and it does,
// exactly once: the camera's centre is a lon/lat this recipe chose, and the
// centre of the canvas is that point. The camera is seeded through
// lib/cameraMemory.ts's session-storage key, as basemap-ground-network.mjs
// does and for its reasons, on a vertex of the Long Path's own line in
// NYNJTC's layer - the Palisades crest above the Hudson, section 1 of their
// guide, between Alpine Lookout and the state line. Zoom 15 keeps the
// vertex under the centre pixel within map/lineTaps.ts's tap box and puts
// no other blazed trail in it. Public ground throughout: a cliff-edge path
// in a state park, no campsite, nobody's report, nobody's fix (the four
// things .claude/skills/pr-screenshot/SKILL.md says must never appear).
//
// TWO HONEST FRAMES, ONE RECIPE - the shape day-hike-builder.mjs already
// ships, and the caption names both because photograph-preview.mjs reads it
// off the module before the drive runs (#1058). Where the bucket this
// preview reads carries nearby_trails.pmtiles, the line is on the canvas at
// z15, the tap lands, and the frame is the sheet: "Aqua blaze · side trail",
// the mark, "Long Path", the length and the park, NYNJTC's provenance line.
// Where it does not - a fork's pull request gets no secrets, and the
// archive is in the bucket only once publish-vector-data.yml has run since
// the merge - there is no line under the pixel, the tap opens nothing, and
// the frame is the map over the Palisades with the A.T. absent because this
// is not its ground. That is a true screen rather than a broken recipe, and
// the answer to "has the network published yet", which the PR body's Data
// pipelines section exists to track.

export const caption =
  'The Long Path’s line sheet — the trail’s own mark beside its name (#1288); the bare map over the Palisades until nearby_trails.pmtiles is in the bucket this preview reads'
export const alt =
  'Either the tapped-line sheet over the map at the Palisades, reading “Aqua blaze · side trail”, then the Long Path’s round logo beside the words “Long Path”, its length and park, and a line saying the data is from the New York-New Jersey Trail Conference; or, where this build has no network archive, the map over the Palisades crest with no trail line to tap.'

/** Vector tiles from the bucket plus contours over a cliff take longer than
 *  chrome; the sheet is waited on by the drive, this is the settle after. */
export const wait = 6000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read back
  // with every field validated, and null on anything that does not convince.
  // The centre is vertex 939 of section 1 in NYNJTC's Long_Path_2023 layer
  // (read 2026-09-08), so the line passes through the centre pixel exactly.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-73.926890961823, 40.9288700881624], zoom: 15 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the CONTEXT (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()

  // The tiles under the centre pixel have to be drawn before a tap can find a
  // line in them; the settle here is the range-read of one tile plus its
  // style pass, generous for a cold preview.
  await page.waitForTimeout(6000)

  const canvas = page.locator('canvas.maplibregl-canvas').first()
  const box = await canvas.boundingBox()
  if (box === null) return
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } })

  // The sheet, by its role and name (chrome/LineSheet.tsx). Waited on rather
  // than assumed, and let go where nothing opens: that is the second frame.
  await page
    .getByRole('dialog', { name: 'Trail line' })
    .waitFor({ timeout: 10000 })
    .catch(() => {})
}
