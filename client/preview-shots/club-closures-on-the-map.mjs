// Every club closure on the map (the maintainer's polls of 2026-10-11: Q2
// "Build the map file now", and standard S6 as drawn in s6-map.html), from
// conditions/trail_closures.json, read at launch with no hike planned.
//
// WHAT A REVIEWER SHOULD CHECK IN THE FRAME, against S6's "the standard,
// drawn" and lib/closureStyle.ts's crossed-out mark (a band of the sheet's
// paper, a dotted trace on it, a chain of small dark crosses along it):
//
//  1. Top: "Example Ridge Trail fire closure", a line closure, crossed out
//     along its own line.
//  2. Middle right: "Example Lake State Park closed", an area closure, drawn
//     as the two trail stretches cut inside the park, each crossed out. The
//     park's edge is not drawn: S6's mock drew it, and said "mock only".
//  3. Lower left: "Bridge out at Example Creek", a point closure, one larger
//     cross - the far mark, at the point.
//  4. Bottom: "Example Canyon Trail closed", a closure the list greys (its
//     source gives no date), crossed out at the SAME full strength as the
//     others - the maintainer's "B: same mark", not faded.
//
// No sheet is left open: the drive taps the point's cross until its sheet
// opens - the proof the file, its reader and map/clubClosureTaps.ts have all
// landed, since nothing else on screen says so - and closes it again.
//
// EVERY CLOSURE AND ORGANIZATION IS INVENTED (fixtures/clubClosures.mjs),
// over Kansas farmland, and the file is answered on the wire before the app
// loads (`before`), whatever the bucket serves. Nothing here reaches an
// account, a hiker's own report, a dispersed campsite or a real location fix
// (.claude/skills/pr-screenshot/SKILL.md): nothing is seeded but the camera,
// and a CI browser has no location fix.
import {
  routeTrailClosures,
  TRAIL_CLOSURES_CAMERA,
  trailClosureRows,
} from './fixtures/clubClosures.mjs'

export const caption =
  'Every club closure crossed out on the map, from conditions/trail_closures.json read at launch with no hike planned (the maintainer’s S6, 2026-10-11): a line closure along its own line, an area closure’s two trail stretches inside the park, one cross for a bridge out, and a closure the list greys drawn at the same full strength. Every closure and organization is an invented example, over farmland.'

export const alt =
  'The map screen at zoom 13 over farmland. Four invented closures are drawn with the crossed-out mark: near the top a long line drawn as a pale band carrying a dotted dark line with a chain of small dark x marks along it; to the right of the middle two short stretches meeting at a point, drawn the same way; lower left a single larger dark x with a pale edge; and near the bottom another long line, drawn exactly as the first. No sheet is open.'

/** Vector basemap tiles at z13, the allowance long-term-closures.mjs makes
 *  for a frame at this zoom. */
export const wait = 22000

export const before = routeTrailClosures

/** How long the drive taps the point closure before it gives up: the
 *  ceiling hazard-area-no-plan.mjs keeps for the same wait, on the same
 *  reasoning (nobody has timed it on a preview). */
const TAP_FOR_MS = 45_000

/** A lon/lat as a point on the map canvas at the camera: MapLibre's world is
 *  512 px a tile, so at zoom z a degree of longitude is 512 * 2^z / 360 px,
 *  and with no map padding the camera's centre is the canvas's centre
 *  (hazard-area-no-plan.mjs's canvasPoint). */
function canvasPoint([lon, lat], box) {
  const { center, zoom } = TRAIL_CLOSURES_CAMERA
  const pxPerDegree = (512 * 2 ** zoom) / 360
  const mercator = (degrees) =>
    (Math.log(Math.tan(Math.PI / 4 + (degrees * Math.PI) / 360)) * 180) / Math.PI
  return {
    x: box.width / 2 + (lon - center[0]) * pxPerDegree,
    y: box.height / 2 - (mercator(lat) - mercator(center[1])) * pxPerDegree,
  }
}

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, as long-term-closures.mjs seeds it.
  await page.evaluate((camera) => {
    sessionStorage.setItem('ourhike:camera', JSON.stringify(camera))
  }, TRAIL_CLOSURES_CAMERA)
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Map' }).click()
  const canvas = page.locator('canvas.maplibregl-canvas').first()
  await canvas.waitFor()
  const box = await canvas.boundingBox()
  if (box === null) throw new Error('the map canvas has no box to tap')
  const position = canvasPoint(trailClosureRows().point.place.geometry.coordinates, box)

  // Tap the bridge's cross until its sheet opens. A tap before the file, its
  // reader and the closures' chunk have landed opens nothing, so tapping
  // early costs nothing.
  const sheet = page.getByRole('dialog', { name: 'Closure notice' })
  const deadline = Date.now() + TAP_FOR_MS
  while (!(await sheet.isVisible())) {
    if (Date.now() > deadline) {
      throw new Error(
        `no "Closure notice" sheet after ${TAP_FOR_MS / 1000} s of taps on the ` +
          'invented bridge closure: the closures did not draw, or something ' +
          'drawn over the cross takes the tap',
      )
    }
    try {
      await canvas.click({ position, timeout: 5000 })
    } catch (error) {
      if (await sheet.isVisible()) break
      throw error
    }
    await sheet.waitFor({ timeout: 1500 }).catch(() => undefined)
  }
  await sheet.getByText('Bridge out at Example Creek (example)').waitFor()
  await sheet.getByRole('button', { name: 'Close' }).click()
  await sheet.waitFor({ state: 'hidden' })
}
