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
// THE LINE IS INVENTED, AND THE CAPTION SAYS SO. The release this build pins
// (lib/dataRelease.ts) was published before decision 64 was built, and no
// feature in its sketch carries `line_kind` (UA's 2026-10-03-2, read
// 2026-10-04: 0 of 211). So the recipe's `before` appends one club group to
// that release's network_overview.geojson on the way in and rewrites the
// manifest's hash to match (fixtures/releaseInjection.mjs): a W-shaped line
// across central Nevada, source key `preview_fixture`, which no organization
// holds. There is no claim that a trail is there.
//
// AND THE SKETCH IS CUT TO THE FRAME, which is the part a reader would not
// guess. UA's 2026-10-03-2 sketch is 41,216,145 bytes decoded, over the
// 33,554,432-byte launch budget (lib/artifactBudget.ts, #1254), so the app
// declines it at the manifest and draws no sketch at all - measured in the
// sandbox 2026-10-04, the console's own warning. The edit keeps only the
// published features with a vertex inside FRAME, unchanged, so what draws
// around the invented line is the pinned release's own haze for that
// ground (BLM's and USFS's) and nothing is moved or restyled. Where a
// release's sketch is under the budget the cut changes nothing on screen.
//
// WHY NO SHEET. A club group in the sketch carries no `name`, like the
// network's own haze groups, and map/lineTaps.ts opens nothing on an unnamed
// line, so a tap at this zoom answers nothing. A club line's sheet
// (chrome/LineSheet.tsx's "Club line" note) opens from the tiled band
// (nearby_trails.pmtiles, z5 up), which a recipe cannot edit on the way in -
// it is read by range, tile by tile - and which carries no club line until a
// release is published with one. lib/lineDetail.test.ts and
// chrome/LineSheet.test.tsx hold that sheet until then.
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
  'Decision 64: a club’s trail line in the opening sketch, drawn in the style every other organization’s line already has (thinner, dashed, the same red). The W-shaped line across central Nevada is INVENTED, added to the pinned release’s network_overview.geojson by the recipe, because no published release carries a club line yet; the rest of the sketch is cut to this frame, because the pinned sketch is over the app’s launch budget and would otherwise not draw at all'
export const alt =
  'The map zoomed out over central Nevada, with a thin dashed red W-shaped line at the centre among the other thin dashed red lines of the trail network; no sheet is open.'

/** The settle after the drive's wait below: the sketch's parse and first
 *  draw, which came some seconds after the manifest in the sandbox. */
export const wait = 12000

const CENTER = [-116.5, 39.4]
const ZOOM = 4.6

/** [west, south, east, north]: wider than a 390 px phone at ZOOM, so no
 *  feature that reaches the screen is cut. */
const FRAME = [-121, 35.5, -112, 43.5]

const W_LINE = [
  [-117.2, 39.0],
  [-116.85, 39.8],
  [-116.5, 39.1],
  [-116.15, 39.8],
  [-115.8, 39.0],
]

function crossesFrame(feature) {
  const geometry = feature.geometry ?? {}
  const lines =
    geometry.type === 'MultiLineString'
      ? geometry.coordinates
      : geometry.type === 'LineString'
        ? [geometry.coordinates]
        : []
  const [west, south, east, north] = FRAME
  return lines.some((line) =>
    line.some(([lon, lat]) => lon >= west && lon <= east && lat >= south && lat <= north),
  )
}

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
        ...(published.features ?? []).filter(crossesFrame),
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
