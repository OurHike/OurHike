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

export interface OffRouteCardProps {
  follow: OffRoute
  units?: UnitSystem
  /** Frame the whole route on the map - the one navigational thing this
   *  screen can do without claiming ground. */
  onShowRoute: () => void
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
        <button type="button" className="off-route__primary" onClick={onShowRoute}>
          Show the whole route
        </button>
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
 * `role="alert"` because it is one, and because it may appear while the phone
 * is in a pocket and be read minutes later.
 */
export function OffRouteBand({ follow, units = 'imperial' }: OffRouteBandProps) {
  return (
    <div className="off-route-band" role="alert">
      <p className="off-route-band__head">You are not on your route</p>
      <p className="off-route-band__body">
        {formatShortDistance(follow.offRouteFeet, units)} from it, at the nearest point.
      </p>
    </div>
  )
}
