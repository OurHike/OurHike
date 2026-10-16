// North-central Washington at zoom 6, where UA's club closures are densest:
// thread 4279229785 of the collaborator's review of #1805 — dlt → dbt
// re-platform as one go/no-go change.
//
// WHAT THE FRAME HAS TO SHOW: one small ✕ per club closure, thinned (the
// maintainer's variant A, "small ✕, thinned",
// 2026-10-15, from q22_frames.html). At z5 and z6 each closure gets the
// chain's own cross, about 7.2 px of ink, in the closure ink on a paper ring,
// at one point on it (map/clubClosureLayers.ts's buildClubClosureFarLayer);
// where closures crowd, a ✕ that would overlap one already placed is
// dropped, so the fire closures over the Cascades read as a scatter of ✕s
// and not as the black-and-white smudges the clamp removed. The clubs' paper,
// trace and shade still start at CLOSURE_MARK_MIN_ZOOM (7), and the ✕s stop
// there. The frame of 2026-10-15 drew 28 ✕s at this camera on UA's file in
// a 320 px square (q22_frames.html, variant A at z6); this 390 x 660 frame
// will place a different number.
//
// THE FILE HAS TO HAVE ARRIVED, or an empty frame proves nothing: the drive
// waits for conditions/trail_closures.json to be served after the reload and
// throws if it never is, so the comment says the camera could not take this
// rather than photographing a map with no closures loaded. A preview built
// against production finds no such file there today (2026-10-15) and gets
// that sentence; the previews of the pull request named above read UA. At
// z7 the small ✕s give way to the bold ✕ and point crosses as before;
// club-closures-on-the-map.mjs photographs the mark near in, on invented
// closures.
//
// REAL DATA, AND THE FOUR THINGS A SHOT MUST NEVER HOLD
// (.claude/skills/pr-screenshot/SKILL.md): no account and no location fix in
// a CI browser; no campsite, because waypoint pins start at z7
// (map/poiLayers.ts's POI_PIN_MIN_ZOOM) and this is z6; and nobody's report:
// the only report-shaped mark drawn at this zoom is a moderator-escalated
// serious warning (map/warningLayers.ts, at every zoom), which the standing
// trail-screen shot already risks over the whole lower 48, and UA's
// conditions/reports.json held none on 2026-10-15. Every closure is an
// agency's or a club's own public notice.
//
// The camera is seeded through fixtures/regionCamera.mjs's openMapAt, the
// region shots' own: lib/cameraMemory.ts's session-storage key, a reload, the
// Map tab, and the map's landmark waited for.

import { openMapAt } from './fixtures/regionCamera.mjs'

/** Centred on the densest of UA's club closures at this zoom. */
export const camera = { center: [-120.8, 47.5], zoom: 6 }

export const caption =
  'North-central Washington at zoom 6, over UA’s real club closures (variant A): each closure gets one small black ✕ on a white ring, and where closures crowd the ✕s are thinned so they never pile up, so the fire closures over the Cascades read as a scatter of ✕s, not as the black-and-white smudges of before. A tap on a ✕ opens that closure’s sheet. The drive waits for conditions/trail_closures.json, so a frame with no ✕s means the file did not load. From zoom 7 the ✕s give way to the bold ✕ and the point crosses.'

export const alt =
  'The map screen over north-central Washington at zoom 6: the trail network as thin red lines over the Cascades and the Columbia Basin, with small black ✕ marks on white rings scattered over the mountains, spaced apart so none touch.'

/** A state's worth of network tiles at a coarse zoom, and the 4.5 MB
 *  closures file, before the frame settles. */
export const wait = 8000

/** How long the drive waits for the closures file after the reload. */
const CLOSURES_FOR_MS = 45_000

export default async function drive(page) {
  // Listening before the reload, so the read the reload makes is the one
  // waited for. Settled to a value either way, never left to reject: if
  // openMapAt throws first, a rejection nobody awaits would take the whole
  // runner down rather than this one shot.
  const closures = page
    .waitForResponse(
      (response) =>
        /\/conditions\/trail_closures\.json(\?|$)/.test(response.url()) &&
        response.status() < 400,
      { timeout: CLOSURES_FOR_MS },
    )
    .then(
      () => null,
      () =>
        new Error(
          `conditions/trail_closures.json was not served within ${CLOSURES_FOR_MS / 1000} s ` +
            'of the reload, so this frame could not show the clubs’ closures as small ✕s at zoom 6',
        ),
    )
  await openMapAt(page, camera)
  const missing = await closures
  if (missing !== null) throw missing
}
