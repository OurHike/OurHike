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
//     the layer by its registry key, "oprhp_hunting_areas", because UA's
//     stewards.json names none of the hazard sources' keys (read
//     2026-10-05: not oprhp_hunting_areas, iata_lands_hunting_regs,
//     usace_garrison_hunting_restrictions, blm_shooting_points or
//     usfs_baer_assessments). That is a gap of its own, left in the frame
//     rather than routed around.
//
// THE AREA IS INVENTED, and its title says "(example)": a box around Bear
// Mountain's summit, which the A.T. crosses (long-term-closures.mjs, at the
// same camera, says the A.T. crosses this frame). No hunting layer is
// photographed: a shot on every future pull request must never draw a real
// area where its layer did not, nor put words in an agency's mouth. Both
// files are answered on the wire before the app loads (`before`).
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix (.claude/skills/pr-screenshot/SKILL.md): no hike or
// account is seeded, a CI browser has no location fix, and at z13 the pins
// that draw here are the agencies' own published places, as
// long-term-closures.mjs records for this camera.

/** Bear Mountain's summit, on the A.T., and the box the invented area is. */
const BOX = { west: -74.02, east: -73.995, south: 41.3, north: 41.318 }
const CAMERA = { center: [-74.0075, 41.306], zoom: 13 }

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
  'The map screen over Bear Mountain State Park at zoom 13, with an invented hunting area drawn around the summit as a pale square with a dashed orange edge, under the red trail lines, and over the lower part of the map a sheet headed "Hunting allowed" with an Advisory tag, the title "Bear Mountain hunting area (example)" and a sentence saying the trail stays open. No hike is planned.'

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
  const map = page.getByRole('region', { name: /trail map/i })
  await map.waitFor()

  // Tap inside the area, east of the summit, until its sheet opens: the
  // area draws only once the hazard file, the rule behind import() and the
  // trail it crosses are all on the phone, so the first taps may land
  // before it is there. The sheet's own name is what proves it drew.
  const sheet = page.getByRole('dialog', { name: 'Hunting allowed' })
  const box = await map.boundingBox()
  if (box === null) throw new Error('the map region has no box to tap')
  // MapLibre's world is 512 px a tile, so at z13 a degree of longitude is
  // 512 * 2^13 / 360 px; the camera's centre is the region's centre.
  const pxPerDegree = (512 * 2 ** CAMERA.zoom) / 360
  const lat = (BOX.south + BOX.north) / 2
  const mercator = (degrees) =>
    Math.log(Math.tan(Math.PI / 4 + (degrees * Math.PI) / 360))
  const x = box.x + box.width / 2 + (-74.0 - CAMERA.center[0]) * pxPerDegree
  const y =
    box.y +
    box.height / 2 -
    ((mercator(lat) - mercator(CAMERA.center[1])) * pxPerDegree * 180) / Math.PI
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await page.mouse.click(x, y)
    if (await sheet.isVisible()) break
    await page.waitForTimeout(1000)
  }
  await sheet.waitFor()
}
