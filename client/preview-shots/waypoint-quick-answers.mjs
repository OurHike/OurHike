// A shelter's peek, and the two answers it now asks for (#1122).
//
// THE SCREEN THIS CHANGE IS ABOUT. The peek is what a hiker sees while still
// holding the phone at arm's length in front of the thing it describes, and it
// is where #1122 lands hardest: a shelter used to be asked "Fine or Full?" and
// is now asked "All good, or Damaged?", with the two ends tinted so which is
// which reads before the words do. Nothing photographed the peek's answer row
// before this recipe existed.
//
// SEARCH RATHER THAN A TAP ON THE MAP, because a drive cannot aim a canvas
// click at a pin - the lon/lat under a fixed pixel depends on where the camera
// happens to be, and where the camera happens to be is App.tsx's opening view
// of the whole corridor. Selecting a search result opens that waypoint's card
// (#527 §3), which is a stable door to the same screen.
//
// AND A SEARCH FOR THE CATEGORY, NOT FOR A NAMED SHELTER. Naming one would
// make this recipe an assertion about which rows ATC currently publishes -
// a shelter renamed or retired upstream would break the camera and say
// nothing about this change. "Shelter" matches whatever the build actually
// holds, and the first result is as good as any: this shot is about the row
// of buttons, not about which shelter is above it.
//
// TWO HONEST FRAMES, ONE RECIPE - the shape day-hike-builder.mjs and
// day-hike-card.mjs already ship, and the caption has to name both because
// photograph-preview.mjs reads `caption` off the module before the drive runs
// (#1058). Where the POI artifacts arrive, the picture is the card. Where they
// do not - a fork's pull request gets no secrets, and an agent sandbox's
// browser cannot reach the bucket at all - Search says "Nothing here by that
// name" and the picture is that, which is a true screen rather than a broken
// one.
//
// Nobody's data is in the frame by construction: no account, no notes seeded,
// no location fix, and no campsite - a shelter is a structure ATC publishes
// the location of, not one of the dispersed sites SOURCE_SURVEY.md §3b is
// about.

export const caption =
  'A shelter’s peek — Damaged where Full used to be, and the two ends tinted (#1122)'
export const alt =
  'Either a waypoint card peeking over the map for a shelter, showing a condition line and two answer buttons — a green one carrying one of the rotating good words and an orange “Damaged” — above a “Notes & details” expander; or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

// The POI artifacts are several megabytes and are hashed before they are
// trusted, so results can take a moment on a cold preview. The drive waits on
// the results themselves; this is the settle after the card opens.
export const wait = 5000

export default async function drive(page) {
  // The app opens on Today since #1054, and search lives in the map header.
  await page.getByRole('tab', { name: 'Map' }).click()

  // The header's icon button, by the visually-hidden span inside it - what a
  // screen reader, and therefore this locator, sees (chrome/Header.tsx).
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByRole('searchbox', { name: 'Search the downloaded map' }).fill('Shelter')

  // Whether any result arrives is the test for which of the two frames this
  // build can reach. Waited on rather than counted immediately: the artifacts
  // may still be landing when the panel opens.
  const first = page
    .getByRole('button')
    .filter({ hasText: /Shelter/ })
    .first()
  await first.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await first.count()) === 0) return

  await first.click()

  // The peek, by the test id the section carries. Waited on rather than
  // assumed: selecting a result also flies the camera, and the card mounts
  // when the shell's selection lands rather than when the tap does.
  //
  // Deliberately NOT opened. "Notes & details" is one pull away and
  // waypoint-conditions.mjs is the recipe that pulls it; this shot is the
  // peek, which is the surface the change was made for.
  await page
    .getByTestId('poi-card-peek-conditions')
    .waitFor({ timeout: 15000 })
    .catch(() => {})
}
