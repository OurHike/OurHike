// The Ice Age Trail wearing its badge, on a phone at z6 over north-central
// Wisconsin.
//
// WHAT CHANGED. pipeline/reference/trail_name_aliases.json gained the Forest
// Service's `ICE AGE NST-A/B/C` spellings on 2026-09-30, and
// map/longTrailNames.ts with them. Before that, those lines drew as anonymous
// threads. mountains-to-sea-badge.mjs has the reasoning for z6: the badge
// layer draws below POI_PIN_MIN_ZOOM (7), and from z5 the lines come from
// vector tiles that carry their names.
//
// WHERE THE CAMERA POINTS, MEASURED against UA release 2026-09-30: the three
// spellings span lon -90.95..-90.28 and lat 45.03..45.33, in the
// Chequamegon-Nicolet National Forest. The centre is that extent's midpoint.
// These 67 miles are the only stretch of the trail that any layer in UA's
// release names, so the rest of it is not on this map under that name.
//
// WHAT THE BADGE SHOULD LOOK LIKE: the plate, the Ice Age Trail Alliance's
// marker and the name "Ice Age Trail". `iat` ships a marker (sources.json
// `org_marks.trail_marks.iat`, unclaimed, not withdrawn). The North Country
// Trail runs through the same forest further north and may wear its own badge
// in the frame.
//
// Nothing here reaches an account, anybody's reports or photos, a dispersed
// campsite at a readable zoom, or a real location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear in a shot.
export const caption =
  'The Ice Age Trail on a phone at z6 over north-central Wisconsin, wearing a badge with the Ice Age Trail Alliance’s marker and the name "Ice Age Trail". The Forest Service publishes this 67-mile stretch as "ICE AGE NST-A", "-B" and "-C". Before this change they had no badge.'
export const alt =
  'The map screen over north-central Wisconsin at zoom 6: trail lines in the Chequamegon-Nicolet National Forest, one carrying a small paper badge with the Ice Age Trail Alliance’s marker and the name "Ice Age Trail".'

export const wait = 8000

export default async function drive(page) {
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-90.62, 45.18], zoom: 6 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
