// One of the two standing shots (see README.md): the entry cards every new
// hiker meets. Photographed on every pull request, whether or not the pull
// request touches this file, because a branch that breaks the very first
// screen breaks everybody — scripts/photograph-preview.mjs names it in
// STANDING rather than waiting for a diff to select it.
//
// Also the screen for the "what OurHike is" step's copy (#1059/#1060) - no
// drive needed, since that step is what loads first. The hero photo, the
// lockup and the step card are one screen rather than two: this component
// renders the brand plate as persistent chrome with the current step's card
// beneath it.
//
// The `alt` below says so, which it did not until 2026-08-27 - it described
// only the brand plate, so the preview comment was silent about the copy this
// shot is half the point of. That mattered the moment the money sentence
// changed: a reviewer reading alt text alone, or anybody on a screen reader,
// got nothing about the sentence under review. Verified by capture rather than
// by reading the component - `node scripts/screenshot.mjs --entry` puts both
// paragraphs plainly in frame at 390x844.
//
// Re-pointed 2026-08-26 (#1054), twice: first for a single ridge photograph,
// then for the pool - the maintainer sent the fixed pick back and asked for
// the whole reviewed gallery, drawn at random (lib/heroPhotos.ts). So this
// shot shows a DIFFERENT backdrop on every capture, which is the feature; the
// stable part to review is the brand plate, whose whole job is to stay
// legible over any of the seventeen.
export const caption = 'First run — over a photo drawn from the pool (#1054)'
export const alt =
  'The first-run entry card over a randomly drawn Appalachian Trail photograph, with the OurHike lockup, tagline and the photo’s credit on a dark plate in the top corner. Below it, step 1 of 3, “What OurHike is”: the map works with no bars and no data plan, and your money belongs with the people holding the tools — the ATC and other organizations who keep these trails open take members and donations directly, while OurHike takes no cut and holds no money. Then: no account, nothing to sign up for.'

// The one recipe that must NOT skip first run — first run is the subject.
export const entry = true
