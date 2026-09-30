// More's home (#1054): the storage card and the six destination rows - the
// five that replaced the four Tabs panels, and Challenges (#1780) after
// Volunteer & report - each row carrying a one-line summary of
// the state behind it, so the shot is evidence the summaries render honestly
// on a phone with nothing downloaded ("Nothing downloaded yet") and nobody
// signed in ("Not signed in").
export const caption =
  'More — six destinations over the storage card, Challenges after Volunteer & report (#1054, #1780)'
export const alt =
  'The More screen: a pine header, an On this phone card admitting nothing is downloaded, and six rows - You, The map, Safety & privacy, Volunteer & report, Challenges, Where this map comes from - each with a one-line summary'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
}
