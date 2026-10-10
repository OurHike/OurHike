// A hunting area drawn over the A.T. on a phone with no hike planned
// (#1805, decision 84).
//
// WHY THIS SCREEN NEEDED A CAMERA. Decision 77 has a phone download
// conditions/notices.json only once a hike is planned, and decision 67's
// hunting areas, shooting sites and burned areas were drawn from that file
// alone, so a phone with nothing planned drew none of them, and a tapped
// stretch inside one lost its advisory. The maintainer's answer (poll,
// 2026-10-05, Q5): "Their own small file, read at launch" -
// conditions/hazard_areas.json, which lib/publishedNotices.ts reads whatever
// is planned. No recipe photographed a hazard area on the map before this
// one: planned-hike-notices.mjs shows the hunting area's row in the panel,
// which needs a planned hike.
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME:
//
//  1. The map at Bear Mountain at z13 with an area drawn under the trails,
//     in decision 67's hunting colour, around the A.T. over the summit. No
//     hike is planned: nothing is seeded, and conditions/notices.json is
//     answered 404 below, so the area can only have come from the hazard
//     file.
//  2. The area's sheet, opened by a tap inside it: "Hunting allowed", the
//     Advisory tag, the invented title, and the sentence that the trail
//     stays open. Never barrier tape and never a closure. The sheet names
//     its publisher, "From New York State Office of Parks, Recreation and
//     Historic Preservation", where it said "...Preservation's layer" (the
//     preview of 6fca5e91) until the word-choice review of #1805
//     (2026-10-09) took "layer", a GIS word, off the card; its dates line
//     says that publisher gives no season dates. UA's stewards.json
//     still names none of the hazard sources' keys (release 2026-10-03-2,
//     read 2026-10-07: not oprhp_hunting_areas, iata_lands_hunting_regs,
//     usace_garrison_hunting_restrictions, blm_shooting_points or
//     usfs_baer_assessments), so the name is the steward it lists for the
//     row's provider, "NYS OPRHP" - lib/notices.ts's noticeOrgLabel, since
//     09c4da87. Before that commit the sheet printed the raw key,
//     "oprhp_hunting_areas", which is what this line used to say.
//
// THE AREA IS INVENTED, and its title says "(example)": a box around Bear
// Mountain's summit, which the A.T. crosses (long-term-closures.mjs, at the
// same camera, says the A.T. crosses this frame). No hunting layer is
// photographed: a shot on every future pull request must never draw a real
// area where its layer did not, nor put words in an agency's mouth. Both
// files are answered on the wire before the app loads (`before`).
//
// NOTHING IS DOWNLOADED OR PLANNED TO MAKE THE AREA DRAW. lib/hazardAreas.ts
// draws an area only where a trail on the phone runs through it, and the
// A.T. is on every phone with signal without a tap: lib/useTrailData.ts
// fetches the trail lines at launch and builds lib/trailPosition.ts's index
// from them. The A.T.'s centerline runs through BOX (measured below), so that
// index is enough.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix (.claude/skills/pr-screenshot/SKILL.md): no hike or
// account is seeded, a CI browser has no location fix, and at z13 the pins
// that draw here are the agencies' own published places, as
// long-term-closures.mjs records for this camera.

/** Bear Mountain's summit, on the A.T., and the box the invented area is. */
const BOX = { west: -74.02, east: -73.995, south: 41.3, north: 41.318 }
const CAMERA = { center: [-74.0075, 41.306], zoom: 13 }

