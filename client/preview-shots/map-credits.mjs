// The map corner's credits, opened (#1019).
//
// The strip collapses to OpenStreetMap plus "N more" (chrome/MapAttribution.tsx
// is a native <details>), so the stewards whose trails are drawn are readable
// only with the disclosure open — and the steward #1019 adds, NYS DEC, is in
// that hidden list.
//
// WHAT THIS SHOT CAN SHOW, AND THE WRONG MEASUREMENT THAT USED TO SIT HERE.
// This recipe was written on 2026-08-25 saying the preview build has no data
// source - `VITE_DATA_BASE_URL` read as an empty literal out of #1021's
// bundle, every preview's trail-screen shot byte-identical - so the opened
// list was the background credits alone and the shot could not show the
// steward #1019 adds. The symptom was real and the cause was not (#1024):
// the camera's own origin failed the bucket's CORS allowlist, #1096 fixed
// the camera on 2026-08-27, and the release's artifacts arrive now. So this
// frame can carry the stewards whose trails are drawn, DEC among them,
// and `src/map/credits.test.ts` still pins the DEC line where a shot cannot
// be trusted to.
//
// TWO HONEST FRAMES, as every recipe that depends on the release says: with
// the artifacts, the disclosure lists the background credits and the
// stewards; without them (a fork's pull request, a camera that missed the
// bucket), it lists the background credits alone.
export const caption =
  'The map corner, credits open — the stewards whose trails are drawn, or the background credits alone (#1019)'
export const alt =
  'The map attribution strip expanded over the trail screen, listing OpenStreetMap, OpenFreeMap and the elevation source, and - where the release arrived - the data stewards beneath them'

export default async function drive(page) {
  // The map first: the app opens on Today since #1054, and the credits
  // live on the map screen's corner.
  await page.getByRole('tab', { name: 'Map' }).click()

  // The <summary> of chrome/MapAttribution.tsx's <details>. Clicked by class
  // rather than by role: a summary's implicit role is not stable across
  // engines, and its accessible name is the first credit plus a count, which
  // is exactly the string #1019 changed.
  await page.locator('.map-attribution__summary').click()
}
