// The other organizations' trails BELOW the pin seam and above the archive's
// cut - the band #1775 moved from the sketch file onto the network tiles.
//
// WHY THE STANDING SHOTS AND network-above-the-seam.mjs ALL MISS IT. The
// trail screen photographs the opening camera, which is z2.2 on a phone and
// z4.39 on the laptop this runs at (App.tsx's UNITED_STATES_BOUNDS) - below
// NETWORK_SKETCH_MAX_ZOOM, so it draws the sketch file and shows nothing
// about this change. network-above-the-seam.mjs sits at z12, above
// CORRIDOR_MAX_ZOOM, where the full network's own layers have always drawn.
// Between them is a band nothing photographed, and it is exactly the band
// this pull request re-sources: z5 to z9 now draws the sketch's paint over
// `nearby_trails.pmtiles` instead of over `network_overview.geojson`.
//
// WHAT WOULD BE WRONG IN THIS FRAME. The change is meant to be invisible -
// same expressions, same widths, same ghosting, one source swapped - so the
// frame's job is to catch the ways that fails rather than to show something
// new:
//
//   - An EMPTY map above the A.T.'s own line means the tiled twins are not
//     reaching the archive at all (a missing `source-layer`, a filter that
//     does not match, an id left out of a list).
//   - The other trails drawn at FULL side-trail weight, each in a dark
//     casing, means the wrong layers are covering this band - the tiled
//     nearby-trail layers rather than the sketch's paint. That is the
//     "cloud of coloured dots" texture the width taper exists to keep off
//     this view (map/style.ts, and features/NEARBY_TRAILS.md §8).
//   - The Long Path drawn as a bare thread with no dark edge means the
//     tiled casing is missing, which is #1586's frame undone at z5.
//
// z6 rather than z7 or z8: it is the first whole zoom inside the band, so a
// seam error at the cut shows here and nowhere else in the set. The A.T.'s
// own line is drawn from trails.geojson at every zoom and is NOT evidence
// about this change - it is the landmark that says the map came up at all.
//
// The Hudson Highlands and the Catskills in one frame: OPRHP's park trails,
// NYS DEC's Catskill network, the Long Path running north from Harriman, and
// the A.T.'s New York miles crossing all of it. Public ground at a zoom where
// one pixel is about 937 m - no campsite, no report, no fix and no readable
// feature of anybody's (the four things .claude/skills/pr-screenshot/SKILL.md
// says must never appear), because at this scale nothing that small is drawn.
//
// The camera is seeded through lib/cameraMemory.ts's session-storage key, as
// network-above-the-seam.mjs does and for its reasons.
//
// WHEN THIS FRAME SHOWS NOTHING, and it is the honest answer rather than a
// failure: the tiles come from the bucket this preview reads, and the z5-z8
// tiles only exist in releases cut since #1615. Against an older release
// map/networkTiles.ts finds no archive named in latest.json and draws
// nothing in this band - which is the same "an artifact no publish has
// carried yet" wall trail-screen.mjs's own header describes.
//
// The pipeline half of #1775 - the sketch cut from 12,238,110 bytes to
// 1,811,212 - is NOT visible here and cannot be. It changes z0-z5, which
// this camera is above, and it only reaches the bucket after the publish
// this pull request's `## Data pipelines` section asks for.

export const caption =
  'The Hudson Highlands and the Catskills at zoom 6 — inside the band #1775 re-sources. Every other organization’s trails should look exactly as they did: thin ghosted threads in their own blaze hues tapering with the camera, the Long Path among them carrying its own dark casing, the A.T.’s white line through them. What is different is where the geometry came from — the network tiles rather than the corridor sketch — so a frame that looks unchanged is the frame that passes. Empty ground, or trails drawn at full weight in dark casings, is the failure this shot exists to catch.'
export const alt =
  'The map screen over the Hudson Valley and Catskills at zoom 6: the Appalachian Trail as a thin white line running across the lower part of the frame, with many fainter coloured threads around and north of it for the other organizations’ trails, one of them — the Long Path — drawn slightly heavier with a dark edge along it.'

/** Vector tiles from the bucket at a coarse zoom cover a lot of ground, so
 *  the archive reads several leaf directories before the first tile draws. */
export const wait = 6000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read back
  // with every field validated, and null on anything that does not convince.
  // Centred between Harriman and the Catskills so both are inside one z6
  // frame with the A.T.'s New York miles along the bottom.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.2, 41.7], zoom: 6 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the CONTEXT (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
}
