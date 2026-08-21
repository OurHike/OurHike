// The elevation ribbon (WIREFRAMES.md §1.3).
//
// The SVG geometry is fixed by the wireframe - viewBox "0 0 100 40" with
// preserveAspectRatio="none", so the profile stretches to whatever width the
// phone has while the waypoint lanes underneath share the same 0-100
// percentage space. That shared coordinate space is the whole reason a pin at
// 60% sits under the part of the climb it belongs to.
//
// The time estimate comes from lib/naismith.ts. It is a DURATION and never an
// arrival clock: Naismith gives no descent credit and knows nothing about
// breaks, so an arrival time would be a promise the rule cannot keep.
//
// It draws two different things, and the difference is who is asking. With a
// GPS fix it is WIREFRAMES.md's field instrument: ten miles around the hiker,
// a "you are here" rule, the next climb called out. While the route builder is
// open it is lib/planRibbon.ts's picture of the stretch being laid out (#910),
// which has no "ahead" and usually no rule - the phone's answer to the desk
// question the desktop chart (#135) already answers above the breakpoint. The
// geometry, the shading and the min/max labels are identical either way; only
// `currentMile`, `upcomingClimb` and the accessible name differ, because those
// are the three things that make a claim about a hiker rather than about the
// ground.
//
// The samples stay in feet and miles whatever the hiker reads in - that is
// what the published profile carries (`elevation_ft`, `distance_mi`) and what
// the geometry below is computed from. Only the three labels convert, through
// lib/units.ts. Converting the samples instead would put a rounded number into
// the path arithmetic for nothing: the SVG is a shape, and a shape has no
// units.

import { naismithTime } from '../lib/naismith'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'

const VIEW_W = 100
const VIEW_H = 40

export interface ElevationSample {
  mile: number
  elevationFt: number
}

export interface UpcomingClimb {
  startMile: number
  endMile: number
  ascentFt: number
}

export interface ElevationRibbonProps {
  samples: ElevationSample[]
  /** Where the hiker is, on the samples' own axis - or null when nothing on
   *  screen knows. Null is not a degraded state: the planning ribbon (#910)
   *  draws a stretch the hiker may be a thousand miles from, and a rule
   *  pinned to the left edge of it would be a claim about their position
   *  rather than the absence of one. */
  currentMile: number | null
  upcomingClimb?: UpcomingClimb
  /**
   * What this ribbon is a picture of, which changes only its accessible name
   * - and has to, because "ahead" is a claim. The fix-anchored ribbon shows
   * the ground in front of a walking hiker; the planning one (#910) shows a
   * stretch somebody is laying out, which is in front of nobody.
   */
  subject?: 'ahead' | 'planned-stretch'
  /**
   * The stretch of trail this ribbon's full width stands for - what x=0 and
   * x=100 mean. Defaults to the first and last sample, which is what it has
   * always been and is right whenever the samples reach both edges.
   *
   * It is worth being able to say otherwise, because the lanes underneath are
   * positioned in this same 0-100 space by whoever supplies them, and the two
   * only line up while they agree about which ground the width covers. They
   * can disagree by a sample spacing at each end - the profile is sampled
   * every 25 m and a window edge falls where it falls - which is enough to
   * push a shelter sitting exactly at the end of a planned stretch off the
   * end of its lane. With a domain given, the samples are drawn at their real
   * fraction of it: a stretch whose DEM coverage starts late draws a line
   * that starts late, rather than one stretched to fill ground it never
   * measured.
   */
  domain?: { startMile: number; endMile: number }
  /** Which units the three labels read in. Defaulted rather than required, so
   *  a ribbon rendered outside the shell still says something true - and
   *  defaulted to the same value lib/userPreferences.ts does, so the default
   *  is the preference's default rather than a second opinion about it. */
  units?: UnitSystem
}

function pctAlong(mile: number, startMile: number, endMile: number): number {
  const span = endMile - startMile
  return span === 0 ? 0 : ((mile - startMile) / span) * 100
}

