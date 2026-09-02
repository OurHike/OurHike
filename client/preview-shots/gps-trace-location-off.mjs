// A recording left open after the hiker switched location off (#1201).
//
// WHY THIS STATE IS WORTH ITS OWN FRAME, when gps-trace.mjs already
// photographs this screen.
//
// It is the state the bug created and the state the fix has to be judged on,
// and it is invisible in the idle shot. Before #1201, turning "Use my
// location" off mid-recording took the whole section away - and with it the
// app's only Stop button - while the five-second poll went on asking the
// platform for positions and the wake lock stayed held. So the recording
// could not be stopped without turning location back on first, which nothing
// on screen said.
//
// What the picture has to show is therefore two things at once: that the
// section is STILL THERE with a working Stop, and that the screen says why
// the reading count has stopped moving. A reviewer reading the diff has to
// hold `More.tsx`'s new condition and `recordingTrouble`'s new first branch
// in their head together to see that; the frame shows it.
//
// AND IT NEEDS NO POSITION AT ALL, which is why this screen can be
// photographed here and not while it is recording normally.
// `.claude/skills/pr-screenshot/SKILL.md` forbids a real location fix in a
// published shot, and gps-trace.mjs's header argues that a faked one is worse
// on the one screen whose whole job is reporting real GPS accuracy. Neither
// applies to this state: nothing has been recorded, no coordinate exists, no
// accuracy radius is rendered, and the "Last reading" row does not appear
// because `lastAccuracyM` is null. The harness grants no geolocation
// permission, so that is structural rather than lucky.
//
// The frame below was PHOTOGRAPHED AND LOOKED AT before this alt text was
// written - `node scripts/photograph-preview.mjs preview-shots/gps-trace-location-off.mjs`,
// 2026-09-02 - because the first draft of it described the "Use my location"
// switch, which is scrolled off the top and is not in the picture at all, and
// omitted the three status rows that are. `node scripts/screenshot.mjs <name>`
// does NOT run a recipe; it only names the file. That mistake produced a
// photograph of the Today screen under this caption, which is the failure
// gps-trace.mjs's header already records paying for twice.
export const caption =
  'A recording left open after "Use my location" was switched off (#1201) — the section stays, so Stop is still reachable, and the screen says why the count stopped rather than sending a tester outside to look for sky'

export const alt =
  'The Safety & privacy settings page scrolled to a GPS trace recording in progress. Above the section, the tail of the location explanation and the greyed-out Wrong-way alert and "Hide my name on reports for..." rows, both marked LATER, and the note that closures and serious warnings are not a setting. Then "RECORD A GPS TRACE": a Recording row reading "0 readings \u00b7 just started", a Trail position row reading "waiting for a fix", an App stalls row reading "none longer than 50 ms", the question "What are you doing right now?" over the three marker buttons — Standing still, Walking, Off the trail — and their note. Below them, in warning red: "You turned \u201cUse my location\u201d off, so nothing is being recorded. Turn it back on to carry on, or stop the recording and keep what it already has \u2014 nothing recorded so far is lost either way." Then a note that the screen is not being kept awake, and a Stop recording button. No position, mile or accuracy figure appears anywhere in the frame, because none has been recorded.'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /safety & privacy/i }).click()

  // On first, because the section does not exist until the app is allowed a
  // position at all - that gate is correct and gps-trace.mjs photographs its
  // other side.
  const useMyLocation = page.getByRole('checkbox', { name: 'Use my location' })
  if (!(await useMyLocation.isChecked())) await useMyLocation.check()
  await page.getByRole('heading', { name: 'Record a GPS trace' }).waitFor()

  await page.getByRole('button', { name: 'Start recording' }).click()
  // Waited on rather than assumed: the rest of this recipe is meaningless if
  // the recording never started, and a photograph of the idle state under
  // this caption would be worse than no photograph.
  await page.getByRole('button', { name: 'Stop recording' }).waitFor()

  // The switch the hiker flips, and the whole point of the frame.
  await useMyLocation.uncheck()

  // Waited on because this sentence IS the change - `recordingTrouble` now
  // answers this case ahead of every other, since the others ("no GPS signal
  // right now", "waiting for the first reading") are all wrong here and all
  // send a tester outside.
  const note = page.getByText(/turned .Use my location. off/i)
  await note.waitFor()

  await page
    .getByRole('heading', { name: 'Record a GPS trace' })
    .evaluate((node) => node.scrollIntoView({ block: 'start' }))
  // Framed on the note rather than the heading, so the sentence finishes
  // inside the frame - the correction gps-trace.mjs's header records paying
  // for twice.
  await note.scrollIntoViewIfNeeded()
}
