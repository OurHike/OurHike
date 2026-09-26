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
// A.T. through Shenandoah near Big Meadows (z14, centred on the springs
// by Tanners Ridge, which a z13.5 first cut left under the top chrome), public land, with the legend's
// Showing picker narrowed to water through the stored preference. That also
// keeps campsites out of the frame altogether, which is one of the four things
// .claude/skills/pr-screenshot/SKILL.md says a shot must never show at a
// readable zoom. Nobody's report, nobody's fix.
//
// WHEN IT SHOWS LESS. No ring on a pin that is drawn means the note roll-up
// says somebody confirmed it (no ring is the middle state, on purpose); no
// pins at all means the waypoints had not landed by the wait.
export const caption =
  'The staleness ring is part of its pin (#1676): water on the A.T. near Big Meadows at walking zoom, waypoints narrowed to water, each never-confirmed spring wearing its faint invite ring around the pin that stands on its point, and any spring that fell back to a dot wearing no ring at all'
export const alt =
  'The map screen over Shenandoah at walking zoom: the Appalachian Trail as a red line, with a few purple water pins standing on their points, each inside a faint blue ring centred on the pin'

/** Vector tiles plus the waypoint source landing take longer than chrome. */
export const wait = 7000

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
      JSON.stringify({ center: [-78.439, 38.546], zoom: 14 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
}
