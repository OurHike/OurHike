// A published route's detail under the dark colour scheme, for #1670 -
// --fg-3 text is under WCAG AA contrast on every light surface, and the app
// uses it 229 times.
//
// WHY THIS SCREEN. Its provenance lines are the third text level, and they
// are what a hiker reads to judge a distance: "Route last verified by them
// on 2024-10-11", "measured on the trail lines this phone holds", the
// publisher's own figure. In dark mode `--fg-3` moved from bone-500 to
// bone-400: 4.96:1 to 6.35:1 on this page's `--bg-page` (ink-900, sampled
// from the frame). This frame is not the worst dark pair, and that is on
// purpose: the worst was `--fg-3` on the caution tint, 3.54:1 before and
// 4.53:1 now, and contrast.test.ts holds it. This frame is what the change
// looks like on an ordinary dark page.
//
// THE DARK SCHEME, NOT A PREFERENCE WRITE, as long-term-closures-night.mjs
// does it: the theme preference ships as `auto`, which follows
// `prefers-color-scheme` (lib/theme.ts), so the browser is asked for dark
// before the app loads and nothing is written to anybody's store.
import hikeDetail from './hike-detail.mjs'

export const caption =
  'A route’s provenance lines in the dark theme’s lighter third level (#1670): bone-400, 6.35:1 on the page, from 4.96:1'
export const alt =
  'The Wapiti to Docs Knob detail screen on a near-black page: the title in near-white, then smaller grey lines reading Route last verified by them on 2024-10-11, a figures line of 7.9 mi, a grey line naming that measurement as this phone’s and 8.5 mi as the publisher’s, a Moderate to Strenuous badge, and a grey Out and back line'

export async function before(page) {
  await page.emulateMedia({ colorScheme: 'dark' })
}

export default hikeDetail
