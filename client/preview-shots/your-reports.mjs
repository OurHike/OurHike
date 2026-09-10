// Your reports (#1373, frame 9d): what this phone has reported, waiting and
// sent, under More → Volunteer & report.
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the door exists and that the empty
// state is a sentence rather than a blank: the preview's phone has never
// filed anything, so the frame is "Nothing reported from this phone yet"
// with where a report starts. The two shelves - "Waiting to send" from the
// outbox and "Sent from this phone" from lib/sentReports.ts's ledger, with
// the live list's Waiting / Confirmed / Fixed / Not confirmed beside a sent
// row - need a report in the queue and one that went, which no recipe seeds
// (a report is somebody's data); YourReports.test.tsx and
// App.yourReports.test.tsx hold both shelves.
//
// Nobody's data: no account, no outbox item, no trail name - so the
// "Reported as …" line is absent too, honestly.
export const caption =
  'Your reports, under Volunteer & report — the door, and the honest empty state on a phone that has reported nothing (#1373, frame 9d)'
export const alt =
  'The More tab’s Volunteer & report page scrolled to a "Your reports" heading with the sentence "Nothing reported from this phone yet. A report starts from a waypoint’s card, a long press on the map, or the door above." and a back link reading "‹ Volunteer & report"'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /^Volunteer & report/ }).click()
  await page.getByRole('button', { name: 'Your reports' }).click()
  await page.getByText(/Nothing reported from this phone yet/).waitFor()
}
