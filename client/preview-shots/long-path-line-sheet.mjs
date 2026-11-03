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
// AMENDED (#1307) - THE HEADING ITSELF CHANGED. The Long Path joined
// PRIMARY_TRAIL_SOURCES/THROUGH_ROUTE_SOURCES, so this exact tap now reads
// "Aqua blaze · Long Path" rather than "Aqua blaze · side trail" -
// lib/lineDetail.ts's chosenThroughRoute distinguishes a through-route the
// hiker has taken from one that is merely a through-route, and the Long
// Path is the first line to be the second kind rather than neither.
//
// AMENDED AGAIN (#1476) - THE SHEET GAINED A CLIMB ROW. The same tap now
// prints "+x ft / -y ft" under the length and the park, and the sentence
// under that saying it is an estimate, wherever the graph cell under the
// Palisades carries its climb half. This recipe is touched rather than
// replaced because it already reaches the one screen that changed, which is
// what pr-preview.yml re-photographs.
//
// AMENDED AGAIN (#1516) - THE SENTENCE UNDER THE ROW NOW HAS TWO FORMS. Where
// the climb row appears at all, the line under it is one of:
//
//   measured    "Climb is an estimate from the best elevation data
//               available - expect other sources to differ."
//   unverified  "Climb over the N mi of this trail on this phone, which may
//               not be all of it."
//
// Which one depends on whether the tapped feature carries `length_miles`.
// lineClimb.ts compares the graph edges this phone holds against that number
// to tell a whole trail from part of one; with no number it cannot tell, so
// it reports the extent it summed over instead of calling it the total. v1.3.0
// shipped that comparison against a field no exporter wrote, which is why
// every tap read `measured` however little of the line was downloaded.
//
// #1516 added the field to export_nearby_trails.records_to_geojson, so
// `unverified` is what a preview draws until a publish carries it - and it
// stays the answer afterwards for any source publishing no length. This
// recipe is touched rather than replaced for the same reason #1476 touched
// it: it already reaches the one screen that changed.
//
// WHAT THE THIRD HONEST FRAME IS, AND WHY IT IS NOT A BROKEN SHOT. The climb
// row needs the climb half in THE RELEASE THIS BUILD PINS, which is a
// narrower condition than "somebody ran a publish with include_elevation"
// and is the distinction that cost two wrong diagnoses on 2026-09-15.
//
// Measured that day, off three manifests:
//
//   production releases/2026-09-14   505 graph cells, 0 elevation cells
//   UA          releases/2026-09-14   502 graph cells, 0 elevation cells
//   UA          releases/2026-09-15-7 505 graph cells, 505 elevation cells
//
// `client/src/lib/dataRelease.ts` pins DATA_RELEASE to 2026-09-14, so BOTH
// preview modes read the top two rows. Dispatching this workflow with
// `data_environment: ua` moves the bucket PREFIX and not the release, which
// is why a UA preview taken after a successful elevation publish still drew
// no climb row. The row arrives when the pin moves to a release carrying
// the cells - a maintainer's act (RELEASING.md), not this recipe's.
//
// Until then the frame is the sheet without a climb row, which is #1476's
// own "no figures on this phone" state rendered correctly and is worth
// photographing.
//
// AND NO LENGTH OR PARK EITHER, on this particular line - the frame of
// 2026-09-15 shows neither, so the tapped Long Path feature publishes no
// `Miles` and no unit name. That is the sheet's omit-rather-than-placeholder
// rule working (lib/lineDetail.ts's extentLine collapses to null when both
// halves are absent), and this comment says so because an earlier version of
// the caption promised a length that is not there.
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
// z15, the tap lands, and the frame is the sheet: "Aqua blaze · Long Path"
// since #1307 (was "Aqua blaze · side trail"), the mark beside the name a
// second time (#1288's line, which only a CHOSEN through-route suppresses),
// the length and the park, NYNJTC's provenance line.
// Where it does not - a fork's pull request gets no secrets, and the
// archive is in the bucket only once publish-vector-data.yml has run since
// the merge - there is no line under the pixel, the tap opens nothing, and
// the frame is the map over the Palisades with the A.T. absent because this
// is not its ground. That is a true screen rather than a broken recipe, and
// the answer to "has the network published yet", which the PR body's Data
// pipelines section exists to track.

export const caption =
  'The Long Path’s line sheet. Since #1476 it says how much the trail CLIMBS — “+x ft / −y ft” — but only where the climb half is in the release this build PINS, and dataRelease.ts pins 2026-09-14, which carries zero elevation cells on production and on UA alike (all three manifests read 2026-09-15). A UA preview does not change that: it moves the bucket prefix, not the release. So the frame here is the sheet WITHOUT a climb row, which is that change’s own honest absence rendered correctly. When the pin does move to a release carrying the cells, #1516 decides the line UNDER the row: “an estimate from the best elevation data available” only where the tapped feature carries a length to check coverage against, and otherwise “Climb over the N mi of this trail on this phone, which may not be all of it” — because a phone that cannot tell whether it holds the whole line must not call the total measured'
export const alt =
  'The tapped-line sheet over the map at the Palisades, reading “Aqua blaze · Long Path”, the Long Path’s round logo beside the words “Long Path” again, and a line saying the data is from the New York-New Jersey Trail Conference. Where this build’s bucket carries per-edge climb, a climb figure written as plus-feet over minus-feet sits above that, with a note under it saying either that climb is an estimate or, where the tapped trail publishes no length to check the download against, how many miles of the trail the figure covers; where it does not, there is no such row. Where the build has no network archive at all, there is no sheet: just the map over the Palisades crest with no trail line to tap.'

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
  const sheet = page.getByRole('dialog', { name: 'Trail line' })
  await sheet.waitFor({ timeout: 10000 }).catch(() => {})

  // AND THEN THE CLIMB ROW, WHICH IS A SECOND ARRIVAL RATHER THAN PART OF
  // THE FIRST (#1476). The sheet opens on the tap with whatever is known
  // then, and the climb is not known then: the figure is summed out of the
  // junction graph's cell for this ground - 2,638,738 bytes of JSON for
  // n40w074 - and the 83,309-byte climb half is only asked for once that
  // cell has merged AND a line has been tapped. Two round trips and a parse
  // after the frame the tap produces, against a 6-second settle.
  //
  // THIS WAIT IS RIGHT AND IT WAS NOT WHAT WAS HIDING THE ROW, and saying so
  // is worth a line because the commit that added it claimed otherwise. Two
  // UA previews drew no climb row with this wait in place; the cause was the
  // pinned release, per the header above, not the settle. What the wait
  // earns is that once a release does carry the cells, the frame is the
  // figure rather than a coin toss against the network.
  //
  // .catch is the honest half and is not belt-and-braces: where the pinned
  // release carries no climb half the row never comes, and that frame - the
  // sheet without it - is #1476's own "no figures on this phone" state and
  // is worth photographing. So this waits, then takes whatever is there.
  await sheet
    .getByText(/^\+[\d,]+ (ft|m) \/ −[\d,]+ (ft|m)$/)
    .waitFor({ timeout: 15000 })
    .catch(() => {})
}
