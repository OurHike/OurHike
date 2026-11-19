// More → Your support (#1876): the row, and the page Stop lives on.
//
// WHAT THE FRAME WILL SHOW, AND WHAT IT WILL NOT. A preview is built with no
// backend - `VITE_API_BASE_URL` is deliberately unset in pr-preview.yml - and
// the support ask is dormant in any build without one (lib/support.ts's
// `shouldAsk`, the maintainer's "backend first", 2026-10-23). So this frame
// is the page as an unconfigured build shows it: the Your support row on More
// with its "$0 included" line, and the page saying support isn't switched on.
// The day-5 sheet, the $0 nudge and the Stop confirm need a backend this
// camera has no way to reach; the pull request carries sandbox frames of
// those, taken against a stand-in API, and says so.
//
// Nothing here reaches an account, a hiker's own report, a dispersed campsite
// or a real location fix - the four things a shot must never contain
// (.claude/skills/pr-screenshot/SKILL.md).
export const caption = 'More → Your support, in a build with no backend (#1876)'
// Only what is in the frame: the row itself is one screen back and is not.
export const alt =
  'The Your support page under More, with a back link to More. It says support is not switched on in this build yet and that everything in OurHike is free for everyone either way, above a link titled "Why OurHike is pay-what-you-want" with the hint "The story, and where every dollar goes".'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /^Your support/ }).click()
  await page.getByRole('heading', { name: 'Your support' }).waitFor()
}
