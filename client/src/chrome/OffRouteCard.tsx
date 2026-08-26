// You are not on your route (#1041, frame `D11`).
//
// "Lost" is the first of the four ways CLAUDE.md says this app can hurt
// somebody, and a trail network is where it happens: 48% of sampled A.T.
// points through Harriman sit within 150 m of a DIFFERENT marked trail
// (features/NEARBY_TRAILS.md, measured by #771), so leaving your route there
// does not feel like leaving a trail at all. It feels like walking.
//
// TWO REFUSALS HOLD THIS SCREEN UP, and they are the frame's point rather
// than its caveats.
//
// The first is the ribbon's, one band up, and it is already
// chrome/ElevationRibbon.tsx's behaviour: with the hiker outside the drawn
// domain the "you are here" rule is DROPPED rather than clamped to an edge,
// because a rule pinned to the left edge reads as "you are at the start of
// this route".
//
// The second is this card's. There is no marked trail between a hiker in the
// laurel and their route - if there were, they would be standing on it - so
// this gives a distance and a bearing and DOES NOT DRAW A WAY BACK. A routed
// line across open ground is the confident-looking wrong answer: it looks
// exactly like a path, on the screen somebody uses to decide where to put
// their feet. Same posture #980 took on bail-outs, from the maintainer's own
// answer on #935: "There should be no guessing as to whether something is
// walkable or not."
//
// WHAT THE FRAME'S TWO BUTTONS BECAME. It draws "Point me at it" and
// "Re-route from a trail". The first needs a live compass heading, which
// nothing in this client reads today - a bearing printed beside a phone that
// cannot say which way it is held is a number a hiker has to orient by hand,
// and the sentence says so rather than a button implying otherwise. The
// second needs the route builder re-entered mid-walk with a new start, which
// is #983's ground. Both wait; what ships is the two things this screen can
// honestly do - put the whole route back on screen, and stop following.

import { compassPoint, type OffRoute } from '../lib/dayHikeFollow'
import { formatDistance, formatShortDistance, type UnitSystem } from '../lib/units'
import './chrome.css'

/**
 * How far off the route reads, in one rule for both the band and the card.
 *
 * Feet under a tenth of a mile, miles above it: "0.1 mi" and "460 ft" are the
 * same distance and only one of them is a number somebody can pace out.
 *
 * ONE function because the two surfaces render the SAME number at the same
 * moment - one under the header, one in the lower third - and they were
 * formatting it differently. "2,640 ft from it" over "0.5 mi away" is a hiker
 * doing arithmetic to work out whether their phone is telling them one thing
 * or two, at the moment they are least able to.
 */
function offRouteDistance(feet: number, units: UnitSystem): string {
  return feet < 528
    ? formatShortDistance(feet, units)
    : formatDistance(feet / 5280, units)
}

export interface OffRouteCardProps {
  follow: OffRoute
  units?: UnitSystem
  /**
   * Frame the whole route on the map - the one navigational thing this screen
   * can do without claiming ground.
   *
   * Omitted when there is no route drawn to frame, and then the button is not
   * rendered at all. It used to be offered unconditionally and, without the
   * geometry artifact, did nothing when pressed: a dead control on the
   * screen a hiker reaches when they are lost is worse than one fewer
   * control (#1044 review, and chrome/LineSheet.tsx's rule).
   */
  onShowRoute?: () => void
  onStopFollowing: () => void
}

export function OffRouteCard({
  follow,
  units = 'imperial',
  onShowRoute,
  onStopFollowing,
}: OffRouteCardProps) {
  const { nearest } = follow
  // Feet under a tenth of a mile, miles above it: "0.1 mi" and "460 ft" are
  // the same distance and only one of them is a number somebody can pace out.
  const away =
    nearest.feet < 528
      ? formatShortDistance(nearest.feet, units)
      : formatDistance(nearest.feet / 5280, units)

  return (
    <section className="off-route" aria-label="You are off your route">
      <p className="off-route__lead">
        The nearest point of your route is <strong>{away}</strong> away,{' '}
        {compassPoint(nearest.bearingDeg)}.
      </p>

      <div className="off-route__refusal">
        <p className="off-route__refusal-head">We will not draw you a line back</p>
        <p className="off-route__refusal-body">
          There is no marked trail between you and your route, and a line across open
          ground would look like a path. Walking back the way you came is ground you know
          is walkable; this bearing is not.
        </p>
      </div>

      <div className="off-route__actions">
        {onShowRoute !== undefined && (
          <button type="button" className="off-route__primary" onClick={onShowRoute}>
            Show the whole route
          </button>
        )}
        <button type="button" className="off-route__secondary" onClick={onStopFollowing}>
          Stop following
        </button>
      </div>
    </section>
  )
}

export interface OffRouteBandProps {
  follow: OffRoute
  units?: UnitSystem
}

/**
 * The one-line band under the header, which is the first thing a hiker sees.
 *
 * UNDER the header rather than in `.map-screen__alerts` above it, and the
 * difference is what each band is about. That strip is the trail's condition
 * ahead - a closure, a serious warning, an ATC advisory - things that are
 * true for everyone walking that ground. This is about one hiker's own route,
 * which nobody else on that trail is on, and frame `D11` places it under the
 * header for the same reason: it belongs with the mode signal it qualifies.
 *
 * NO LIVE ROLE ON THIS BAND (#1055), for the reason chrome/MapScreen.tsx
 * gives 46 lines above the slot it renders into. It carried `role="alert"`,
 * and the body below ends in a distance that App.tsx recomputes on every GPS
 * fix - `offRouteFeet` is an unrounded float printed as whole feet, so under
 * canopy the string inside the region changed while the hiker stood still. A
 * live region re-announces on any mutation inside it, and `role="alert"` is
 * the assertive one: it cuts off whatever a screen reader was mid-sentence
 * through. That is #315's defect exactly, at 528x the step - #315's number
 * was tenths of a mile and this one was Math.round(feet).
 *
 * What is announced instead is MapScreen's own polite line, via
 * `followAnnouncement`: one sentence, no number, changing only when the
 * hiker crosses the threshold rather than when the fix wobbles. So it fires
 * once per event, which is what the hysteresis in lib/dayHikeFollow.ts
 * already exists to make true.
 *
 * The distance stays here, visible and reachable by navigating to it. It is
 * worth reading; it is not worth being interrupted for forty times an hour.
 */
export function OffRouteBand({ follow, units = 'imperial' }: OffRouteBandProps) {
  return (
    <div className="off-route-band">
      <p className="off-route-band__head">You are not on your route</p>
      <p className="off-route-band__body">
        {offRouteDistance(follow.offRouteFeet, units)} from it, at the nearest point.
      </p>
    </div>
  )
}
