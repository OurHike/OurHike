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
  'The Safety & privacy settings page: a "Use my location" switch turned on, and below it a "Record a GPS trace" section with a Start recording button, a note saying it keeps the screen from going dark and will use a lot more battery because the screen is most of that, a note saying that locking the phone yourself pauses recording until you unlock it and nothing already recorded is lost, a note saying the recording stays on this phone and is never uploaded or attached to a problem report, and a "Keep recording with the screen off" checkbox with a note saying it uses far less battery, that the phone shows a notice the whole time, and that the readings it takes are measured slightly differently from the browser\u2019s so the saved file records which is which — followed, in a browser, by a line saying this only works in the installed app'

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
  // should fail loudly rather than publish a photograph of its absence with a
  // caption describing it.
  await page
    .getByRole('checkbox', { name: /keep recording with the screen off/i })
    .waitFor()
}