/**
 * Where the drive taps: inside BOX, on ground with no trail line and no
 * waypoint near it. map/hazardAreaTaps.ts puts an area LAST IN LINE, so a
 * warning pin, a waypoint pin, closure tape, an ATC band or a trail line
 * within a thumb of the tap takes it first, and the area's sheet never opens.
 *
 * Measured 2026-10-07 against UA's release 2026-10-03-2, the one
 * lib/dataRelease.ts pins: at z13 this point is 71 px from the nearest trail
 * line (the A.T. and its side trails in trails.geojson, and every line in
 * nearby_trails.pmtiles's z13 tiles over the park) and 70 px from the
 * nearest waypoint (nearby_poi.geojson and the poi_*.geojson files). A line
 * takes a tap within map/lineTaps.ts's LINE_TAP_SLOP_PX (19.75 px) of it,
 * plus half its width.
 *
 * WHY THE FIRST VERSION PHOTOGRAPHED ON ONE PREVIEW IN THREE. It tapped
 * (-74.0, 41.309), which the same measurement puts 8.5 px from the A.T.'s
 * own centerline, and no other line within 45 px. Once the A.T. is drawn,
 * every tap there opens the A.T.'s "Trail line" sheet. The area's own sheet
 * opened only for a tap that landed after the area was drawn and before the
 * A.T. was. Which of the two is drawn first after the reload varies. Run
 * locally against UA's data on 2026-10-07 (dev server), the unchanged
 * recipe failed once (taps 2 to 20 all opened "Trail line") and passed once
 * (tap 2 opened "Hunting allowed"). On previews it failed on 4d4493d2 and
 * 484b0210 and passed on 6fca5e91. Why the order varies is reasoned, not
 * traced: after the reload the A.T.'s index comes back from
 * lib/trailIndexBuild.ts's per-release cache, while MapLibre has to tile
 * trails.geojson again before the line is drawn. More taps or a longer
 * wait would not have helped: once the A.T. is drawn, no tap there reaches
 * the area.
 * Ground a tap can reach the area through is scarce here: sampled every
 * 4 px, about 28% of BOX at z13 is clear of every line's tap box and every
 * waypoint.
 *
 * A later release can put a trail or a waypoint on this spot. If the drive
 * fails saying another sheet opened, measure again against the release the
 * build pins.
 */
const TAP = [-74.0174, 41.3099]

/**
 * How long the drive keeps tapping before it gives up. A ceiling, not the
 * fix: the first version tapped for about 20 s and then waited 30 s more,
 * and this is a little under the two together. Locally the drive reached
 * the sheet 4 to 8 s after it began, reload included, on four runs (dev
 * server with UA's data, 2026-10-07); nobody has timed it on a preview.
 */
const TAP_FOR_MS = 45_000

/** A lon/lat as a point on the map canvas, at CAMERA. MapLibre's world is
 *  512 px a tile, so at z13 a degree of longitude is 512 * 2^13 / 360 px,
 *  and with no map padding the camera's centre is the canvas's centre. */
function canvasPoint([lon, lat], box) {
  const pxPerDegree = (512 * 2 ** CAMERA.zoom) / 360
  const mercator = (degrees) =>
    (Math.log(Math.tan(Math.PI / 4 + (degrees * Math.PI) / 360)) * 180) / Math.PI
  return {
    x: box.width / 2 + (lon - CAMERA.center[0]) * pxPerDegree,
    y: box.height / 2 - (mercator(lat) - mercator(CAMERA.center[1])) * pxPerDegree,
  }
}

/** conditions/hazard_areas.json, in the shape pub_conditions_hazard_areas
 *  writes: notices.json's own rows, the hazard ones only. */
export function hazardAreasDocument() {
  const stamp = new Date(Date.now() - 3_600_000).toISOString().slice(0, 19) + 'Z'
  return {
    generated_at: stamp,
    notices: [
      {
        notice_id: 'oprhp_hunting_areas:example-bear-mountain',
        source_key: 'oprhp_hunting_areas',
        club: 'nysparks',
        provider: 'NYS OPRHP',
        steward_kind: 'agency',
        title: 'Bear Mountain hunting area (example)',
        category: 'Hunting area',
        locality: 'Bear Mountain State Park',
        place: {
          kind: 'geometry',
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [BOX.west, BOX.south],
                [BOX.east, BOX.south],
                [BOX.east, BOX.north],
                [BOX.west, BOX.north],
                [BOX.west, BOX.south],
              ],
            ],
          },
        },
        hazard: 'hunting',
        obstructs_trail: false,
        starts_on: null,
        ends_on: null,
        updated_at: null,
        checked_at: stamp,
        first_seen_at: stamp,
        changed_at: stamp,
        carried_since: null,
        source_url: 'https://parks.ny.gov/',
        review_state: 'unreviewed',
      },
    ],
  }
}

