// A club's trail line in the opening sketch, drawn as every other
// organization's line is (decision 64).
//
// WHAT THIS FRAME IS EVIDENCE FOR. Decision 64 (pipeline/ELT.md's decisions
// table, chosen by poll 2026-10-04) draws the clubs' own trail lines and
// routes none of them. In network_overview.geojson a club's lines are one
// group per (source, blaze colour), after every network group, carrying
// `line_kind: 'club'` and no `trail_status` (the pipeline's
// int_trail_lines__network_overview_features). The client draws the sketch
// by source alone, so a club group takes the other-organization style the
// default sheet already gives the haze - thinner, dashed, the same red
// (#1597) - and nothing in map/ was changed to make it so. That sameness is
// what this frame is for.
//
// THE LINE IS INVENTED, AND THE CAPTION SAYS SO. The recipe was written
// against a release published before decision 64 was built, whose sketch no
// feature carried `line_kind` in (UA's 2026-10-03-2, read 2026-10-04: 0 of
// 211). So the recipe's `before` appends one club group to the pinned
// release's network_overview.geojson on the way in and rewrites the
// manifest's hash to match (fixtures/releaseInjection.mjs): a W-shaped line
// across central Nevada, source key `preview_fixture`, which no organization
// holds. There is no claim that a trail is there.
//
// THE PINNED RELEASE HAS CLUB LINES OF ITS OWN NOW, and two cross this frame.
// 2026-10-10-2, pinned since 2026-10-15, carries 12 club groups, and the
// Arizona Trail Association's and BLM's Old Spanish National Historic Trail
// lines have vertices inside the view this camera spans (Measured 2026-10-15
// against its sketch, for a 390 x 844 map at z4.6; Reasoned that the map
// fills the phone). They draw in the same style beside the invented line. A
// recipe framing one of them, with no invented line, is the stronger
// picture and has not been written.
//
// THE WHOLE SKETCH DRAWS. Until 2026-10-15 the edit also cut the sketch to
// this frame, because 2026-10-03-2's was 41,216,145 bytes decoded, over the
// 33,554,432-byte launch budget (lib/artifactBudget.ts, #1254), and the app
// declined it at the manifest and drew no sketch at all. 2026-10-10-2's is
// 2,710,574 bytes, so the published features arrive as published, with the
// invented group appended.
//
// WHY NO SHEET. A club group in the sketch carries no `name`, like the
// network's own haze groups, and map/lineTaps.ts opens nothing on an unnamed
// line, so a tap at this zoom answers nothing. A club line's sheet
// (chrome/LineSheet.tsx's "Club line" note) opens from the tiled band
// (nearby_trails.pmtiles, z5 up), which a recipe cannot edit on the way in -
// it is read by range, tile by tile. 2026-10-03-2, built before decision 64,
// had no club line to tile; whether 2026-10-10-2's tiles carry its 12 has not
// been read. Until a recipe opens one, lib/lineDetail.test.ts and
// chrome/LineSheet.test.tsx hold that sheet.
//
// The camera is seeded through lib/cameraMemory.ts's session-storage key at
// z4.6: under the sketch's ceiling (map/style.ts's NETWORK_SKETCH_MAX_ZOOM,
// 5), where the sketch is what draws. Seeded by an init script in `before`
// rather than by long-path-line-sheet.mjs's write-and-reload, because a
// reload drops the manifest request while the sketch is being fetched to
// edit, which ended one sandbox capture with the route's own error.
//
// NOTHING HERE IS ANYBODY'S: an invented line over public desert, no
// account, no report, no location fix, no campsite.
import { injectIntoRelease } from './fixtures/releaseInjection.mjs'

export const caption =
  'Decision 64: a club’s trail line in the opening sketch, drawn in the style every other organization’s line already has (thinner, dashed, the same red). The W-shaped line across central Nevada is INVENTED, added to the pinned release’s network_overview.geojson by the recipe, which was written before any release carried a club line; the pinned release’s own club lines, the Arizona Trail’s and the Old Spanish Trail’s, cross this frame too, drawn the same way'
export const alt =
  'The map zoomed out over central Nevada, with a thin dashed red W-shaped line at the centre among the other thin dashed red lines of the trail network; no sheet is open.'

/** The settle after the drive's wait below: the sketch's parse and first
 *  draw, which came some seconds after the manifest in the sandbox. */
export const wait = 12000

const CENTER = [-116.5, 39.4]
const ZOOM = 4.6

const W_LINE = [
  [-117.2, 39.0],
  [-116.85, 39.8],
  [-116.5, 39.1],
  [-116.15, 39.8],
  [-115.8, 39.0],
]

export async function before(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read once
  // when App.tsx first renders.
  await page.addInitScript(
    ([center, zoom]) => {
      sessionStorage.setItem('ourhike:camera', JSON.stringify({ center, zoom }))
    },
    [CENTER, ZOOM],
  )
  await injectIntoRelease(page, {
    'network_overview.geojson': (published) => ({
      ...published,
      features: [
        ...(published.features ?? []),
        {
          type: 'Feature',
          geometry: { type: 'MultiLineString', coordinates: [W_LINE] },
          properties: {
            source: 'preview_fixture',
            blaze_color: 'Unknown',
            line_kind: 'club',
          },
        },
      ],
    }),
  })
}

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
  // The header's In view door (in-view.mjs) appears once the release's
  // waypoints are on the phone, which is after the manifest this recipe
  // holds back until the sketch is edited: the first thing on screen that
  // proves the edited manifest arrived. Let go where it never comes (a build
  // with no waypoint data), and the settle above takes whatever is there.
  await page
    .getByRole('button', { name: /^In view, \d+/ })
    .waitFor({ timeout: 40000 })
    .catch(() => {})
}
