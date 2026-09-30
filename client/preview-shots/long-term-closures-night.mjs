// CROSSED OUT SINCE 2026-09-26 (#1677). The notes below describe the red
// band this frame used to show. The white paper survives - it is still
// closureTapeGround's day white on a dark sheet - and what sits on it now
// is a dotted dark trace with a chain of dark x marks, the same mark as the
// day frame. Red light is no longer an open question: it draws the mark in
// its one hue on the sheet's own ink (map/style.ts's closureInk).
//
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
// AMENDED 2026-09-20 (#1598): the band in this frame carries 41% of its
// length in red rather than 28%, inside a hard dark outline - and on a dark
// sheet the outline is the one part of it that does nothing,
// since a near-black edge against near-black ground has nothing to separate.
// That is the honest reading of this frame: the outline is for the day
// sheets and for the overview camera, and the white paper is still what
// makes a closure findable here.
//
// THE DARK SCHEME, NOT A PREFERENCE WRITE. The theme preference ships as
// `auto` (lib/userPreferences.ts), which follows the OS through
// `prefers-color-scheme` (lib/theme.ts), so the drive asks the browser for
// the dark scheme before the reload and the field sheet's auto-dark - which
// is night_hike - is what draws. Nothing is written to anybody's store, and
// the day frame's rule stands: no location fix, no account, nobody's reports.
export const caption =
  'The Bear Mountain frame of long-term-closures.mjs on the dark sheet, crossed out (#1677). Each closed trail is knocked out to a band of the day sheet’s white paper (closureTapeGround, 2026-09-18), with a dotted dark trace and a chain of dark x marks on it. On near-black ground it is the lightest thing in the frame. The open trails around it stay red: the A.T. solid, the park’s trails dashed. Red light is not this frame; it draws the same mark in its one hue on its own ink.'
export const alt =
  'The map screen over Bear Mountain State Park at zoom 13 on a dark sheet: red trail lines over near-black ground, with contour lines. Along several trails the line gives way to a white band carrying a dotted dark line and a row of small dark x marks, marking a closed trail, plainly lighter than everything around it.'

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
