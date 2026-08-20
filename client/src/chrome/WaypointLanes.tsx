// The three waypoint lanes under the elevation ribbon (WIREFRAMES.md §1.4).
//
// Positions are percentages in the same 0-100 space the ribbon's SVG uses, so
// a pin at 60% sits directly under the part of the profile it belongs to.
// Clustering lives in lib/waypointLanes.ts.
//
// AND TAPPING ONE OPENS IT (§4 of #527). These were `<button>`s with no
// `onClick` from the day they were built - markup that offers a press, a focus
// ring and a pointer cursor to something that does nothing. WIREFRAMES.md §1.4
// describes the count pill as a control; it had never been one.
//
// `onSelectPoi` is REQUIRED rather than optional, which is the part worth
// stating. An optional handler would let the inert rendering back in silently -
// a caller that forgets it gets the exact defect this fixes, and gets it with a
// green typecheck. Required, the compiler is what stops that recurring.

import { LANES, clusterWaypoints, type Waypoint } from '../lib/waypointLanes'
import type { StalenessTreatment } from '../lib/stalenessDisplay'
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
  /**
   * Open a waypoint's card, by id - the same handler a tap on the map's own pin
   * goes through, so the ribbon and the canvas open the same card rather than
   * two that can drift.
   *
   * A PILL OPENS ITS FIRST MEMBER, which is the one its glyph already shows
   * (`WaypointCluster.type` is `members[0].type`). So what the pill looks like
   * and what it opens are the same waypoint, rather than the pill showing a
   * spring and opening the shelter behind it.
   *
   * What that does NOT reach, said plainly: a pill collapsing two waypoints
   * that are not parts of one place - two shelters a tenth of a mile apart -
   * opens the first and leaves the second reachable only by zooming the ribbon
   * in. Where the members ARE one site the card covers them all, because its
   * chip strip lists the whole site (#526), and features/POI_SITES.md measured
   * co-location as the dominant case: a privy sits a median 42 m from its
   * shelter. So the gap is real and is the minority; closing it would mean a
   * pill opening a list, which is a bigger thing than #527 §4 asks for.
   */
  onSelectPoi: (id: string) => void
  /**
   * What the field has said about a waypoint, for the lane's own copy of the
   * tier styling (#759's second surface - "the highest-value surface of the
   * four, and it costs a `match` expression because the lane is already
   * drawn"). lib/stalenessDisplay.ts's `stalenessPresentation`, partially
   * applied by the shell over the note roll-up; null for a type outside the
   * nudge scope. Absent means notes are not wired - the lanes render exactly
   * as they always have.
   *
   * Applied to LONE pins only. A pill stands for several waypoints whose
   * tiers can disagree, and a ring that means "the first one" while looking
   * like "all of them" is the kind of half-claim this app does not draw.
   */
  stalenessFor?: (
    poiId: string,
    poiType: string,
  ) => { treatment: StalenessTreatment; words: string } | null
}

/** The ring names a lane pin can wear, as CSS modifiers. Only the states a
 *  visible treatment exists for - `none` at full opacity adds no class, so a
 *  neutral pin's markup is byte-identical to what it was before notes. */
function conditionClass(treatment: StalenessTreatment): string {
  const ring =
    treatment.ring === 'green'
      ? ' waypoint-pin--fresh'
      : treatment.ring === 'grey-dotted'
        ? ' waypoint-pin--stale'
        : treatment.ring === 'faint-invite'
          ? ' waypoint-pin--no-word'
          : ''
  return `${ring}${treatment.opacity < 1 ? ' waypoint-pin--faded' : ''}`
}

export function WaypointLanes({
  points,
  startMile,
  endMile,
  onSelectPoi,
  stalenessFor,
}: WaypointLanesProps) {
  const lanes = clusterWaypoints(points, { startMile, endMile })

  return (
    <div className="waypoint-lanes">
      {LANES.map((lane) => (
        <div key={lane.id} className="waypoint-lane" data-testid={`lane-${lane.id}`}>
          <span className="waypoint-lane__label">{lane.label}</span>

          <div className="waypoint-lane__track">
            {lanes[lane.id].map((cluster) => {
              const name = typeLabel(cluster.type)
              // Lone pins only - see the prop's own note on pills.
              const presentation =
                cluster.count === 1 && stalenessFor !== undefined
                  ? stalenessFor(cluster.members[0].id, cluster.type)
                  : null
              const condition =
                presentation === null ? '' : conditionClass(presentation.treatment)
              // The words ride only where the pixels do (WIREFRAMES.md §11's
              // channel rule, both halves): a visibly-ringed or faded pin
              // says why, and a neutral one stays quiet rather than reading
              // "never confirmed" over every pin on the ribbon.
              const spoken =
                presentation !== null && condition !== ''
                  ? `${name} — ${presentation.words}`
                  : name
              // A pill says how many it stands for; a lone pin just names
              // itself, so "1" never appears as noise next to every glyph.
              const accessibleName =
                cluster.count > 1 ? `${cluster.count} ${name}` : spoken

              return (
                <button
                  key={cluster.members[0].id}
                  type="button"
                  className={`waypoint-pin${condition}`}
                  style={{ left: `${cluster.positionPct}%` }}
                  onClick={() => onSelectPoi(cluster.members[0].id)}
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
