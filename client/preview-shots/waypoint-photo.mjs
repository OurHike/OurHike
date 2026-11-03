// The opened card's photograph, and the frame it is drawn in (#1495).
//
// NO EXISTING RECIPE REACHES THIS BOX, which is why this is a new file rather
// than a touch of an old one. waypoint-quick-answers.mjs photographs the peek,
// and the peek carries the category's silhouette and never a photograph (#941
// moved the picture into the opened card). waypoint-conditions.mjs does open
// the card - and then scrolls straight past the media box to the "Say
// something back" band, so the photograph is never in its frame. The drive
// below is that recipe's, stopped one step earlier.
//
// WHAT THIS SHOT CAN PROVE, AND WHAT IT CANNOT. #1495 gives the card two
// frames: `hero`, which fills the 16:10 box as it always has, and `inset`,
// which draws a photograph smaller than 480px at its own size, centred, rather
// than upscaling and cropping it.
//
// This frame shows HERO, and that is the whole of what it can show today.
// Every photograph the app currently ships is 640px - the hiker's own are
// re-encoded to CARD_PHOTO_EDGE on the device, and the Commons and ATC fetches
// ask for the same edge - so nothing reachable from a preview build is under
// the line. The NYNJTC archive corpus that inset exists for (396 of 403 images
// between 150 and 300px, #1450) is recovered but unshipped: it stops at a
// review sheet, and no confirmed row has been written into
// pipeline/reference/ yet.
//
// So this shot is a REGRESSION CHECK rather than a demonstration. #1495 edits
// the rules that draw every photograph on this card, and the question a
// reviewer needs answered is whether the photographs that ship today still
// fill their box exactly as before. That is a question a picture answers and a
// sentence does not. The inset path's evidence is the test run in the pull
// request body, and the body says so rather than letting this frame imply
// more than it holds.
//
// The day an archive photograph does ship, this recipe is already pointed at
// the box it will appear in - touch it and it re-photographs.
//
// THREE HONEST FRAMES, and the caption names all three because
// photograph-preview.mjs reads `caption` before the drive runs (#1058):
// the opened card with a photograph; the opened card with the category glyph,
// where that waypoint has none; and the search panel saying nothing is here,
// where the build has no POI artifacts at all - a fork's pull request gets no
// secrets, and an agent sandbox's browser cannot reach the bucket.
//
// Nobody's data is in the frame by construction: no account, no notes seeded,
// no location fix, and a shelter rather than a campsite - a structure ATC
// publishes the location of, not one of the dispersed sites SOURCE_SURVEY.md
// §3b is about. The credit line under the photograph is the pipeline's own
// attribution, which is the licence's price for showing the picture at all.

export const caption =
  'The opened card’s photograph — every shipped photo is 640px and still fills its box, the frame #1495 leaves untouched'
export const alt =
  'Either a waypoint card pulled open for a shelter, showing the photograph filling a 16:10 box under the heading with its credit line across the bottom edge; or the same card with the category’s silhouette where that shelter has no photograph; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

// The POI artifacts are several megabytes and are hashed before they are
// trusted, and the photograph itself is a second fetch after the card mounts.
// This is the settle after both.
export const wait = 5000

export default async function drive(page) {
  // Reached exactly as waypoint-conditions.mjs reaches it - see that recipe
  // for why this searches a category rather than naming a shelter (a rename
  // upstream would break the camera and say nothing about this change), and
  // why a canvas tap is not an option (a drive cannot aim a click at a pin).
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByRole('searchbox', { name: 'Search the downloaded map' }).fill('Shelter')

  const first = page
    .getByRole('button')
    .filter({ hasText: /Shelter/ })
    .first()
  await first.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await first.count()) === 0) return

  await first.click()

  const expand = page.getByTestId('poi-card-expand')
  await expand.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await expand.count()) === 0) return
  await expand.click()

  // Wait on the media box and DO NOT scroll. The opened card leads with its
  // heading and then the photograph, so at 390x844 the box is already in
  // frame - it is the answers and the report plates below it that are under
  // the fold, which is what waypoint-conditions.mjs scrolls for.
  //
  // The box rather than the photograph: `poi-card-photo` exists only where
  // that waypoint has one, so waiting on it would turn the second honest
  // frame - the category glyph - into a timeout. The media box is there
  // either way.
  await page
    .getByTestId('poi-card-media')
    .waitFor({ timeout: 15000 })
    .catch(() => {})
}
