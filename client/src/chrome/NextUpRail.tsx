// The next-up rail (#1054): the phone's strip of coming waypoints, replacing
// the three waypoint lanes.
//
// The lanes positioned pins by percentage under the ribbon's profile; the
// rail is the same data walked instead of plotted - one card per waypoint,
// in the order the hiker will meet them, horizontally scrollable. What the
// lanes were careful about, this stays careful about:
//
//  - `onSelectPoi` is REQUIRED, the lanes' own defence (#527): an optional
//    handler would let an inert rendering back in with a green typecheck.
//    A card opens the same waypoint card a map pin does.
//  - The heading follows the ribbon's subject the way its aria-label does:
//    "NEXT UP" is a claim about which way somebody is walking, and it is
//    only printed for the fix window with a settled direction. Anything
//    else gets the honest word for what it is.
//  - An unknown POI type still gets a card (fallback glyph and colour,
//    map/poiIcons.ts) - a later import must not vanish from the rail.
//  - Staleness words ride only where the pixels do (WIREFRAMES.md §11):
//    the treatments come from the one policy home (lib/stalenessDisplay.ts).
//  - Cards are border-box. The prototype shipped content-box cards that
//    overflowed their own rail, and that bug is the reason the rule is
//    stated in the stylesheet as well as here.

import type { HikeDirection } from './Header'
import type { RibbonSubject } from './ElevationRibbon'
import type { StalenessTreatment } from '../lib/stalenessDisplay'
import type { Waypoint } from '../lib/ribbonView'
import { poiColor, poiGlyphPath } from '../map/poiIcons'
import { typeLabel } from './legendLabels'
import { formatDistance, type UnitSystem } from '../lib/units'

/**
 * One swipe's worth of cards. The rail is "what is coming", not the whole
 * window - a map-view domain can hold hundreds of waypoints, and a rail that
 * long is a worse index than the map it sits under. The heading says when
 * the list was cut, so a shortened rail never reads as a short trail.
 *
 * @unvalidated 12 is picked, not measured. What would settle it: how far
 * along the rail hikers actually swipe.
 */
export const RAIL_MAX_CARDS = 12

/** The honest word for what the cards stand for - the ribbon's own subject
 *  discipline (ElevationRibbon's SUBJECT_LABELS), one surface over. "NEXT UP"
 *  without a settled direction would be a coin flip printed as a claim. */
export function railHeading(
  subject: RibbonSubject,
  direction: HikeDirection | undefined,
): string {
  if (subject === 'ahead') return direction === undefined ? 'NEARBY' : 'NEXT UP'
  if (subject === 'planned-stretch') return 'ON THIS STRETCH'
  if (subject === 'map-view') return 'IN VIEW'
  return 'ON THE TRAIL'
}

export interface NextUpRailProps {
  points: readonly Waypoint[]
  subject: RibbonSubject
  /** The fix's mile on the points' own axis, or null - decides whether a
   *  card may say how far away it is. */
  currentMile: number | null
  direction?: HikeDirection
  /** Required - see the header. */
  onSelectPoi: (id: string) => void
  /** Feet-and-miles or metric, through lib/units.ts like every distance a
   *  hiker reads. The mile-marker fallback below stays a mile whatever this
   *  says - markers are signage, not measurement (screens/Volunteer.tsx's
   *  own stance). */
  units?: UnitSystem
  stalenessFor?: (
    poiId: string,
    poiType: string,
  ) => { treatment: StalenessTreatment; words: string } | null
}

/** The same modifier ladder the lane pins wore, at card scale - policy from
 *  lib/stalenessDisplay.ts, never a fourth copy of the tiers. */
function conditionClass(treatment: StalenessTreatment): string {
  const ring =
    treatment.ring === 'green'
      ? ' next-up__card--fresh'
      : treatment.ring === 'grey-dotted'
        ? ' next-up__card--stale'
        : treatment.ring === 'faint-invite'
          ? ' next-up__card--no-word'
          : ''
  return `${ring}${treatment.opacity < 1 ? ' next-up__card--faded' : ''}`
}

export function NextUpRail({
  points,
  subject,
  currentMile,
  direction,
  onSelectPoi,
  units = 'imperial',
  stalenessFor,
}: NextUpRailProps) {
  const heading = railHeading(subject, direction)

  // Walk order. NEXT UP means ahead of the fix in the settled direction;
  // NEARBY means nearest first in either direction; everything else reads
  // the domain south-to-north, which is the order its miles already carry.
  const ordered = (() => {
    if (subject === 'ahead' && currentMile !== null) {
      if (direction === 'NOBO') {
        return points
          .filter((point) => point.mile >= currentMile)
          .sort((a, b) => a.mile - b.mile)
      }
      if (direction === 'SOBO') {
        return points
          .filter((point) => point.mile <= currentMile)
          .sort((a, b) => b.mile - a.mile)
      }
      return [...points].sort(
        (a, b) => Math.abs(a.mile - currentMile) - Math.abs(b.mile - currentMile),
      )
    }
    return [...points].sort((a, b) => a.mile - b.mile)
  })()

  const shown = ordered.slice(0, RAIL_MAX_CARDS)

  return (
    <div className="next-up">
      <div className="next-up__rule">
        <span className="next-up__label">{heading}</span>
        {/* Said only when the rail was cut, so a shortened rail never reads
            as a short trail - the dropped-count's own honesty (#528). */}
        {ordered.length > shown.length && (
          <span className="next-up__count">
            {shown.length} of {ordered.length}
          </span>
        )}
      </div>

      {shown.length > 0 && (
        <div className="next-up__cards" data-testid="next-up-cards">
          {shown.map((point) => {
            const presentation =
              stalenessFor === undefined ? null : stalenessFor(point.id, point.type)
            const condition =
              presentation === null ? '' : conditionClass(presentation.treatment)
            const name = point.name ?? typeLabel(point.type)
            // The words ride only where the pixels do: a visibly-marked card
            // says why, a neutral one stays quiet.
            const spoken =
              presentation !== null && condition !== ''
                ? `${name} — ${presentation.words}`
                : name
            const meta =
              currentMile === null
                ? `${typeLabel(point.type).toLowerCase()} · mi ${point.mile.toLocaleString(
                    'en-US',
                    { minimumFractionDigits: 1, maximumFractionDigits: 1 },
                  )}`
                : `${typeLabel(point.type).toLowerCase()} · ${formatDistance(
                    Math.abs(point.mile - currentMile),
                    units,
                  )}`
            return (
              <button
                key={point.id}
                type="button"
                className={`next-up__card${condition}${
                  point.type === 'closure' || point.type === 'serious-warning'
                    ? ' next-up__card--danger'
                    : ''
                }`}
                onClick={() => onSelectPoi(point.id)}
              >
                <span className="visually-hidden">{spoken}</span>
                <span aria-hidden="true" className="next-up__card-body">
                  <span
                    className="next-up__chip"
                    style={
                      { '--chip-accent': poiColor(point.type) } as React.CSSProperties
                    }
                  >
                    <svg viewBox="0 0 1 1" focusable="false">
                      <path d={poiGlyphPath(point.type)} fillRule="evenodd" />
                    </svg>
                  </span>
                  <span className="next-up__card-name">{name}</span>
                  <span className="next-up__card-meta">{meta}</span>
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
