// North-central Washington at zoom 6, where UA's club closures are densest:
// thread 4279229785 of the collaborator's review of #1805 — dlt → dbt
// re-platform as one go/no-go change.
//
// WHAT THE FRAME HAS TO SHOW: nothing of a club closure. From this change the
// clubs' paper, trace and shade start at lib/closureStyle.ts's
// CLOSURE_MARK_MIN_ZOOM (7), with the far mark and the point cross that
// already did (map/clubClosureLayers.ts). Before it they had no minzoom, and
// below z7 every closure was a 4 px white paper under a 1.4 px dotted trace
// whatever its length, so the 907 closures UA's file of 2026-10-15 puts in
// a 390 x 660 px frame here drew as black-and-white smudges over the
// Cascades (rendered that day, before and after). Look for the trail
// network's thin lines and no black-and-white marks anywhere.
//
// THE FILE HAS TO HAVE ARRIVED, or an empty frame proves nothing: the drive
// waits for conditions/trail_closures.json to be served after the reload and
// throws if it never is, so the comment says the camera could not take this
// rather than photographing a map with no closures loaded. A preview built
// against production finds no such file there today (2026-10-15) and gets
// that sentence; the previews of the pull request named above read UA. At
// z7 the same closures draw their bold ✕ and point
// crosses as before; club-closures-on-the-map.mjs photographs the mark near
// in, on invented closures.
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
  'North-central Washington at zoom 6, over UA’s real club closures (review thread 4279229785): nothing of a club closure draws below zoom 7 now, where before about 900 of them drew here as black-and-white smudges. The drive waits for conditions/trail_closures.json, so an empty frame means clamped, not unloaded. From zoom 7 the bold ✕ and the point crosses draw as before.'

export const alt =
  'The map screen over north-central Washington at zoom 6: the trail network as thin red lines over the Cascades and the Columbia Basin, with no black-and-white closure marks anywhere in the frame.'

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
            'of the reload, so this frame could not show the clubs’ closures held off zoom 6',
        ),
    )
  await openMapAt(page, camera)
  const missing = await closures
  if (missing !== null) throw missing
}
