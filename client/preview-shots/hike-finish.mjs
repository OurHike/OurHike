// The finish (#1317) - the one celebratory screen in the app.
//
// WHAT THIS SHOT IS EVIDENCE FOR, and it is the reason this recipe exists at
// all: that the screen most likely to grow a percentage, a rank or a streak
// has none. Four figures, every one a record of what happened rather than a
// comparison, and a closing line saying so out loud - "No badge, no rank,
// nobody to compare with." A reviewer can read the whole frame and check it.
//
// THE DRIVE IS THE REAL ONE. The screen is OFFERED, never declared, so the
// only way to it is a hiker saying they finished - through More, the hike's
// row, and "I finished it". A recipe that reached it any other way would be
// photographing a state the app cannot actually enter.
//
// WHAT IT IS NOT EVIDENCE FOR. The hero photo and the places grid, which
// need photos with their own attribution paths (features/POI_PHOTOS.md) and
// are absent on a phone with none - so the shot shows the pine ground the
// hero sits on. The crews card is absent for the same honest reason: this
// phone cannot say how many clubs maintain the trail, and a number would be
// invented.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'The finish — no badge, no rank, nobody to compare with (#1317)'
export const alt =
  'A pine full-screen showing FINISHED and a date, the hike name in large display type, a sentence naming what was walked and between which dates, figures for miles walked, days walking and sections, two buttons to share or keep the record, and a closing line reading "No badge, no rank, nobody to compare with"'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /^You/ }).click()
  await page.getByRole('button', { name: 'Springer → Katahdin' }).click()
  await page.getByRole('button', { name: /I finished it/ }).click()
  await page.getByText(/No badge, no rank/).waitFor()
}
