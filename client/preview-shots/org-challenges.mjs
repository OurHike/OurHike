// A club's challenges, and the one being edited (#1780, the handoff's frame #2a).
//
// WHAT THIS ANSWERS THAT A DIFF DOES NOT. The page's argument is mostly
// absences, and absences are invisible in a file list: no field anywhere to
// type a mile or a coordinate into (a place is a published waypoint, picked
// when the file is reviewed), no hiker named, no rank. A reviewer can only
// check those by looking at the editor with nothing missing from it.
//
// THE COLUMN TO LOOK AT IS "HIKERS IN". Three rows, three answers: a number
// the server sent, "fewer than 25" where it sent none because the count is
// below the k-anonymity floor, and "not live" for a draft no phone has. None
// of the three is ever a zero standing in for "we do not know".
//
// Invented organization, real ground, nobody signed in - the same demo org
// the other org-*.mjs shots use, whose challenges are Central Park's own and
// not the handoff's illustrative examples (client/src/org/demoOrg.ts says so
// above DEMO_CHALLENGES). No account, no report, no photo, no location fix.
export const caption =
  "A club's challenges — the list, and the editor with no field to type a place into"
// Written from the fixture and the component, not from a render: this
// sandbox's run of the recipe is reported in the pull request, and if the
// editor's foot falls below the 1280x800 fold the Publish button is the part
// of this description the frame does not carry.
export const alt =
  "The Challenges page of the demo organization, on desktop: the console rail with Challenges marked, a banner saying the organization is invented, the heading Challenges, a table of three challenges - Park Drive loop end to end, the Ramble's bridges and arches, and a draft Give a day to the North Woods - with columns for window, places, finished at and hikers in reading 64, fewer than 25 and not live; three tiles headed Your trails only, Places, not taps and Ships with the data; and beside the table an editor for the first challenge with a trail picker, What counts chips with Sections walked pressed, Opens and Closes date fields, Finished at, and When someone finishes set to send a patch"

// DESKTOP, because the console IS a desktop surface: the wireframes are
// 1440px and the rail is a fixed column, so a 390px capture of it is a
// photograph of a layout nobody uses - the same call every org-*.mjs makes.
export const desktop = true

export default async function drive(page) {
  // `new URL` against the page's own address, so this works at the preview's
  // base path and at the sandbox's root alike.
  await page.goto(
    new URL('org/central-park-throughikers/setup?page=challenges', page.url()).href,
    { waitUntil: 'load' },
  )

  // Settle on the thing the shot is of: the table's rows are rendered from
  // the demo fixture, so the first one proves the screen arrived.
  await page.getByRole('table').first().waitFor()
  await page
    .getByRole('heading', { name: 'Challenges', exact: true })
    .scrollIntoViewIfNeeded()
}
