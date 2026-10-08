// The drive every map-region recipe shares (preview-shots/map-region-*.mjs):
// open the map screen at one remembered camera, and do nothing else.
//
// DECISION 31's MAP SHOT PER REGION (pipeline/ELT.md, "The go/no-go gate"):
// the new-data review report counts what the marts carry, and these recipes
// are its picture, one per part of the ground the marts' region boxes cover
// (pipeline/dbt/macros/lands_outside_its_region.sql's region_boxes()). Each
// recipe holds its own camera, so touching a recipe re-photographs the frame
// it names; this file holds only how a camera is reached.
//
// THE CAMERA IS SEEDED, NOT FLOWN TO. lib/cameraMemory.ts keeps the view in
// sessionStorage under CAMERA_MEMORY_KEY, and App.tsx reads it once as the
// app starts, so after the reload the map is BUILT at this camera rather than
// moved there - colorado-network.mjs and network-at-the-corridor-camera.mjs
// do the same, for the same reason. First run stays skipped across the
// reload: the runner installs that through an init script on the browser
// CONTEXT (scripts/screenshot.mjs's skipFirstRun), which runs on every page.
//
// NOTHING ELSE IS TOUCHED, which is most of why a region shot is safe to take
// again on every pull request that changes it: no sign-in, no search, no
// report, no locate button. src/test/regionMapShots.test.ts runs each recipe
// against a stand-in page that refuses any other call, and checks that what
// the drive stores is a camera readCamera() accepts.

/** lib/cameraMemory.ts's key, spelled here because a recipe cannot import the
 *  app's TypeScript; regionMapShots.test.ts reads it back through
 *  readCamera(), which uses the app's own constant, so the two cannot drift. */
export const CAMERA_MEMORY_KEY = 'ourhike:camera'

/** Seed `camera` ({ center: [lon, lat], zoom }), reload, and open the Map tab. */
export async function openMapAt(page, camera) {
  await page.evaluate(
    ([key, seeded]) => sessionStorage.setItem(key, JSON.stringify(seeded)),
    [CAMERA_MEMORY_KEY, camera],
  )
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
  // The map's own landmark, so a build whose map never mounts is "the
  // camera could not take" in the comment rather than a blank frame.
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
