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

import { naismithTime } from '../lib/naismith'

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
  currentMile: number
  upcomingClimb?: UpcomingClimb
}

function pctAlong(mile: number, startMile: number, endMile: number): number {
  const span = endMile - startMile
  return span === 0 ? 0 : ((mile - startMile) / span) * 100
}

export function ElevationRibbon({
  samples,
  currentMile,
  upcomingClimb,
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

  const herePct = pctAlong(currentMile, startMile, endMile)

  return (
    <div className="elevation-ribbon">
      <div className="elevation-ribbon__labels">
        <span className="elevation-ribbon__max">{maxFt.toLocaleString('en-US')} ft</span>
        <span className="elevation-ribbon__min">{minFt.toLocaleString('en-US')} ft</span>
      </div>

      <svg
        className="elevation-ribbon__svg"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Elevation profile ahead"
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

        <line
          data-testid="you-are-here"
          x1={herePct}
          x2={herePct}
          y1={0}
          y2={VIEW_H}
          className="elevation-ribbon__here"
        />
      </svg>

      {upcomingClimb && (
        <p data-testid="climb-callout" className="elevation-ribbon__callout">
          {`+${upcomingClimb.ascentFt.toLocaleString('en-US')} ft · ${(
            upcomingClimb.endMile - upcomingClimb.startMile
          ).toFixed(1)} mi · ${naismithTime({
            distanceMi: upcomingClimb.endMile - upcomingClimb.startMile,
            ascentFt: upcomingClimb.ascentFt,
          })}`}
        </p>
      )}
    </div>
  )
}
