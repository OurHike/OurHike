// The entry, visible from day one (#1964): "Your entry" from the challenge's
// own page at 3 of 25. The seeded ATC list takes no entries through OurHike
// (no `takes_entries`, as the reviewed file stands until the ATC confirms), so
// it points at the ATC's own rules rather than listing what the ATC would
// receive - the maintainer's poll of 2026-11-04, after the review of #2020 -
// with its finish line and the draft line, and nothing to send.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'The entry at 3 of 25 on a list the ATC collects itself: its rules, its finish line, nothing sent (#1964, seeded hiker)'
export const alt =
  'A screen headed Your entry under ATC · A.T. Summer Bucket List, with a draft banner, a line reading 3 earned over 3 days, the ATC’s rules link, The ATC collects entries itself, Its finish line is 25 for the drawing, and the draft’s nobody-to-send-to line'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('button', { name: 'Your entry' }).click()
  await page.getByText(/The ATC collects entries itself/).waitFor()
}
