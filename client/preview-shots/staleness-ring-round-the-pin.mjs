// The staleness ring, round the pin it belongs to (#1636, v1.3.2 release
// review).
//
// WHAT THIS FRAME IS EVIDENCE FOR. Since the jigger (2026-09-20) every pin
// stands on its point - `icon-anchor: 'bottom'` - and the ring, a circle
// layer centred on that point, stayed where it was and cut through the lower
// half of the pin. Since #1676 (2026-09-26) the ring is painted into the
// pin's own image (map/stalenessRing.ts's composeRingedPin), round the disc's
// centre, so in this frame each water pin should sit INSIDE its faint blue
// ring, not above it - and a spring that lost its pin to a neighbour is a
// plain dot with no ring beside it, because the ring goes where the pin goes.
//
// WHY WATER ONLY, AND WHY HERE. Never-confirmed water is the one category
// that wears a ring on day one (lib/stalenessDisplay.ts, #256), and at a
// planning zoom most springs are dots, which wear no ring - which is why
// waypoints-at-the-carry-zoom.mjs shows few. So this is the walking zoom over
// quiet ground: the
// A.T. through Shenandoah by Blackrock (z14), public land, with the legend's
// Showing picker narrowed to water through the stored preference.
//
// THE CAMERA MOVED 1.6 KM SOUTH ON 2026-09-26 (#1676), to -78.437, 38.532.
// The old centre, -78.439, 38.546, photographed no trail line and no spring
// at all, on `main` and on #1681's branch alike, in CI and in the agent
// sandbox. The nearest springs in the pinned release's poi_water.geojson
// (2026-09-24-2) sit at 38.530-38.532, just off the bottom of that frame.
// Here, three of them lie within about 100 m of each other beside the trail,
// so at z14 some keep a ringed pin and the rest fall back to plain dots. That
// is the case this frame exists to show. That also
// keeps campsites out of the frame altogether, which is one of the four things
// .claude/skills/pr-screenshot/SKILL.md says a shot must never show at a
// readable zoom. Nobody's report, nobody's fix.
//
// ROUND THE SLIM PIN SINCE #1682: the pin is drawn 26 px across inside its
// 38 px footprint and the ring sits 3 px outside the DRAWN pin, at 16 px. The
// springs by Blackrock are all `confidence: high` in the pinned release, so
// they are filled and keep the invite; an unverified spring is hollow and
// wears none (lib/stalenessDisplay.ts's pinConditionFor).
//
// WHEN IT SHOWS LESS. No ring on a pin that is drawn means the note roll-up
// says somebody confirmed it (no ring is the middle state, on purpose), or
// that the spring is unverified and hollow; no pins at all means the
// waypoints had not landed by the wait.
export const caption =
  'The staleness ring is part of its pin (#1676): water on the A.T. by Blackrock in Shenandoah at walking zoom, waypoints narrowed to water, each never-confirmed spring wearing its faint invite ring around the pin that stands on its point, and any spring that fell back to a dot wearing no ring at all'
export const alt =
  'The map screen over Shenandoah at walking zoom by Blackrock: the Appalachian Trail as a red line, two blue water pins standing on their points, each inside a faint blue ring centred on the pin, and beside one of them a few small blue dots with no ring, for the springs that lost their pin to a neighbour'

/** Vector tiles plus the waypoint source landing take longer than chrome.
 *
 * 22000, as the Hudson Highlands desktop recipes wait, since #1676's first
 * preview (built from 698274a7): at the old wait all three waypoint recipes
 * photographed the map mid-load - the carry frame with its dots drawn but no
 * pin and no trail line, the Brooklyn and Shenandoah frames with neither. The trail
 * line is not something #1676 touches, so the frame was early rather than
 * wrong. Measured in the agent sandbox the same day, through
 * scripts/data-proxy.mjs: at 6 s `main` and #1676's branch were both still
 * blank at the carry camera, and at 15-20 s both had drawn everything. */
export const wait = 22000

export default async function drive(page) {
  // The stored preference the legend's Showing picker writes (#530), merged
  // over the defaults by lib/preferences.ts, so this one field is enough.
  await page.evaluate(
    () =>
      new Promise((done, fail) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const store = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
          const read = store.get('ourhike:preferences')
          read.onsuccess = () => {
            const write = store.put(
              { ...(read.result ?? {}), waypoint_types_shown: ['water'] },
              'ourhike:preferences',
            )
            write.onsuccess = () => done()
            write.onerror = () => fail(write.error)
          }
          read.onerror = () => fail(read.error)
        }
      }),
  )
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-78.437, 38.532], zoom: 14 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
}
