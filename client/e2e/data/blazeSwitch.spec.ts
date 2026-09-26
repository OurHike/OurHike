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
// first. After it, 12 of 12 taps drew the right lines with no error. This
// spec itself, run locally, failed every run on the build before the fix
// (5 of 5) and passed every run on the build with it (9 of 9).

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
 *  - `hues`: clearly a yellow or a blue blaze - the two hues lib/blaze.ts
 *    gives #dcae1b and #1f5fa8. Nothing on the default sheet is either,
 *    every line there being lib/blaze.ts's red, so these can only be on
 *    screen if the hues are drawn;
 *  - `red`: clearly that red, #b2321f - the default sheet's lines.
 *
 * Measured 2026-09-26 by this function at this camera, release 2026-09-24-2:
 * 2 `hues` and 4,480 `red` on the default sheet, 4,114 and 1,068 with the
 * hues on, and 2 `hues` on the grey frame the defect left (three runs before
 * the fix, all three failing at the first poll below). The thresholds sit
 * well inside both ends, so one trail changing in a release does not move
 * the verdict.
 *
 * Read off a Playwright screenshot rather than the canvas, because MapLibre
 * does not keep its drawing buffer and reading the WebGL canvas back returns
 * blank. The PNG is decoded in the page, which has an image decoder, rather
 * than here, where this package has none.
 */
async function drawnInk(page: Page): Promise<{ hues: number; red: number }> {
  const shot = await page.getByRole('region', { name: 'Trail map' }).screenshot()
  return page.evaluate(async (base64) => {
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
    let hues = 0
    let red = 0
    for (let i = 0; i < data.length; i += 4) {
      const [r, g, b] = [data[i], data[i + 1], data[i + 2]]
      const yellow = r > 190 && g > 140 && g < 200 && b < 80
      const blue = r < 70 && g > 70 && g < 120 && b > 140
      if (yellow || blue) hues++
      if (r > 150 && g < 80 && b < 60) red++
    }
    return { hues, red }
  }, shot.toString('base64'))
}

/** More than this many `hues` pixels and the hues are on the map. */
const HUES_DRAWN = 300
/** Fewer than this many and they are not. */
const HUES_GONE = 50
/** More than this many `red` pixels on the default sheet and its lines are
 *  drawn - the wait before the first tap. */
const DEFAULT_RED_DRAWN = 1_000

test.describe('the Blaze colors switch on a drawn map', { tag: '@desktop' }, () => {
  test('switching the hues on and off repaints the lines each time, with no render error', async ({
    page,
  }) => {
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))

    await seedCamera(page, HUDSON_HIGHLANDS, HUDSON_HIGHLANDS_ZOOM)
    // THE DOWNLOADED BACKGROUND, with nothing downloaded: plain paper under
    // the trails, and no network request for background tiles. The live
    // sheet draws the Hudson, its creeks and its reservoirs in blues that
    // `drawnInk` counts as a blue blaze - measured on this spec's first CI
    // run, 2026-09-26: 388 `hues` pixels on the default sheet before any
    // tap, against a bar of 50. The defect is in the trail layers, which
    // draw the same over either background, so the paper costs this test
    // nothing and makes the count mean only the trails.
    await seedPreferences(page, { background_source: 'usgs_topo_offline' })
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
    await blazes.click()
    await expect(blazes).not.toBeChecked()
    await expect
      .poll(async () => (await drawnInk(page)).hues, { timeout: 15_000 })
      .toBeLessThan(HUES_GONE)
    expect(errors).toEqual([])

    // On a second time: the first tap cannot be the only one that works.
    await blazes.click()
    await expect
      .poll(async () => (await drawnInk(page)).hues, { timeout: 15_000 })
      .toBeGreaterThan(HUES_DRAWN)
    expect(errors).toEqual([])
  })
})
