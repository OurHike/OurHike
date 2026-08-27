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

import { useMemo } from 'react'
import { naismithTime } from '../lib/naismith'
import { pctAlong, ribbonGeometry, VIEW_H, VIEW_W } from '../lib/ribbonGeometry'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'

/** Written out one per line, so each has to be read as the claim it is. */
const SUBJECT_LABELS: Record<RibbonSubject, string> = {
  ahead: 'Elevation profile ahead',
  'todays-walk': 'Elevation profile of your whole walk today',
  'planned-stretch': 'Elevation profile of the stretch being planned',
  'map-view': 'Elevation profile of the trail shown on the map',
  'whole-trail': 'Elevation profile of the whole trail',
}

export interface ElevationSample {
  mile: number
  elevationFt: number
  /**
   * The first sample after ground this ribbon has no shape for, so the drawn
   * line BREAKS here instead of sloping across it.
   *
   * The name and the convention are `lib/elevationGain.ts`'s `ProfileSample.
   * partStart`, deliberately, rather than a second marker meaning the same
   * thing: that field already tells `cumulativeGainOverProfile` where a seam
   * in the trail is rather than a slope, and `pipeline/export_network_profile.
   * py` names both sides of the language boundary as the documented way to
   * flatten a route without inventing climb across a join.
   *
   * WHAT IT MARKS HERE IS A STRETCH BOUNDARY, NOT AN EDGE BOUNDARY, and the
   * difference is the whole reason this is safe to draw at all. A day hike
   * built from several stretches (#983) has ground between them that OurHike
   * will not route - a road walk, most often - and a line sloping across it
   * would be a picture of terrain nobody measured. A junction between two
   * edges INSIDE a stretch is not marked: this ribbon prices nothing, so the
   * vertical step an endpoint weld can leave (up to 19.06 m of horizontal
   * separation, measured by export_network_profile.py) is a step in a drawing
   * rather than climbing in a total, and it is sub-pixel on a 54 px band. A
   * route crosses a median 23 of those junctions, so marking them all would
   * render the ribbon as dots.
   */
  partStart?: boolean
}

export interface UpcomingClimb {
  startMile: number
  endMile: number
  ascentFt: number
}

/**
 * What the ribbon is drawing, which is the one thing that changes its
 * accessible name. lib/ribbonView.ts decides which, and its `source` IS this
 * type - one value, not a field here and a field there that can drift apart.
 */
export type RibbonSubject =
  'ahead' | 'todays-walk' | 'planned-stretch' | 'map-view' | 'whole-trail'

/** One map-framing button under the ribbon (#910 review). The screen decides
 *  WHICH exist - they depend on what the ribbon is currently showing - so this
 *  component only draws what it is handed. */
export interface RibbonControl {
  label: string
  onClick: () => void
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
   * What this ribbon is a picture of, which changes only its accessible name -
   * and has to, because every one of these is a different claim and "ahead" is
   * the strongest of them. A screen reader saying "ahead" over the whole trail
   * has told a hiker something false about where they are going.
   *
   * The same union lib/ribbonView.ts resolves, rather than a second opinion
   * about it.
   */
  subject?: RibbonSubject
  /**
   * The stretch of trail this ribbon's full width stands for - what x=0 and
   * x=100 mean. Defaults to the first and last sample, which is what it has
   * always been and is right whenever the samples reach both edges.
   *
   * Worth being able to say otherwise, because the waypoint lanes underneath
   * are positioned in this same 0-100 space by whoever supplies them, and the
   * two line up only while they agree about which ground the width covers.
   * They can disagree by a sample spacing at each end - the profile is sampled
   * every 25 m and a domain's edge falls where it falls - which is enough to
   * push the shelter at the end of a planned stretch off the end of its lane.
   * With a domain given, the samples are drawn at their real fraction of it: a
   * domain whose DEM coverage starts late draws a line that starts late,
   * rather than one stretched to fill ground it never measured.
   *
   * `lib/ribbonView.ts` already carries this per domain, so MapScreen's
   * spread of a `RibbonView` supplies it for all four.
   */
  domain?: { startMile: number; endMile: number }
  /**
   * Buttons that frame this ribbon's ground on the map - the desktop chart's
   * "Zoom to stretch" and "Whole trail", which the maintainer asked for here
   * too, plus the way back to the hiker once they have panned away.
   *
   * Their own row UNDER the 54px block rather than floating over the profile,
   * and that is the trade worth naming: a row costs the map about 44px while
   * any button exists, and overlaying instead would cost either the terrain
   * the ribbon exists to show or the touch target a gloved hand in sunlight
   * needs (#105). Height is something a maintainer can decide to spend
   * differently; a mis-tap on a mountain is not.
   */
  controls?: readonly RibbonControl[]
  /** Which units the three labels read in. Defaulted rather than required, so
   *  a ribbon rendered outside the shell still says something true - and
   *  defaulted to the same value lib/userPreferences.ts does, so the default
   *  is the preference's default rather than a second opinion about it. */
  units?: UnitSystem
}

export function ElevationRibbon({
  samples,
  currentMile,
  upcomingClimb,
  subject = 'ahead',
  controls,
  units = 'imperial',
  domain,
}: ElevationRibbonProps) {
  const startMile = domain?.startMile ?? samples[0]?.mile ?? 0
  const endMile = domain?.endMile ?? samples[samples.length - 1]?.mile ?? 0

  // The one expensive part of this render - the min/max scan and the two
  // ~640-point path strings (lib/ribbonGeometry.ts). Memoized because the
  // shell re-renders once per GPS callback while a phone sits still (#1100),
  // reaching here with these three props unchanged (#1111): the mile rule and
  // the labels may move without the drawn ground changing, and the ground is
  // all this computes.
  const { minFt, maxFt, pointsPath, areaPath } = useMemo(
    () => ribbonGeometry(samples, startMile, endMile),
    [samples, startMile, endMile],
  )

  // Only where the fix genuinely falls inside what is drawn. Outside it the
  // rule would be clamped to an edge by the SVG viewport and read as "you are
  // at the start of this stretch", which is the confident-looking wrong
  // answer CLAUDE.md's four-ways section rules out.
  const herePct =
    currentMile === null || currentMile < startMile || currentMile > endMile
      ? null
      : pctAlong(currentMile, startMile, endMile)

  return (
    <>
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
          aria-label={SUBJECT_LABELS[subject]}
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

      {controls !== undefined && controls.length > 0 && (
        <div className="elevation-ribbon-controls">
          {controls.map((control) => (
            <button
              key={control.label}
              type="button"
              className="elevation-ribbon-controls__button"
              onClick={control.onClick}
            >
              {control.label}
            </button>
          ))}
        </div>
      )}
    </>
  )
}
