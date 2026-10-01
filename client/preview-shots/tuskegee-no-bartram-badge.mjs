// Tuskegee National Forest, Alabama, at z6 on a phone - where a badge used to
// name the wrong trail (#1781).
//
// WHAT CHANGED. The Forest Service publishes "BARTRAM" for the Georgia-North
// Carolina Bartram Trail and for Tuskegee National Forest's own Bartram trail.
// map/longTrailNames.ts matched on the name alone, so the Alabama lines wore
// the Bartram Trail's badge and the Bartram Trail Conference's marker. Each row
// of pipeline/reference/trail_name_aliases.json now carries the box a line
// must lie in, and the Bartram box stops at lon -83.94.
//
// WHERE THE CAMERA POINTS, MEASURED 2026-09-30: the two Alabama features,
// usfs_trails:8251537 and :8280457, lie at lon -85.65..-85.56, lat
// 32.45..32.48. The centre sits west of them, at lon -86.3, so that the
// Georgia Bartram (lon -83.37 and east) is off the frame: at z6 a 390 px phone
// spans 4.28 degrees of longitude, lon -88.4..-84.2 here. Any "Bartram Trail"
// badge in this frame is therefore the defect coming back.
//
// WHAT SHOULD BE THERE: no "Bartram Trail" badge. The Pinhoti Trail in the
// Talladega National Forest, to the north-east, is in frame and may wear its
// own badge; that one is correct. z6 for the reason mountains-to-sea-badge.mjs
// gives: the badge layer draws below POI_PIN_MIN_ZOOM (7), from vector tiles
// that carry names from z5.
//
// Nothing here reaches an account, anybody's reports or photos, a dispersed
// campsite at a readable zoom, or a real location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear in a shot.
export const caption =
  'Tuskegee National Forest, Alabama, on a phone at z6, with no "Bartram Trail" badge. The Forest Service calls a trail here "BARTRAM", and until this change it wore the badge of the Bartram Trail in Georgia and North Carolina, a different trail about 200 miles away. The Pinhoti Trail to the north-east may wear its own badge, which is correct.'
export const alt =
  'The map screen over east-central Alabama at zoom 6, showing trail lines around Tuskegee National Forest with no badge reading "Bartram Trail"; to the north-east, lines in the Talladega National Forest, possibly with a badge reading "Pinhoti Trail".'

export const wait = 8000

export default async function drive(page) {
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-86.3, 32.46], zoom: 6 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
