// The copy /for-orgs/ is made of, kept out of the page so a test can hold it
// to the things it must and must not say (tests/orgOnboarding.test.mjs).
//
// features/ONBOARDING.md records the maintainer's correction of 2026-08-27 -
// "There is no funding model today for the orgs" - after the app's own
// value-prop screen had claimed OurHike "funds the ATC and affiliated clubs"
// for weeks. That sentence is now guarded in the app by a test that reads the
// app's value-prop step, and that test cannot see this site. So the copy that
// could make the same mistake lives here, where a test can read it without
// rendering a page.

/** The four reasons, in the order the page shows them.
 *
 *  The fourth one is the money one and is the reason this file exists. It says
 *  where the money GOES - to the organization - and never that OurHike sends
 *  any, because OurHike sends none and has no arrangement under which it
 *  would. `title` carries markup because each is two lines on purpose: a
 *  four-card row reads as a row when the headings break in the same place.
 */
export const REASONS = [
  {
    key: "maps",
    title: "Beautiful maps,<br />free to every hiker",
    body: "Your sections drawn from your own geometry, with your own blaze colours, working with no bars and no data plan.",
  },
  {
    key: "reports",
    title: "Crowd-source<br />trail problems",
    body: "A blowdown reported at noon reaches the maintainer who covers that mile — not a generic inbox.",
  },
  {
    key: "volunteers",
    title: "Every hiker learns<br />about volunteering",
    body: "Your workdays appear where hikers already look — engage more volunteers, more frequently.",
  },
  {
    key: "money",
    title: "Members and donations<br />reach you directly",
    body: "The money goes to trail organizations, not a VC-backed tech company. OurHike is maintained by volunteers and keeps nothing beyond what running it costs — we publish the whole split, payment fees included, before we ever ask you to opt in.",
  },
];

/** The on-ramp and the three stages after it, plus the ongoing work.
 *
 *  Five entries and only three of them are stages, which is the point the row
 *  is making: registering is today and the volunteer work never finishes, so a
 *  reader can see where the end is without being told the tool has one.
 *
 *  Every duration here is @unvalidated. "About five minutes", "a day or two"
 *  and "an afternoon if your files are tidy" come from the design and nobody
 *  has watched an organization do any of it. What would settle them: the first
 *  real registration, timed. They are stated as estimates in the copy rather
 *  than as promises, which is the most this can honestly be.
 */
export const STAGES = [
  {
    key: "register",
    when: "THE ON-RAMP · TODAY",
    title: "Register the org",
    body: "Your web address, three admins, and where your giving pages live. About five minutes.",
    glyph: '<path d="M6 3v18M6 4h11l2.5 3L17 10H6z" />',
  },
  {
    key: "approve",
    when: "STAGE 1 · A DAY OR TWO",
    title: "Admins approve",
    body: "Each of the three says yes by email. Whoever answers first picks up the registry.",
    glyph:
      '<rect x="3" y="5.5" width="18" height="13" rx="2" /><path d="m3.5 7 8.5 6 8.5-6" />',
  },
  {
    key: "registry",
    when: "STAGE 2 · THE LONG CLIMB",
    title: "The hike registry",
    body: "Your GIS sections and featured hikes, read with you. An afternoon if your files are tidy.",
    glyph:
      '<path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z" /><path d="M9 4v13.5M15 6.5V20" />',
  },
  {
    key: "signoff",
    when: "STAGE 3 · SIGN-OFF",
    title: "All three confirm it",
    body: "Your admins read the registry line by line. When they agree it publishes — and onboarding is done.",
    glyph:
      '<circle cx="12" cy="12" r="8.5" /><path d="m8.5 12 2.5 2.5 4.5-5" />',
  },
  {
    key: "volunteers",
    when: "THEN · ONGOING",
    title: "Your volunteers",
    body: "Roles, coverage, your roster and their welcome emails. Not a stage to finish — the work the tool exists for.",
    glyph: '<path d="M12 3 4 19h16z" /><path d="M9.5 13.5h5" />',
  },
];

/** Every sentence this page puts in front of an organization, as one string.
 *
 *  Only so a test can read the lot without a DOM. It is not rendered.
 */
export function allCopy() {
  return [
    ...REASONS.map((r) => `${r.title} ${r.body}`),
    ...STAGES.map((s) => `${s.when} ${s.title} ${s.body}`),
  ].join(" ");
}
