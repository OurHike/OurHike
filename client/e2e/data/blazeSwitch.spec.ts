// The legend's "Blaze colors" switch, tapped on a real map with real tiles.
//
// WHY THIS NEEDS A REAL RENDERER (#1698). Switching the hues on drew every
// trail grey until a zoom - reported twice by the maintainer, 2026-09-20 and
// 2026-09-26. Every paint write the switch makes was already correct, and
// src/map/appearanceRestore.test.ts proves that against a mock map. The grey
// was MapLibre throwing mid-frame: a blaze layer's `line-dasharray` changed
// between per-feature and absent, and a frame drawn before the tiles were
// re-laid out picked the dashed shader for a bucket with no dash in it. The
// throw also stopped the render loop, so the casings (drawn first, grey) were
// all that showed. src/map/style.ts's blazeDashArray has the whole trace. A
// mock cannot throw that way, so this is the only test that can see it.
//
// TAGGED `@desktop`, because the laptop's legend is a panel beside the map
// and the map keeps drawing while it is open. On a phone the legend sheet
// covers the canvas (#1138), so a tap there proves nothing about the frame.
//
// Measured 2026-09-26 in headless Chromium through scripts/data-proxy.mjs
// against release 2026-09-24-2, at this file's camera, with a probe script
// before this spec existed: before the fix, switching on went grey after 14
// of 18 taps; switching off drew red again but threw 2 to 3 errors per tap
// first. After it, 12 of 12 taps drew the right lines with no error. Every
// version of this spec, run locally, failed on the build before the fix and
// passed on the build with it; this one failed 1 of 1 and passed 3 of 3.
// The agent sandbox cannot draw the live topo sheet, so what these local
// runs cannot show is the background - drawnInk says how that was settled.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, seedCamera } from '../support/seed'

/** The Hudson at Dutchess Junction, z13: the camera of
 *  preview-shots/hudson-highlands-blaze-colors.mjs, the frame both reports
 *  were about. OPRHP's yellow- and blue-blazed trails over Breakneck Ridge
 *  are in it, which is what the pixel count below looks for. Nobody's
 *  location - a park, picked for its trails. */
const HUDSON_HIGHLANDS: readonly [number, number] = [-73.96, 41.47]
const HUDSON_HIGHLANDS_ZOOM = 13

/**
 * What the map frame is drawing, counted in pixels of two kinds:
 *
 *  - `hues`: a yellow or a blue blaze - within INK_TOLERANCE of the two hexes
 *    lib/blaze.ts gives them, #dcae1b and #1f5fa8. Nothing on the default
 *    sheet is either, every line there being lib/blaze.ts's red, so these
 *    can only be on screen if the hues are drawn;
 *  - `red`: within the same tolerance of that red, #b2321f - the default
 *    sheet's lines.
 *
 * TIGHT TO THE PALETTE'S OWN HEXES, AND THAT IS WHAT MAKES IT A TRAIL COUNT.
 * The first version counted any strong blue or yellow, and the live topo
 * sheet under the trails is full of blue water: CI read 388 `hues` pixels on
 * the default sheet before any tap (2026-09-26, bar 50), and 405 on the
 * downloaded background it was then moved to, from something drawn late that
 * this spec never identified. Matched within 10 of each hex instead, the
 * preview's own hues-on frame of this camera over the live sheet (CI,
 * release 2026-09-24-2) counted 2,326 yellow and 1,060 blue, against 2,343
 * and 1,084 for the same frame on bare paper in the agent sandbox - within
 * 2%, so at this tolerance the background adds nothing, and the default
 * sheet counted 0 of either. INK_TOLERANCE is 12: past 16, blue water starts
 * to count (1,598 on the CI frame at 24).
 *
 * Read off a Playwright screenshot rather than the canvas, because MapLibre
 * does not keep its drawing buffer and reading the WebGL canvas back returns
 * blank. The PNG is decoded in the page, which has an image decoder, rather
 * than here, where this package has none.
 */
