// A published route's detail under the dark colour scheme, for #1670 -
// --fg-3 text is under WCAG AA contrast on every light surface, and the app
// uses it 229 times.
//
// WHY THIS SCREEN. It is the one frame the preview's phone reaches that shows
// both halves of #1670 at once, on the same page:
//
//   - The trust lines, "Route last verified by them on 2024-10-11" and
//     "measured on the trail lines this phone holds · Vernon Trails says
//     8.5 mi", which a hiker reads to judge a distance. They moved out of the
//     faint grey into `--fg-2` (bone-300 in dark): 8.74:1 on this page's
//     `--bg-page` (ink-900, sampled from the frame), from bone-500's 4.96:1.
//     test/trustLines.test.ts holds the list.
//   - "Out and back · Vernon State Forest", which stays in `--fg-3`. That grey
//     itself moved from bone-500 to bone-400 here: 4.96:1 to 6.35:1.
//
// This frame is not the worst dark pair, and that is on purpose: the worst was
// `--fg-3` on the caution tint, 3.54:1 before and 4.53:1 now, and
// contrast.test.ts holds it. This frame is what the change looks like on an
// ordinary dark page.
//
// THE DARK SCHEME, NOT A PREFERENCE WRITE, as long-term-closures-night.mjs
// does it: the theme preference ships as `auto`, which follows
// `prefers-color-scheme` (lib/theme.ts), so the browser is asked for dark
// before the app loads and nothing is written to anybody's store.
import hikeDetail from './hike-detail.mjs'

export const caption =
  'A route’s trust lines in the secondary grey and its facet line in the lighter faint grey, dark theme (#1670): 8.74:1 and 6.35:1 on the page, both from 4.96:1'
export const alt =
  'The Wapiti to Docs Knob detail screen on a near-black page: the title in near-white, then a light grey line reading Route last verified by them on 2024-10-11, a figures line of 7.9 mi, a light grey line naming that measurement as this phone’s and 8.5 mi as the publisher’s, a Moderate to Strenuous badge, and a dimmer grey Out and back line'

export async function before(page) {
  await page.emulateMedia({ colorScheme: 'dark' })
}

export default hikeDetail
