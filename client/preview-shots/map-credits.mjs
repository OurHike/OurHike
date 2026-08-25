// The map corner's credits, opened (#1019).
//
// The strip collapses to OpenStreetMap plus "N more" (chrome/MapAttribution.tsx
// is a native <details>), so the stewards whose trails are drawn are readable
// only with the disclosure open — and the steward #1019 adds, NYS DEC, is in
// that hidden list.
//
// WHAT THIS SHOT CAN AND CANNOT SHOW, measured on #1021's own preview rather
// than assumed. **The preview build has no data source.**
// `VITE_DATA_BASE_URL` is empty in the deployed bundle — read out of
// pr-1021.ourhike-preview.pages.dev's `assets/main-*.js` on 2026-08-25, where
// lib/config.ts's `RAW_BASE.replace(...)` has an empty literal in front of it —
// so nothing fetches an artifact, `hasNearbyTrails` is false, and the opened
// list is the background credits alone: OpenStreetMap, OpenFreeMap, the
// elevation line. The trail-screen standing shot says the same in its header
// ("No trail line"), and that shot is byte-identical on another open pull
// request's preview (sha256 db7bf8c4… on both #1021 and #1022), so this is how
// every preview here is built and not something one change did.
//
// So this shot is evidence that the disclosure opens and what it lists — not
// that DEC is in it. `src/map/credits.test.ts` is what pins the DEC line. The
// day the preview gets a data source, the camera is already pointed at the
// right element and the name appears here without anybody re-aiming it.
export const caption =
  'The map corner, credits open — no steward listed, because the preview build has no data'
export const alt =
  'The map attribution strip expanded over the trail screen, listing the background credits only: OpenStreetMap, OpenFreeMap and the elevation source'

export default async function drive(page) {
  // The <summary> of chrome/MapAttribution.tsx's <details>. Clicked by class
  // rather than by role: a summary's implicit role is not stable across
  // engines, and its accessible name is the first credit plus a count, which
  // is exactly the string #1019 changed.
  await page.locator('.map-attribution__summary').click()
}
