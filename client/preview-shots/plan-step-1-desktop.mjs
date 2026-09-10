// Step 1 on a laptop, beside the map (the maintainer's review of #1374: "That
// 3 step process should be a sidebar on the map. Match the original
// design"; the design's R2, "the map never leaves"). The phone's step 1 is
// the Plan tab's own page (plan-step-1.mjs); on a laptop the shell hands
// the same element to the map's beside-the-map slot, so it is the first
// face of the column steps 2 and 3 take, at the right edge of the map. The
// shot is the evidence that the map is there and the column is where the
// builder's will be.

export const caption =
  'Step 1 on a laptop — "Where do you want to go?" as the column beside the map, where step 2’s builder and step 3’s review will stand (#1374 review; the design’s R2)'
export const alt =
  'A wide browser window with the OurHike sidebar down the left, Plan selected, the map filling the middle, and a column down the right holding step 1 of the planning spine: a three-stop rail reading Day hike, Route and Details with the first stop lit, the heading "Where do you want to go?", the search field, the doors - or, on a build with no junction graph, the sentence saying the trail network is not on the phone with a Try again button - then "or start from one of these" with its shelf, and Cancel at the foot'

// The wide layout is the subject.
export const desktop = true

export default async function drive(page) {
  // Through the Plan tab's own primary, not Today's pinned bar: the bar is
  // Today's (chrome/PinnedBar.tsx), and the Plan tab a laptop lands on has
  // "Start on the map" where the phone's recipe found the bar - the camera
  // caught the bar's door timing out here at 05e9506a.
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: 'Start on the map' }).click()
  await page.getByRole('heading', { name: 'Where do you want to go?' }).waitFor()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
