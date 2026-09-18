// The same Bear Mountain frame as long-term-closures.mjs, under the dark
// colour scheme: the barrier tape on a dark sheet (#1575, and the
// maintainer's reading of 2026-09-18).
//
// WHY A SECOND FRAME. Option E - red stripes on an opaque band of the
// sheet's paper - was chosen from five treatments rendered on the day
// sheet, and built as "the sheet's paper" it put red stripes on night_hike's
// near-black ink over a near-black map. The maintainer, in dark mode:
// "it's really hard to tell it's a closure when the background is black,
// with black & red alternating for the closure. Maybe that should be red &
// white just for dark mode." So on every dark sheet but red light's the
// band is now the field day sheet's white (map/style.ts's closureTapeGround),
// and this frame is the evidence: the same seven closed runs as the day
// frame, each a white band of red diagonals over the sheet's ink, where the
// day frame's band is white over white paper and the previous build's night
// band was ink over ink.
//
// THE DARK SCHEME, NOT A PREFERENCE WRITE. The theme preference ships as
// `auto` (lib/userPreferences.ts), which follows the OS through
// `prefers-color-scheme` (lib/theme.ts), so the drive asks the browser for
// the dark scheme before the reload and the field sheet's auto-dark - which
// is night_hike - is what draws. Nothing is written to anybody's store, and
// the day frame's rule stands: no location fix, no account, nobody's reports.
export const caption =
  'The Bear Mountain frame of long-term-closures.mjs on the dark sheet: OPRHP’s long-term closed trails as barrier tape on a band of the DAY sheet’s white paper over night_hike’s ink (closureTapeGround, 2026-09-18) - red and white, where the previous build laid red stripes on the sheet’s own ink and the maintainer could not tell a closure from the ground. Red light is not this frame: it keeps its ink, and the change’s docstring says why that question is left open'
export const alt =
  'The map screen over Bear Mountain State Park at zoom 13 on a dark sheet: contour lines and trails in red over near-black ground, and along several trails a wide white band of red diagonal stripes laid over the line, the barrier tape marking a closed trail, plainly lighter than everything around it'

/** Vector tiles from the bucket plus generated contours over a park at z13,
 *  the same allowance long-term-closures.mjs makes. */
export const wait = 22000

export default async function drive(page) {
  // The OS's answer to prefers-color-scheme, which the `auto` theme reads.
  await page.emulateMedia({ colorScheme: 'dark' })

  // lib/cameraMemory.ts's contract, as long-term-closures.mjs seeds it: the
  // centre of the densest cell of closed lines the release carries.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.005, 41.308], zoom: 13 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the context (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