export const caption =
  'A hunting area drawn over the A.T. at Bear Mountain with no hike planned, from conditions/hazard_areas.json, and its sheet: hunting allowed, the trail stays open (decision 84, #1805). The area is an invented example.'

export const alt =
  'The map screen over Bear Mountain State Park at zoom 13, with an invented hunting area drawn around the summit as a pale square with a dashed orange edge, under the red trail lines, and over the lower part of the map a sheet headed "Hunting allowed" with an Advisory tag, the title "Bear Mountain hunting area (example)", a sentence saying the trail stays open, a line saying the publisher gives no season dates, and "From" with the publisher’s name. No hike is planned.'

/** Vector tiles and the trail data over a park at z13, the allowance
 *  long-term-closures.mjs makes at this camera. */
export const wait = 22000

/** The hazard file, and a 404 for notices.json, before the app loads. */
export async function before(page) {
  await page.route(/\/conditions\/hazard_areas\.json(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(hazardAreasDocument()),
    }),
  )
  await page.route(/\/conditions\/notices\.json(\?|$)/, (route) =>
    route.fulfill({ status: 404, body: '' }),
  )
}

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, as long-term-closures.mjs seeds it.
  await page.evaluate((camera) => {
    sessionStorage.setItem('ourhike:camera', JSON.stringify(camera))
  }, CAMERA)
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Map' }).click()

  // The canvas, not the region around it: a click on the canvas locator is
  // refused if any chrome covers the point, so a tap under a button fails
  // here by name instead of reading as a missing sheet. On the 390x844 phone
  // the canvas is 390x772 and TAP lands near (80, 326), clear of the header
  // plate and the map buttons (dev server, 2026-10-07).
  const canvas = page.locator('canvas.maplibregl-canvas').first()
  await canvas.waitFor()
  const box = await canvas.boundingBox()
  if (box === null) throw new Error('the map canvas has no box to tap')
  const position = canvasPoint(TAP, box)

  // Tap until the area's sheet opens. The area draws only once the hazard
  // file, the A.T.'s index and the two chunks behind import()
  // (lib/noticeSelection.ts, map/hazardAreaTaps.ts) are all on the phone,
  // and nothing on screen says when that is; the sheet's own name is the
  // first proof the app gives. A tap on TAP before then opens nothing,
  // because nothing else is drawn there (measured locally, 2026-10-07: 29
  // taps over 45 s on a build with no data opened no sheet), so tapping
  // early costs nothing and the drive does not depend on which part of the
  // map draws first.
  const sheet = page.getByRole('dialog', { name: 'Hunting allowed' })
  // Every sheet a map tap opens is a dialog (the A.T.'s is "Trail line",
  // chrome/LineSheet.tsx). One that was not open before the taps means
  // something now sits within a thumb of TAP, and more taps will not help.
  const openDialogs = () =>
    page
      .getByRole('dialog')
      .evaluateAll((found) =>
        found.map(
          (dialog) =>
            dialog.getAttribute('aria-label') ?? (dialog.textContent ?? '').slice(0, 60),
        ),
      )
  const openBefore = new Set(await openDialogs())
  const deadline = Date.now() + TAP_FOR_MS
  while (!(await sheet.isVisible())) {
    const opened = (await openDialogs()).filter(
      (name) => !openBefore.has(name) && name !== 'Hunting allowed',
    )
    if (opened.length > 0) {
      throw new Error(
        `a tap at ${TAP.join(', ')} opened "${opened.join('", "')}" and not the ` +
          'hunting area: something is drawn there now, so measure TAP again',
      )
    }
    if (Date.now() > deadline) {
      throw new Error(
        `no "Hunting allowed" sheet after ${TAP_FOR_MS / 1000} s of taps at ` +
          `${TAP.join(', ')}: the area did not draw, or nothing reaches it`,
      )
    }
    try {
      await canvas.click({ position, timeout: 5000 })
    } catch (error) {
      // The sheet opening over the point mid-click is the one refusal that
      // means the drive has worked.
      if (await sheet.isVisible()) break
      throw error
    }
    await sheet.waitFor({ timeout: 1500 }).catch(() => undefined)
  }
}
