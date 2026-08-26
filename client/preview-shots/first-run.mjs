// One of the two standing shots (see README.md): the entry cards every new
// hiker meets. Photographed on every pull request, whether or not the pull
// request touches this file, because a branch that breaks the very first
// screen breaks everybody — scripts/photograph-preview.mjs names it in
// STANDING rather than waiting for a diff to select it.
//
// Also the screen for the "what OurHike is" step's copy (#1059/#1060) - no
// drive needed, since that step is what loads first.
//
// Re-pointed 2026-08-26 (#1054), twice: first for a single ridge photograph,
// then for the pool - the maintainer sent the fixed pick back and asked for
// the whole reviewed gallery, drawn at random (lib/heroPhotos.ts). So this
// shot shows a DIFFERENT backdrop on every capture, which is the feature; the
// stable part to review is the brand plate, whose whole job is to stay
// legible over any of the seventeen.
export const caption = 'First run — over a photo drawn from the pool (#1054)'
export const alt =
  'The first-run entry card over a randomly drawn Appalachian Trail photograph, with the OurHike lockup, tagline and the photo’s credit on a dark plate in the top corner'

// The one recipe that must NOT skip first run — first run is the subject.
export const entry = true
