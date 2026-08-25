// The map corner's credits, opened (#1019).
//
// The strip collapses to OpenStreetMap plus "N more" (chrome/MapAttribution.tsx
// is a native <details>), so the stewards whose trails are drawn are only
// readable with the disclosure open — and the steward this pull request adds,
// NYS DEC, is in that hidden list. A shot of the trail screen would show the
// count going up by one and nothing else.
//
// In CI the map data is real, so the nearby-trail artifact loads and the list
// is the four stewards the corner should name. In a sandbox it will be short:
// nothing downloads the network there, so `hasNearbyTrails` is false and only
// the background credits appear. That is the sandbox, not the change.
export const caption = 'The map corner, credits open — look for NYS DEC in the list'
export const alt =
  'The map attribution strip expanded over the trail screen, listing every steward whose trails are drawn, including the New York State Department of Environmental Conservation'

export default async function drive(page) {
  // The <summary> of chrome/MapAttribution.tsx's <details>. Clicked by class
  // rather than by role: a summary's implicit role is not stable across
  // engines, and its accessible name is the first credit plus a count, which
  // is exactly the string this pull request changes.
  await page.locator('.map-attribution__summary').click()
}
