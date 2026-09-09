// The Map tab, on a long hike (#1367).
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the map finally says which hike you
// are on, and offers the way to a different one. #1338 put that door on the
// sidebar, Today's header, the Plan band and a Settings row, and left this
// screen with nothing — the PR said so rather than papering over it.
//
// WHY IT TOOK A SECOND PASS: chrome/Header.tsx's plate is a read-only zone
// that "takes exactly one slot", citing WIREFRAMES.md §2's "Nothing else
// lives here". That rule is about the PLATE, and the map has a separate
// action zone beside it — so the eyebrow names the hike (still read-only,
// still identity, still one slot) and the switch sits in `.map-header__actions`
// with legend and search. No rule overturned.
//
// WHAT TO LOOK FOR: the plate's eyebrow reading the hike's name rather than
// "Appalachian Trail", the mile underneath it unchanged, and a third icon
// button top-right.
//
// WHAT THIS SHOT CANNOT SETTLE, and the reason the glyph is @unvalidated in
// Header.tsx: whether a hiker reads two arrows turning back on each other as
// "change which hike I'm on". A picture proves the control is there, not
// that anybody finds it. Watching somebody look would settle it; nobody has.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'The Map tab, naming the hike it is showing (#1367)'
export const alt =
  'The trail map with its floating plate top-left reading "SPRINGER → KATAHDIN" over the mile readout, and three icon buttons top-right — a two-way arrow, a legend and a search'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: /Change which hike/ }).waitFor()
}
