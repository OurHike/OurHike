// Keeping a spot marked on the map, as a window (#1563, the maintainer's
// steer of 2026-09-17: "the Keep this should be an emergent window").
//
// WHAT THE PICTURE IS FOR. The crosshair's bar used to carry Keep beside
// its answer, on a slim strip at the foot of the map; the tap opens a window
// now, with the answer the tap got said large and Keep under it. What to
// look at: the window centred over the map, "Keep this spot?" on its dark
// header with Cancel at the right; the answer - a mile in CI, where the
// trail index is on the phone, or "This spot" without one - and the line
// saying the spot was marked by hand; "Keep this spot" filled and "Tap
// again" outlined under it; the crosshair's bar still at the foot of the
// map behind the scrim, saying the same answer, with only Cancel on it.
//
// THE TAP IS ON THE CANVAS'S MIDDLE, in the mouse's own terms, the way
// map-press-plate.mjs presses: the point of this gesture is that nothing
// has to be aimed at. Driven from the report window's own refusal - no fix,
// so Blow down opens the location sheet, and its map row hands the hiker
// the map (the window stands aside behind it).
//
// Nobody's data is in it: no account, no fix, no report filed - the tap
// that would file is the Keep, and this photographs the moment before it.

export const caption =
  'Keeping a spot marked on the map is a window (#1563): the tap on the map opens it with the answer the tap got — a mile, “This spot”, or off the trail — and Keep under it, where the crosshair’s bar used to carry the button.'
export const alt =
  'A small dialog centred over the map, its dark header reading “Keep this spot?” with a “Cancel” button at the right. Inside, a large line with the answer the tap got — a trail mile, or “This spot” — over a quieter line reading “Marked by hand on the map. The report says so, and whoever reads it sees that beside the coordinates.”, then a filled “Keep this spot” button and an outlined “Tap again” button. Behind the scrim, the map with a slim bar at its foot repeating the answer, with a “Cancel” button and no Keep.'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByRole('button', { name: /^Report a problem/ }).click()
  await page.getByRole('dialog', { name: 'What did you find?' }).waitFor()

  // No fix, so the tap is refused and opens the sheet; its map row hands
  // over the map with the crosshair's bar at the foot.
  await page.getByTestId('report-tile-blowdown').click()
  await page.getByTestId('location-map').click()
  await page.getByRole('dialog', { name: 'Say where this was' }).waitFor()

  const canvas = page.getByRole('region', { name: /trail map/i })
  const box = await canvas.boundingBox()
  if (box === null) return

  // TAPPED UNTIL THE MAP ANSWERS. A tap is the engine's event, not the
  // page's: MapLibre fires `click` only once it is up, and the map tab was
  // switched to a moment ago, so the first tap can land on a canvas that is
  // still loading and go nowhere - which is exactly what the first run of
  // this recipe did in CI (one tap, then a 5 s wait that timed out).
  // map-press-plate.mjs needs none of this because a press is the page's
  // own gesture. So: tap, give the window a moment, tap again, for as long
  // as a slow runner could need.
  const keep = page.getByRole('dialog', { name: 'Keep this spot?' })
  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
    const opened = await keep.waitFor({ timeout: 1_500 }).then(
      () => true,
      () => false,
    )
    if (opened) return
  }
  // Failed as a missing recipe rather than quietly photographing the bar.
  throw new Error('the map never answered a tap with the keep window')
}
