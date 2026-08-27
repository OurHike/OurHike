// First run on a laptop — the screen #1084 is about.
//
// The standing first-run shot photographs a phone (photograph-preview.mjs's
// STANDING), and until this recipe there was no way to photograph anything
// else: the runner captured every recipe at PHONE. That is why a desktop
// layout could regress unseen for as long as this one did — the backdrop was
// showing a quarter of its photograph on a 1920px window, and the camera had
// no way to look at a 1920px window.
//
// So the recipe carries `desktop`, the flag added with it, and the pair is
// the point: the wide layout now has a lens pointed at it, and the next
// change to it re-photographs itself by touching this file.
//
// WHAT TO LOOK FOR, since the backdrop is a random draw from the pool
// (lib/heroPhotos.ts) and no two captures show the same photograph: the
// photo reaches all four edges of the window with no pine band under it,
// the entry card is against the RIGHT edge rather than centred on the
// subject, and the brand plate is legible in the top-left corner over
// whatever was drawn.
export const caption = 'First run on a desktop — the photo fills the window (#1084)'
export const alt =
  'The first-run entry card docked to the right edge of a wide browser window, over an Appalachian Trail photograph filling the whole window, with the OurHike lockup, tagline and the photo’s credit on a dark plate in the top-left corner'

// First run is the subject, so it must not be skipped past.
export const entry = true

// The wide layout, not the phone. Above desktop.css's 900px breakpoint, which
// is the whole reason this recipe exists.
export const desktop = true
