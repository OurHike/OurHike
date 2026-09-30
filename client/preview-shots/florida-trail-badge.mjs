// The Florida Trail wearing its badge, on a phone at z6 over north Florida.
//
// WHAT CHANGED. pipeline/reference/trail_name_aliases.json gained the Forest
// Service's five `FNST - … SECTION` spellings on 2026-09-30, and
// map/longTrailNames.ts with them. Before that, every one of those lines drew
// as an anonymous thread. mountains-to-sea-badge.mjs has the reasoning for z6:
// the badge layer draws below POI_PIN_MIN_ZOOM (7), and from z5 the lines come
// from vector tiles that carry their names.
//
// WHERE THE CAMERA POINTS, MEASURED against UA release 2026-09-30: the five
// spellings span lon -85.02..-81.53 and lat 28.97..30.35 - the Apalachicola,
// Osceola and Ocala national forests. The centre is that extent's midpoint.
// At z6 a 390 px phone spans 4.28 degrees of longitude, so all three forests
// are in frame; the badge sits on the longest visible piece, once, however
// many sections are on screen.
//
// WHAT THE BADGE SHOULD LOOK LIKE: the plate, the Florida Trail
// Association's marker and the name "Florida Trail". `fnst` ships a marker
// (sources.json `org_marks.trail_marks.fnst`, unclaimed, not withdrawn).
//
// Nothing here reaches an account, anybody's reports or photos, a dispersed
// campsite at a readable zoom, or a real location fix - the four things
// .claude/skills/pr-screenshot/SKILL.md says must never appear in a shot.
export const caption =
  'The Florida Trail on a phone at z6 over north Florida, wearing a badge with the Florida Trail Association’s marker and the name "Florida Trail". The Forest Service publishes this trail only as sections, such as "FNST - OSCEOLA SECTION". Before this change none of those lines had a badge.'
export const alt =
  'The map screen over north Florida at zoom 6: trail lines in the Apalachicola, Osceola and Ocala national forests, one carrying a small paper badge with the Florida Trail Association’s marker and the name "Florida Trail".'

export const wait = 8000

export default async function drive(page) {
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-83.28, 29.66], zoom: 6 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
