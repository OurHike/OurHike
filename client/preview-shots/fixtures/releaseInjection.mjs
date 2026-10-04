// One invented record added to a file of the release this build pins, for a
// recipe whose screen no published release reaches yet (decisions 64 and 65:
// a club line in the sketch, a seasonal tap's card).
//
// WHY A RECIPE HAS TO DO THIS. The pipeline writes `line_kind` and
// `water_caution` from the dbt path, and the release a build pins was
// published before either existed, so the camera finds neither in the
// bucket (UA's 2026-10-03-2, read 2026-10-04: no feature carries either).
// Both files are verified against the release's manifest before anything
// draws or stores them (lib/trailData.ts's readChecked, and
// lib/nearbyTrailData.ts's own sha256Of check), so the edit is made
// on the way in and the manifest's hash and sizes are rewritten to the
// edited bytes: an edit the manifest did not vouch for would fail that check,
// and the frame would be a download error instead of the screen.
//
// NOBODY'S DATA. The record a recipe adds is invented, named as a fixture
// where the file carries a name ("Example ... (preview fixture)"), and
// carries the source key `preview_fixture`, which no organization holds, so
// no line on screen can credit an invented record to a real steward.
// Everything else on the screen is the pinned release as it stands.
//
// Not a recipe: shared fixtures live one directory down, where the runner's
// recipe glob does not reach (fixtures/suggestedHikes.mjs explains).
import { createHash } from 'node:crypto'

function escaped(key) {
  return key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Routes the pinned release's manifest and each file in `edits` so the file
 * arrives edited and the manifest vouches for the edit.
 *
 * `edits` maps a release key (`nearby_poi.geojson`) to a function from the
 * published document to the one to serve. A file the release does not have,
 * or a manifest that does not list it, is left alone: the recipe's frame is
 * then the release as it stands, which its caption names.
 *
 * Each file is fetched and edited ONCE per page, however many times the app
 * asks for the manifest: network_overview.geojson is 41,216,145 bytes raw in
 * UA's 2026-10-03-2 manifest, and fetching it again on every manifest read is
 * a second wait for nothing. A request the page drops while one is in flight
 * is let go rather than thrown, because a throw inside a route handler ends
 * the whole capture rather than the one request.
 */
export async function injectIntoRelease(page, edits) {
  const edited = {}
  const editOnce = (base, key) => {
    // page.request rather than route.fetch: it is not tied to the request
    // being answered, so it survives that request being dropped, and it
    // does not pass back through these routes.
    edited[key] ??= (async () => {
      const published = await page.request.get(base + key, { timeout: 120000 })
      if (!published.ok()) return null
      return JSON.stringify(edits[key](await published.json()))
    })().catch(() => null)
    return edited[key]
  }

  await page.route(/\/releases\/[^/]+\/manifest\.json(\?|$)/, async (route) => {
    try {
      const response = await route.fetch()
      if (!response.ok()) return await route.fulfill({ response })
      const manifest = await response.json()
      const base = route
        .request()
        .url()
        .replace(/manifest\.json(\?.*)?$/, '')
      for (const key of Object.keys(edits)) {
        const entry = manifest.artifacts?.[key]
        if (entry === undefined) continue
        const body = await editOnce(base, key)
        if (body === null) continue
        entry.sha256 = createHash('sha256').update(body).digest('hex')
        entry.size_bytes = Buffer.byteLength(body)
        entry.transfer_bytes = Buffer.byteLength(body)
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(manifest),
      })
    } catch {
      await route.abort().catch(() => {})
    }
  })

  for (const key of Object.keys(edits)) {
    await page.route(
      new RegExp(`/releases/[^/]+/${escaped(key)}(\\?|$)`),
      async (route) => {
        try {
          // Only once a manifest has vouched for the edit: before that, the
          // published bytes are the ones its hash describes.
          const body = edited[key] === undefined ? null : await edited[key]
          if (body === null) return await route.continue()
          await route.fulfill({ status: 200, contentType: 'application/json', body })
        } catch {
          await route.abort().catch(() => {})
        }
      },
    )
  }
}
