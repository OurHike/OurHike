// The recorder that turns #106's walk into data, at rest (#1180).
//
// WHY THE IDLE STATE IS THE SHOT, AND NOT A RECORDING IN PROGRESS.
//
// `.claude/skills/pr-screenshot/SKILL.md` forbids a real location fix in a
// published screenshot, and this is the one screen in the app whose entire
// job is writing fixes down. A shot of it recording would either carry a
// coordinate or carry a faked one dressed as real - and the reading a
// reviewer needs from this change is not what a trace looks like. It is
// whether the three things a tester must know BEFORE they tap are on the face
// of the control: what it costs in battery, what a locked phone does to it,
// and that the recording never leaves the phone. All three are only visible in
// the idle state, which is also the only state a hiker meets first.
//
// The middle one is here because the first version of this screen did not have
// it and promised the opposite, and a real walk came back short. This shot is
// the standing check that the correction is still on the page.
//
// The section is gated on "Use my location", so the recipe turns that on
// before navigating - with location off the panel is deliberately absent,
// which is the correct behaviour and a blank photograph.
//
// WHAT #1182 ADDED TO THIS FRAME, AND WHY IT BELONGS IN THE IDLE SHOT.
//
// The "Keep recording with the screen off" switch is offered before the walk
// rather than during it, because it is a decision ABOUT the walk: flipped
// mid-recording it would leave half a trace measuring the browser's watch and
// half measuring the native one, whose accuracy radius means a different thing
// (68% confidence against the web API's 95%). So it sits in exactly the state
// this recipe already photographs, and the note beside it - that the two are
// measured differently and the file records which - is the one sentence a
// tester needs before tapping rather than after exporting.
//
// The shot is taken in a browser, so the switch will also show its "this only
// works in the installed app" line. That is the honest reading here and the
// reason it is worded as a fact about browsers rather than as a failure: the
// preview IS a browser, and it is where every field test so far has happened.
export const caption =
  'Record a GPS trace, before anything is running — the battery cost, what a locked phone does to it, the on-device promise, and the screen-off switch with its warning that the two watches measure differently, all said before the button (#1180, #1182)'

export const alt =
  'The Safety & privacy settings page, scrolled down to the "Record a GPS trace" section below its location and closures rows: a Start recording button, a note saying it writes down where your phone thinks you are several times a minute and keeps the screen from going dark so it can, and that it will use a lot more battery than usual because the screen is most of that, a note saying that locking the phone yourself pauses recording until you unlock it and nothing already recorded is lost, a note saying the recording stays on this phone and is never uploaded or attached to a problem report, and an unchecked "Keep recording with the screen off" switch with a note saying it uses far less battery, that the phone shows a notice the whole time it runs, and that the readings it takes are measured slightly differently from the browser\u2019s so the saved file records which is which'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /safety & privacy/i }).click()

  // The section only exists once the app is allowed a position at all. The
  // switch is a real control here rather than a stub - it is the same
  // preference lib/useGeolocation.ts reads - so this is the tester's own
  // first step, photographed rather than mocked around.
  const useMyLocation = page.getByRole('checkbox', { name: 'Use my location' })
  if (!(await useMyLocation.isChecked())) await useMyLocation.check()

  await page.getByRole('heading', { name: 'Record a GPS trace' }).waitFor()

  // Waited on rather than assumed: if the switch stops rendering, this recipe
  // should fail loudly rather than publish a photograph of its absence under a
  // caption describing it. `scrollIntoViewIfNeeded` waits as well as scrolls,
  // so this is the settle and the framing at once (downloads-window.mjs and
  // legend.mjs use it the same way).
  const screenOff = page.getByRole('checkbox', {
    name: /keep recording with the screen off/i,
  })
  await screenOff.waitFor()

  // SCROLLED SO THE NOTE UNDER THE SWITCH FINISHES ITS SENTENCE, which is a
  // correction rather than a preference. The published frame at 43a14fc4 cut
  // it mid-word at the fold - "the saved file records which is" - while the
  // alt text described a further line that was not in the picture at all. An
  // alt text that outruns its image is the same failure as a display
  // outrunning its source, committed in the one text a reader who cannot see
  // the image depends on entirely.
  //
  // Verified by running this recipe locally (`node scripts/screenshot.mjs`,
  // 2026-08-29) rather than guessed at a second time: the page is short
  // enough that this scrolls only about 76px, and that is exactly enough to
  // finish the note. The section does NOT fill the frame and the alt text
  // does not claim it does - the location and closures rows are still above
  // it, which is honest and is how a tester meets the page anyway.
  await page
    .getByRole('heading', { name: 'Record a GPS trace' })
    .evaluate((node) => node.scrollIntoView({ block: 'start' }))
  await screenOff.scrollIntoViewIfNeeded()
}
