// Safety & privacy with the two usage-statistics switches (#1902).
//
// WHAT TO LOOK FOR. Under "Use my location", whose note no longer says the
// fix is "sent nowhere unless you file a report" - it now says the fix also
// leaves sealed inside usage statistics while those are on - come "Share
// usage statistics" (ticked: on by default, the maintainer's split consent of
// 2026-10-27) and "Link them to my account" (unticked: nobody has been asked
// on a fresh install). Each note is the wording the maintainer approved as
// drawn (poll 3, frame A).
//
// Since #1885 the "Share usage statistics" note also lists choosing to give
// $0, and says the position goes with every count but that one: a support
// choice is counted by its level alone (features/EVENTING.md §0).
//
// The default state, signed out, on a phone that has downloaded nothing: the
// screen a hiker meets when they go looking. Nothing on it belongs to anybody.
export const caption =
  'Safety & privacy: "Share usage statistics" on by default and "Link them to my account" unticked, under a location note that now says the fix leaves sealed inside usage statistics (#1902)'

export const alt =
  'The Safety & privacy settings page: a "Use my location" switch with a note saying the fix leaves the phone only with a report you file or sealed inside usage statistics while those are on; a ticked "Share usage statistics" switch with a note listing what is counted, choosing to give $0 among them, that the position goes with each count but the $0 one, sealed as it arrives with only the rough area it falls in, a grid square about the size of a town, readable, kept six months, and that off stops all of it; an unticked "Link them to my account" switch with a note saying it adds a code made from the account, with no name or email, and keeps a running total that turning it off or deleting the account deletes; then the greyed "Hide my name on reports for…" row and the closures notice'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /safety & privacy/i }).click()
  await page.getByRole('checkbox', { name: 'Share usage statistics' }).waitFor()
}
