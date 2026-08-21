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

/** Written out one per line, so each has to be read as the claim it is. */
const SUBJECT_LABELS: Record<RibbonSubject, string> = {
  ahead: 'Elevation profile ahead',
  'planned-stretch': 'Elevation profile of the stretch being planned',
  'map-view': 'Elevation profile of the trail shown on the map',
  'whole-trail': 'Elevation profile of the whole trail',
}

export interface ElevationSample {
  mile: number
  elevationFt: number
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
export type RibbonSubject = 'ahead' | 'planned-stretch' | 'map-view' | 'whole-trail'

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

function pctAlong(mile: number, startMile: number, endMile: number): number {
  const span = endMile - startMile
  return span === 0 ? 0 : ((mile - startMile) / span) * 100
}

export function ElevationRibbon({
  samples,
  currentMile,
  upcomingClimb,
  subject = 'ahead',
  controls,
  units = 'imperial',
}: ElevationRibbonProps) {
  const startMile = samples[0]?.mile ?? 0
  const endMile = samples[samples.length - 1]?.mile ?? 0

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
  // than a bare line.
  const areaPath = `${pointsPath} L${VIEW_W},${VIEW_H} L0,${VIEW_H} Z`

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
