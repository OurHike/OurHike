// The legend sheet again, for #1670 - --fg-3 text is under WCAG AA contrast
// on every light surface, and the app uses it 229 times.
//
// WHY A SECOND RECIPE FOR THE SAME SCREEN. legend.mjs's caption is about its
// rows; this change is about the colour of the small grey text on every
// screen, and the legend carries the most of it on one light frame: the
// "ALWAYS SHOWN" labels beside Closure and Serious warning, and "Showing".
// `--fg-3` moved from stone-500 to stone-600 there - 3.81:1 on the sheet's
// white to 5.51:1. The drive is legend.mjs's, imported rather than copied,
// so the two frames cannot drift apart.
//
// WHAT TO COMPARE AGAINST. Any earlier preview's legend shot: the words are
// the same, and only their ink is darker. The change is small on purpose.
// The maintainer picked it over moving the text to `--fg-2` (poll,
// 2026-09-26) because it keeps three levels of text.
export { default } from './legend.mjs'

export const caption =
  'The legend’s small grey text in the darker third level (#1670): “ALWAYS SHOWN” and “Showing” at 5.51:1 on white, from 3.81:1'
export const alt =
  'The legend sheet over the trail screen, scrolled to the foot: the Closure and Serious warning rows, each with the words ALWAYS SHOWN at the right in a mid grey, and below them the Showing control, its label in the same grey'