export function ElevationRibbon({
  samples,
  currentMile,
  upcomingClimb,
  subject = 'ahead',
  units = 'imperial',
  domain,
}: ElevationRibbonProps) {
  const startMile = domain?.startMile ?? samples[0]?.mile ?? 0
  const endMile = domain?.endMile ?? samples[samples.length - 1]?.mile ?? 0

  const elevations = samples.map((s) => s.elevationFt)
  const minFt = Math.min(...elevations)
  const maxFt = Math.max(...elevations)

  // A flat window makes max === min. Dividing by that range would put NaN into
  // the path, which renders as nothing at all - so a flat profile is drawn as
  // a flat line down the middle instead.
  const range = maxFt - minFt
  const yFor = (ft: number) =>
    range === 0 ? VIEW_H / 2 : VIEW_H - ((ft - minFt) / range) * VIEW_H

  const pointsPath = samples
    .map((s, i) => {
      const x = pctAlong(s.mile, startMile, endMile)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${yFor(s.elevationFt).toFixed(2)}`
    })
    .join(' ')

  // Closing back along the baseline is what makes this a shaded area rather
  // than a bare line. It closes under the LINE's own ends rather than under
  // the ribbon's: with no domain given those are the same two x values, and
  // where a domain leaves the samples short of an edge, shading out to it
  // would fill ground the DEM never covered.
  const firstX = samples.length === 0 ? 0 : pctAlong(samples[0].mile, startMile, endMile)
  const lastX =
    samples.length === 0
      ? VIEW_W
      : pctAlong(samples[samples.length - 1].mile, startMile, endMile)
  const areaPath = `${pointsPath} L${lastX.toFixed(2)},${VIEW_H} L${firstX.toFixed(2)},${VIEW_H} Z`

  // Only where the fix genuinely falls inside what is drawn. Outside it the
  // rule would be clamped to an edge by the SVG viewport and read as "you are
  // at the start of this stretch", which is the confident-looking wrong
  // answer CLAUDE.md's four-ways section rules out.
  const herePct =
    currentMile === null || currentMile < startMile || currentMile > endMile
      ? null
      : pctAlong(currentMile, startMile, endMile)

  return (
    <div className="elevation-ribbon">
      <div className="elevation-ribbon__labels">
        <span className="elevation-ribbon__max">{formatElevation(maxFt, units)}</span>
        <span className="elevation-ribbon__min">{formatElevation(minFt, units)}</span>
      </div>

      <svg
        className="elevation-ribbon__svg"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={
          subject === 'ahead'
            ? 'Elevation profile ahead'
            : 'Elevation profile of the stretch being planned'
        }
      >
        {upcomingClimb && (
          <rect
            data-testid="upcoming-climb"
            x={pctAlong(upcomingClimb.startMile, startMile, endMile)}
            y={0}
            width={
              pctAlong(upcomingClimb.endMile, startMile, endMile) -
              pctAlong(upcomingClimb.startMile, startMile, endMile)
            }
            height={VIEW_H}
            className="elevation-ribbon__climb"
          />
        )}

        <path
          data-testid="profile-area"
          d={areaPath}
          className="elevation-ribbon__area"
        />
        <path d={pointsPath} className="elevation-ribbon__line" fill="none" />

        {herePct !== null && (
          <line
            data-testid="you-are-here"
            x1={herePct}
            x2={herePct}
            y1={0}
            y2={VIEW_H}
            className="elevation-ribbon__here"
          />
        )}
      </svg>

      {upcomingClimb && (
        <p data-testid="climb-callout" className="elevation-ribbon__callout">
          {`+${formatElevation(upcomingClimb.ascentFt, units)} · ${formatDistance(
            upcomingClimb.endMile - upcomingClimb.startMile,
            units,
          )} · ${naismithTime({
            distanceMi: upcomingClimb.endMile - upcomingClimb.startMile,
            ascentFt: upcomingClimb.ascentFt,
          })}`}
        </p>
      )}
    </div>
  )
}
