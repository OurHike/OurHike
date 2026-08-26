// More's home (#1054): the storage card and the five destination rows that
// replaced the four Tabs panels - each row carrying a one-line summary of
// the state behind it, so the shot is evidence the summaries render honestly
// on a phone with nothing downloaded ("Nothing downloaded yet") and nobody
// signed in ("Not signed in").
export const caption = 'More — five destinations over the storage card (#1054)'
export const alt =
  'The More screen: a pine header, an On this phone card admitting nothing is downloaded, and five rows - You, The map, Safety & privacy, Volunteer & report, Where this map comes from - each with a one-line summary'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
}
