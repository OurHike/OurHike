// A through-route badge with nothing in the mark's slot (2026-09-29).
//
// WHAT CHANGED AND WHY IT NEEDS A PICTURE. map/trailBadges.ts's `text-field`
// carried `['coalesce', ['image', mark], ['image', chip]]`, so a trail whose
// steward has granted nothing still wore an OurHike-drawn blaze chip where
// that organization's mark goes. sources.json's `org_marks` block had
// already ruled on that shape of thing - "never a placeholder mark, never an
// initial, never a generated shape" - so the coalesce is gone and a markless
// badge is now the plate and the name alone.
//
// THIS FRAME IS THE ARGUMENT AGAINST THE CHANGE, AS MUCH AS FOR IT.
// long-path-badge.mjs opens with the maintainer's own words - "All long
// distance trails should have that Pill and a logo" - and this change means
// most of them do not have the logo, because nobody has asked their
// organizations for it. pipeline/reference/trail_marks.json holds 35 marks
// found on the stewards' own sites against exactly that day, and ships none
// of them, because test_org_marks.py wants a recorded basis and 33 of the 35
// have none. What is on the screen here is the honest state that leaves:
// a named pill with an empty slot, which is the thing most likely to prompt
// somebody to go and ask. If the maintainer looks at this and prefers the
// chip, the chip is one revert away and this recipe is the evidence for
// that call rather than against it.
//
// WHY LAKE TIORATI AT z12 AND NOT THE OPENING CAMERA. Below POI_PIN_MIN_ZOOM
// the other organizations' trails draw from the coarse overview sketch, and
// the opening frame badges the A.T. and the Long Path - the two trails that
// DO carry a mark, which is the one thing this frame must not show alone.
// Over Harriman the full lines draw from the tiles with their names, so the
// Ramapo-Dunderberg, the Arden-Surebridge and the rest badge beside the
// A.T., and the difference between a granted mark and none is the whole
// picture. Same camera and same reasons as legend-trails-in-view.mjs and
// network-above-the-seam.mjs, reusing a way of reaching the screen rather
// than inventing one.
//
// WHAT MAY DIFFER BY BUILD, said rather than promised. The badge falls back
// to the mark alone where the full pill has no free position - but only for
// a trail that HAS a mark, since a bare nothing is not a badge
// (map/trailsInView.ts's `anchorWithRoom` now keeps a markless trail on the
// full plate for that reason). And until a publish has carried
// nearby_trails.pmtiles to the bucket this preview reads, the frame may hold
// the A.T. alone - the same "has publish-vector-data.yml run since the
// merge" question network-above-the-seam.mjs's frame already asks, and the
// honest state a phone on an older release is in.
//
// Nobody's data is in the frame: no account, no notes, no reports, no
// location fix, and no dispersed campsite - the pins here are the park's own
// shelters and water at a camera the app already photographs.

export const caption =
  'Harriman at z12 — the A.T. on its pill with the ATC mark, and the trails around it badged with an empty slot where their stewards have granted no mark (#933, 2026-09-29)'
export const alt =
  'A phone map over Lake Tiorati in Harriman State Park: the Appalachian Trail as a cased line carrying a paper pill with the round ATC mark and its name, and other trails nearby carrying paper pills of the same shape that hold only a trail name, with no logo in front of it'

/** legend-trails-in-view.mjs's own note sizes this: the tiles behind these
 *  lines land well after the chrome, and the badge is the SUBJECT here, so
 *  this waits as long as long-path-badge.mjs does rather than as long as the
 *  legend recipe does - that one is photographing a panel that lists what
 *  drew, this one is photographing what drew. */
export const wait = 12000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, seeded the way network-above-the-seam.mjs
  // seeds it: Lake Tiorati, where the A.T., the Ramapo-Dunderberg and the
  // Long Path's feeder trails all sit inside one z12 frame.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.09, 41.25], zoom: 12 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Map' }).click()

  // No hike seeded and nothing tapped: `taken` styling is legend-trails-in-
  // view.mjs's subject, and a taken trail here would put a second difference
  // in a frame that exists to show one.
}
