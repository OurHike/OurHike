// The Hours form's link out to NYNJTC's own volunteer-hours form (#1154) - a
// courtesy link, never a data connection. OurHike's own logbook (#761) stays
// exactly as designed; this is the one line that says so, and it renders on
// the plain form with nothing logged, so the drive below needs no data and
// no sign-in prompt.
export const caption = "Your hours — the link out to NYNJTC's own form (#1154)"
export const alt =
  'The Volunteer page scrolled to Your hours: the day/hours/activity/note form, above it a line reading Volunteering with NYNJTC? This logbook is OurHike’s own — report the same day on NYNJTC’s own volunteer hours form too, where you’ll sign into your NYNJTC account, with NYNJTC’s own volunteer hours form as a link out'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /volunteer/i }).click()

  await page.getByRole('heading', { name: 'Your hours' }).scrollIntoViewIfNeeded()
}
