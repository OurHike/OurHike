// The size offer with no manifest: what a phone that cannot reach the bucket
// sees (#1167).
//
// WHY THIS IS A SECOND RECIPE rather than a second assertion on the first.
// #1167 removed hikingDetail.ts's hand-copied byte constants, which had
// drifted up to 34.7% from one environment and twice UNDERSTATED - the
// direction that strands a hiker who freed exactly enough room. `latest.json`
// is now the only thing that prices this sheet, and the question that leaves
// is what the card says when the manifest has not landed.
//
// It has to be a picture rather than a claim, because the answer is a copy
// decision on the screen where somebody decides whether they have room. There
// are three states a rung can be in and only two words available if you get
// it wrong: "Not offered" would hide a map the hiker can actually take, and a
// number would be invented. The frame shows the third.
//
// HOW THE STATE IS REACHED, deterministically rather than by luck: the drive
// aborts every request for `latest.json` and reloads, so `usePublishedSizes`
// resolves to nothing on a build that is otherwise fully wired. Routing
// before the reload is the same shape trail-notices.mjs uses to park its
// camera - the runner has already loaded the page by the time a drive runs,
// so anything that must affect the load has to be set and then reloaded into.
//
// This one CAN be checked in a sandbox, unlike the notices sheet: first run
// needs no conditions artifacts and no map data, so
// `node scripts/photograph-preview.mjs preview-shots/first-run-download-offline.mjs --dist`
// reaches it here. It was, before this was pushed.
//
// Nothing here reaches an account, anybody's reports, a campsite or a location
// fix - first run is pre-account by construction, and the card draws no map.
export const caption =
  'The same offer with the manifest blocked — a size withheld rather than guessed (#1167)'
export const alt =
  'The second first-run card over the hero photo: "Take the whole trail with you" with three size options — Light, Standard marked as recommended, and Fine — each reading "Unknown offline" where a figure would normally be, all three still selectable, above a Keep going button and a Decide this later link'

// First run is the subject, so the runner must not skip it.
export const entry = true

export default async function drive(page) {
  // Abort the manifest, not the whole origin: the point is a build that is
  // working normally and simply has not been told what the artifacts weigh.
  // Blocking everything would photograph a broken app instead.
  await page.route('**/latest.json', (route) => route.abort())
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('button', { name: 'Continue' }).click()

  // Wait on the rung rather than a timer - it both settles the shot and
  // asserts the state actually arrived. If a future change gives the picker a
  // size from somewhere else, this recipe fails loudly rather than quietly
  // photographing the priced card under a caption promising the opposite.
  await page
    .getByText(/unknown offline/i)
    .first()
    .waitFor()
}
