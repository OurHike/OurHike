// The sign-in ask on a laptop (#1596): one door, in the sidebar's top-left
// corner, and the window it opens as a centred box.
//
// WHAT THIS SHOT IS EVIDENCE FOR, and it is the half of #1596 that only the
// wide layout can show. On a phone the account button lives on the map
// header and on Today's own chrome, one screen at a time, so one button is
// on the page. Above desktop.css's 900px breakpoint those two screens are
// drawn SIDE BY SIDE and both of those buttons were on the page together -
// the maintainer's report, 2026-09-20, looking at exactly this frame. The
// button moved to the sidebar, which is the one piece of chrome both screens
// share, and desktop.css hides the other two.
//
// So the thing to look for is a negative as much as a positive: the person
// glyph at the top-left of the pine column, above Today - and no second one
// in the journal's header or in the map's action cluster beside Search.
//
// The window is the second half. signInWindow.css centres it as a box past
// 900px rather than docking it to the foot as it does on a phone, and the
// map and the sidebar are both still there behind it, which is what makes it
// a window rather than a screen.
//
// Nobody's data: the preview's browser has never signed in, so the button is
// the hollow glyph and the ask promises nothing about a saved report.

export const caption =
  'Sign in on a laptop — one account button, in the sidebar’s top-left corner, and the ask as a centred window over the map and the journal (#1596)'
export const alt =
  'A wide browser window with the OurHike pine sidebar down the left, a person glyph at its top-left corner above the Today tab, and a centred "Sign in" dialog over the journal column and the map: "Continue with GitHub" in black, "Continue with Google" in white, "Continue with email" in dark green carrying the OurHike app icon, a "Not now" button, and the note that reading the map never needs an account. No second account button in the journal header or beside the map’s search control.'

// The wide layout is the entire subject.
export const desktop = true

export default async function drive(page) {
  // The map first, so the window has the desktop layout behind it rather than
  // a Today that has not yet handed over to the map screen. The region is the
  // wait rather than a timeout, for the reason today-desktop.mjs gives: a CI
  // runner's software-rendered map build is not something a sleep can budget
  // for, and a waitFor can.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()

  // The sidebar's button, which on this layout is the only one drawn - so
  // this locator is unambiguous here in a way it is not on a phone, and
  // `.first()` is deliberately absent. If the two header copies ever come
  // back, this line goes red as a strict-mode violation rather than quietly
  // photographing whichever one came first in the DOM.
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('dialog', { name: 'Sign in' }).waitFor()
}
