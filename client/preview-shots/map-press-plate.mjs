// Press and hold a spot on the map (#1137).
//
// THE THIRD DOOR, and the only one that can name a place the app has no name
// for. Today's foot anchors on the hiker's own fix; a place's card anchors on
// that place. Neither reaches the blow-down at a nameless bend, which is the
// case features/SAYING_THANKS.md opens with — "someone cleared forty blowdowns
// out of this mile and I have no idea who".
//
// WHAT TO LOOK AT is that the plate is SMALL and sits AT THE PRESS, with the
// map still there around it. That is the whole design argument and it is
// entirely visual: a hiker who pressed a spot is looking at that spot, so a
// sheet sliding up from the bottom would cover the thing they were pointing
// at. A picture settles whether this reads as "the map handed me something"
// or as "a screen appeared", and prose cannot.
//
// The two buttons are the same pair, in the same order and at the same weight,
// as Today's foot (`today-crew-row.mjs`) and the opened card
// (`waypoint-conditions.mjs`). Three surfaces, one relationship — worth
// checking across those three frames rather than in this one alone.
//
// THE LINE ABOVE THE BUTTONS IS THE LOAD-BEARING PART. It names where the
// press landed, and it is all that stands between a hiker and a report filed
// somewhere they did not mean. In this build it will read "This spot": the
// preview downloads no corridor archive, so there is no trail index to ask,
// and #249's rule is that "we could not check" and "you are three miles into
// the woods" are opposite things to say. On a phone with the trail on it the
// same line reads "mi 628.4".
//
// SO THIS FRAME SHOWS THE HONEST-UNKNOWN BRANCH, deliberately and not as a
// shortfall. It is the one a reviewer should most want to see: a plate that
// invented a mile here would be the failure the line exists to prevent.
//
// Nobody's data is in it. No account, no location fix, nothing filed — a press
// on bare map is a gesture, not a record, and the plate files nothing on its
// own.

export const caption =
  'Press and hold — a report anchored to a spot with no waypoint on it (#1137)'
export const alt =
  'A small plate over the map at the point that was pressed: a line reading “This spot”, a solid blaze-orange “Report a problem” above a solid forest-green “Say thanks”, and a quiet “Not here” beneath them. The map is still visible around it.'

export default async function drive(page) {
  // The app opens on Today (#1054); the map is a tab away.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()

  // Press and hold, in the mouse's own terms. The gesture module takes
  // `mousedown` as well as `touchstart` precisely so it is reachable on a
  // laptop - and so a camera without a touchscreen can photograph it.
  //
  // Aimed at the middle of the canvas rather than at any feature: the point of
  // this gesture is that there is nothing to aim at.
  const canvas = page.getByRole('region', { name: /trail map/i })
  const box = await canvas.boundingBox()
  if (box === null) return

  const x = box.x + box.width / 2
  const y = box.y + box.height / 2
  await page.mouse.move(x, y)
  await page.mouse.down()
  // Longer than LONG_PRESS_MS, with room for a slow runner. Held rather than
  // released: the plate opens on the timer while the finger is still down, and
  // photographing it mid-press is what the screen actually looks like.
  await page.waitForTimeout(900)

  // Waited on rather than assumed - if the plate never opened, the shot should
  // fail as a missing recipe rather than quietly photograph a bare map.
  await page.getByTestId('press-plate').waitFor({ timeout: 5000 })
  await page.mouse.up()
}