async function drawnInk(page: Page): Promise<{ hues: number; red: number }> {
  const shot = await page.getByRole('region', { name: 'Trail map' }).screenshot()
  return page.evaluate(
    async ({ base64, tolerance }) => {
      const image = new Image()
      image.src = `data:image/png;base64,${base64}`
      await image.decode()
      const canvas = document.createElement('canvas')
      canvas.width = image.width
      canvas.height = image.height
      const context = canvas.getContext('2d')
      if (context === null) return { hues: -1, red: -1 }
      context.drawImage(image, 0, 0)
      const data = context.getImageData(0, 0, canvas.width, canvas.height).data
      const near = (i: number, hex: readonly [number, number, number]) =>
        Math.abs(data[i] - hex[0]) <= tolerance &&
        Math.abs(data[i + 1] - hex[1]) <= tolerance &&
        Math.abs(data[i + 2] - hex[2]) <= tolerance
      let hues = 0
      let red = 0
      for (let i = 0; i < data.length; i += 4) {
        if (near(i, [0xdc, 0xae, 0x1b]) || near(i, [0x1f, 0x5f, 0xa8])) hues++
        if (near(i, [0xb2, 0x32, 0x1f])) red++
      }
      return { hues, red }
    },
    { base64: shot.toString('base64'), tolerance: INK_TOLERANCE },
  )
}

/** How far, per channel, a pixel may sit from a palette hex and still count
 *  as that ink. drawnInk's comment has the measurement it was picked from. */
const INK_TOLERANCE = 12

/** More than this many `hues` pixels and the hues are on the map. */
const HUES_DRAWN = 300
/** Fewer than this many and they are not. */
const HUES_GONE = 50
/** More than this many `red` pixels on the default sheet and its lines are
 *  drawn - the wait before the first tap, and the check that switching off
 *  brought them back. The frame measured 3,527 at a tolerance of 10 in the
 *  agent sandbox. Not the trails' alone: the 44 px serious-warning pin is
 *  the same hex, so a frame with a few of those and no trail lines could
 *  meet this bar (reasoned from the palette; not measured) - which is why
 *  the switch-on checks count hues, and red is only ever asked of the
 *  default sheet. */
const DEFAULT_RED_DRAWN = 1_000

/** The waits below, added up: 60 s for the first lines, then four 15 s
 *  polls. The data suite's 90 s default is shorter than that, and a slow
 *  first load would then fail as a timeout on whichever poll it reached
 *  rather than on the one that saw the map stay grey. */
const SPEC_TIMEOUT_MS = 180_000

test.describe('the Blaze colors switch on a drawn map', { tag: '@desktop' }, () => {
  test('switching the hues on and off repaints the lines each time, with no render error', async ({
    page,
  }) => {
    test.setTimeout(SPEC_TIMEOUT_MS)
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))

    await seedCamera(page, HUDSON_HIGHLANDS, HUDSON_HIGHLANDS_ZOOM)
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    // WAIT ON THE LINES, NOT A TIMER (CLAUDE.md): the default sheet's own
    // red, in the frame. The legend's "Trails in view" section, which
    // e2e/data/mapSheets.spec.ts waits on, is not drawn on the desktop panel
    // until the hues are on, so it cannot be the signal before the tap.
    await expect
      .poll(async () => (await drawnInk(page)).red, { timeout: 60_000 })
      .toBeGreaterThan(DEFAULT_RED_DRAWN)
    const legend = page.getByRole('region', { name: 'Legend' })
    const blazes = legend.getByRole('switch', { name: /^Blaze colors/ })
    await expect(blazes).not.toBeChecked()
    expect((await drawnInk(page)).hues).toBeLessThan(HUES_GONE)

    // On. Before the fix this is where the frame went grey and stayed grey:
    // the poll timed out on a map whose render loop had stopped.
    await blazes.click()
    await expect(blazes).toBeChecked()
    await expect
      .poll(async () => (await drawnInk(page)).hues, { timeout: 15_000 })
      .toBeGreaterThan(HUES_DRAWN)
    expect(errors).toEqual([])

    // And off again. This direction always recovered, but threw on the way.
    // The hues going is not enough on its own: a frame with no trail lines
    // at all has none either, so the default's red has to come back too.
    await blazes.click()
    await expect(blazes).not.toBeChecked()
    await expect
      .poll(async () => (await drawnInk(page)).hues, { timeout: 15_000 })
      .toBeLessThan(HUES_GONE)
    await expect
      .poll(async () => (await drawnInk(page)).red, { timeout: 15_000 })
      .toBeGreaterThan(DEFAULT_RED_DRAWN)
    expect(errors).toEqual([])

    // On a second time: the first tap cannot be the only one that works.
    await blazes.click()
    await expect
      .poll(async () => (await drawnInk(page)).hues, { timeout: 15_000 })
      .toBeGreaterThan(HUES_DRAWN)
    expect(errors).toEqual([])
  })
})
