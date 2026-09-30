// An organization's own loaded data, drawn in the app (#1540).
//
// WHY THIS SCREEN AND NOT THE CONSOLE'S FRONT PAGE. The question a reviewer
// has about this branch is "does an org's GIS actually come out the other end
// as something a person can read", and the sign-off screen is the only one
// that answers it with both halves at once: the registry as a table, and the
// same sections drawn from their own geometry beside it. The setup hub shows
// counts, which is a claim rather than the data.
//
// THE ORG IS INVENTED AND THE GROUND IS REAL. Central Park Throughikers do
// not exist; the coordinates are the park's four surveyed corners and its
// real paths (client/src/org/demoOrg.ts says so at length, and the banner at
// the top of the shot says it to the reviewer). So nothing here is anybody's
// data: no account is signed in, no report or photo appears, and there is no
// location fix — the four things a shot must never carry.
//
// It is reached by URL rather than by tapping, because that is how the org
// surface is reached at all: `lib/orgRoute.ts` answers three addresses and
// nothing in the hiker's app links to them.
export const caption =
  "An organization's registry as the app draws it — the table they signed off, and their own geometry beside it"
// WHAT IS ACTUALLY IN THE FRAME, checked against the render rather than
// described from the source. The sign-off panel and its "0 of 3" are BELOW
// the 1280x800 fold and are not claimed here - legend.mjs carries the story
// of a caption that named something outside its own frame and reached a
// reviewer that way.
export const alt =
  'The registry sign-off screen of the demo organization, on desktop: the console rail on the left, a banner saying the organization is invented and the ground is real, the heading "All three admins confirm it is accurate" with a stage 3 of 3 eyebrow reading 2 of 3, a table of six sections carrying the park, the trail, a coloured blaze swatch with the org\'s own blaze word beside it, the section name, its two end anchors and its length, and beside the table a schematic map drawing those same sections from the geometry the org supplied, captioned "All 6 sections". The head of a Blaze mapping panel is visible at the foot.'

// DESKTOP, because the console IS a desktop surface: the wireframes are
// 1440px, the rail is a fixed 348px column, and a 390px capture of it is a
// photograph of a layout nobody uses. The volunteer's own screens work at
// both widths - they are shot wide here so the three org shots read as one
// set beside each other in the comment.
export const desktop = true

export default async function drive(page) {
  // `new URL` against the page's own address, so this works at the preview's
  // base path and at the sandbox's root alike - the two differ, and a
  // hardcoded absolute path is wrong in whichever one it was not written for.
  await page.goto(
    new URL('org/central-park-throughikers/setup?page=signoff', page.url()).href,
    {
      waitUntil: 'load',
    },
  )

  // Settle on something observable rather than a fixed wait: the registry
  // table is what the shot is of, so its first row is the thing that proves
  // the screen arrived rather than the thing that happens to be slowest.
  await page.getByRole('table').first().waitFor()
  await page.getByText('Blaze mapping').scrollIntoViewIfNeeded()
}
