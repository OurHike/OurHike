// One of the two standing shots (see README.md): the entry cards every new
// hiker meets. Photographed on every pull request, whether or not the pull
// request touches this file, because a branch that breaks the very first
// screen breaks everybody — scripts/photograph-preview.mjs names it in
// STANDING rather than waiting for a diff to select it.
//
// Also the screen for the "what OurHike is" step's copy (#1059/#1060) - no
// drive needed, since that step is what loads first.
export const caption = 'First run'
export const alt = 'The first-run entry card'

// The one recipe that must NOT skip first run — first run is the subject.
export const entry = true
