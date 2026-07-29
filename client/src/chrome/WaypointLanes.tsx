// The three waypoint lanes under the elevation ribbon (WIREFRAMES.md §1.4).
//
// Positions are percentages in the same 0-100 space the ribbon's SVG uses, so
// a pin at 60% sits directly under the part of the profile it belongs to.
// Clustering lives in lib/waypointLanes.ts.

import { LANES, clusterWaypoints, type Waypoint } from '../lib/waypointLanes'
import { typeLabel } from './legendLabels'

const GLYPHS: Record<string, string> = {
  water: '💧',
  shelter: '⌂',
  campsite: '△',
  resupply: '⬢',
  town: '▣',
  parking: 'P',
  crossing: '≈',
  closure: '⊘',
  'serious-warning': '⚠',
}

export interface WaypointLanesProps {
  points: Waypoint[]
  startMile: number
  endMile: number
}

export function WaypointLanes({ points, startMile, endMile }: WaypointLanesProps) {
  const lanes = clusterWaypoints(points, { startMile, endMile })

  return (
    <div className="waypoint-lanes">
      {LANES.map((lane) => (
        <div key={lane.id} className="waypoint-lane" data-testid={`lane-${lane.id}`}>
          <span className="waypoint-lane__label">{lane.label}</span>

          <div className="waypoint-lane__track">
            {lanes[lane.id].map((cluster) => {
              const name = typeLabel(cluster.type)
              // A pill says how many it stands for; a lone pin just names
              // itself, so "1" never appears as noise next to every glyph.
              const accessibleName = cluster.count > 1 ? `${cluster.count} ${name}` : name

              return (
                <button
                  key={cluster.members[0].id}
                  type="button"
                  className="waypoint-pin"
                  style={{ left: `${cluster.positionPct}%` }}
                >
                  <span className="visually-hidden">{accessibleName}</span>
                  <span aria-hidden="true" className="waypoint-pin__glyph">
                    {GLYPHS[cluster.type] ?? '•'}
                  </span>
                  {cluster.count > 1 && (
                    <span aria-hidden="true" className="waypoint-pin__count">
                      {cluster.count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
