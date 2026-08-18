// The hike zoom (#790): a hike's trips and its gaps, in trail order, under
// a ribbon of the whole thing.
//
// The outermost of the Plan tab's three depths, and features/SEGMENTS.md's
// tree rendered as a screen rather than as a second model: a Hike holds
// trips, a trip holds days, and the control at the top is which of those
// you are looking at.
//
// THE GAPS ARE ROWS HERE, not a feature. A zoom that lists a hike's pieces
// while silently omitting the unwalked ones would be a list of achievements
// - which is exactly what this project has decided a plan must not become.
// Naming what is left, and what its ends are called, is the honest version;
// **#791 — What's left: the gaps, both of their ends, and which piece fits
// the days you actually have** is the screen that helps a hiker choose
// between them, and none of that guidance is here.
//
// ROW HEIGHT IS DAYS, the day timeline's hours-encoding one zoom out
// (lib/planDisplay.ts's tripRowHeight) - so a long summer reads long before
// a single number has been read.

import { useEffect, useRef, useState } from 'react'
import {
  hikeBounds,
  hikeFigures,
  hikePieces,
  type Hike,
  type HikePiece,
  type PlaceRef,
} from '../lib/hikes'
import { planDayViews } from '../lib/plan'
import { dayDateLabel, stopLabel, tripRowHeight } from '../lib/planDisplay'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'
import { formatDistance, type UnitSystem } from '../lib/units'
import { TrailRibbon } from './TrailRibbon'
import './plan.css'

export interface HikeZoomProps {
  hike: Hike
  /** Every kept trip; the hike picks its own out by id. */
  trips: readonly Trip[]
  pois: readonly StoredPoi[]
  units: UnitSystem
  /** Where the hiker is on the pipeline's mile axis, or null - the ribbon's
   *  marker, and nothing else on this screen. */
  gpsMile: number | null
  openTripId: string | null
  onOpenTrip: (id: string) => void
  /** Start planning a stretch nobody has walked yet. The whole gap is
   *  handed over, ends and all, so the route builder opens on the place the
   *  row named rather than on a mile it has to recognise again. */
  onPlanGap: (gap: Extract<HikePiece, { kind: 'gap' }>) => void
  /** Open "What's left" (#791) - the screen that helps choose between the
   *  gaps rather than only listing them. Offered when there is at least one
   *  to choose from. */
  onWhatsLeft: () => void
}

export function HikeZoom({
  hike,
  trips,
  pois,
  units,
  gpsMile,
  openTripId,
  onOpenTrip,
  onPlanGap,
  onWhatsLeft,
}: HikeZoomProps) {
  const pieces = hikePieces(hike, trips, pois)
  const figures = hikeFigures(hike, trips, pois)
  const bounds = hikeBounds(hike, pois)
  const gapCount = pieces.filter((piece) => piece.kind === 'gap').length

  // The ribbon scrubs the rows: a tapped band brings its row into view and
  // marks it. State rather than an anchor because the piece list is derived
  // and its ids are not addresses.
  const [picked, setPicked] = useState<string | null>(null)
  const rows = useRef(new Map<string, HTMLLIElement>())

  useEffect(() => {
    if (picked === null) return
    const row = rows.current.get(picked)
    // jsdom has no layout and no scrollIntoView; a scrubber that throws in
    // a test would be worse than one that does not scroll in one.
    if (row !== undefined && typeof row.scrollIntoView === 'function') {
      row.scrollIntoView({ block: 'center' })
    }
  }, [picked])

  return (
    <div className="hike-zoom">
      <TrailRibbon
        pieces={pieces}
        bounds={bounds}
        startLabel={endLabel(hike.start.name, bounds.from)}
        endLabel={endLabel(hike.end.name, bounds.to)}
        figures={`${formatDistance(figures.walkedMi, units)} walked · ${formatDistance(
          figures.leftMi,
          units,
        )} to go`}
        hereMile={gpsMile}
        onPick={setPicked}
        pickedId={picked}
      />

      {figures.uncertain && (
        <p className="hike-zoom__note" role="note">
          One end of this hike points at a place this download doesn&rsquo;t have, so
          these figures rest on the mile it had when you set it.
        </p>
      )}

      <ol className="hike-zoom__pieces">
        {pieces.map((piece) => (
          <li
            key={piece.id}
            ref={(node) => {
              if (node === null) rows.current.delete(piece.id)
              else rows.current.set(piece.id, node)
            }}
            className={
              piece.id === picked
                ? 'hike-zoom__row hike-zoom__row--picked'
                : 'hike-zoom__row'
            }
          >
            {piece.kind === 'trip' ? (
              <TripRow
                piece={piece}
                units={units}
                open={piece.trip.id === openTripId}
                onOpen={() => onOpenTrip(piece.trip.id)}
              />
            ) : (
              <GapRow piece={piece} units={units} onPlan={() => onPlanGap(piece)} />
            )}
          </li>
        ))}
      </ol>

      {pieces.length === 0 && (
        <p className="hike-zoom__empty">
          Nothing in this hike yet. A trip joins it the moment you group it in.
        </p>
      )}

      {gapCount > 0 && (
        <button type="button" className="hike-zoom__whats-left" onClick={onWhatsLeft}>
          What&rsquo;s left — {gapCount} {gapCount === 1 ? 'piece' : 'pieces'}
        </button>
      )}
    </div>
  )
}

/** A gap end by the name the hike knows it by, or by its mile marker -
 *  the timeline's own rule for a stop, so one place cannot be called two
 *  things on two zooms. */
function placeLabel(ref: PlaceRef): string {
  return stopLabel({
    mile: ref.mile,
    ...(ref.name === undefined ? {} : { name: ref.name }),
  })
}

/** A hike end's own name, or the mile marker it sits at. */
function endLabel(name: string | undefined, mile: number): string {
  if (name !== undefined && name !== '') return name
  return `mi ${mile.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

function TripRow({
  piece,
  units,
  open,
  onOpen,
}: {
  piece: Extract<HikePiece, { kind: 'trip' }>
  units: UnitSystem
  open: boolean
  onOpen: () => void
}) {
  const views = planDayViews(piece.trip.plan)
  const recorded = piece.trip.recorded === true
  const dates = views
    .map((day) => day.date)
    .filter((date): date is string => date !== null)

  return (
    <button
      type="button"
      className={`hike-zoom__trip hike-zoom__trip--${piece.state}`}
      // A recorded stretch's "days" are the boundaries a hiker could
      // remember years later (#789), never days anybody walked as days - so
      // it gets no height off them either, not just no printed count.
      style={{ height: `${tripRowHeight(recorded ? 0 : views.length)}px` }}
      onClick={onOpen}
    >
      <span className="hike-zoom__trip-top">
        <span className="hike-zoom__trip-name">{piece.trip.name}</span>
        <span className="hike-zoom__badge">{stateLabel(piece, recorded)}</span>
      </span>
      <span className="hike-zoom__trip-figures">
        {formatDistance(piece.span.to - piece.span.from, units)}
        {!recorded && ` · ${views.length} ${views.length === 1 ? 'day' : 'days'}`}
        {dates.length > 0 && ` · from ${dayDateLabel(dates[0])}`}
        {open && ' · open'}
      </span>
    </button>
  )
}

function stateLabel(
  piece: Extract<HikePiece, { kind: 'trip' }>,
  recorded: boolean,
): string {
  if (recorded) return 'recorded'
  if (piece.state === 'walked') return 'walked'
  if (piece.state === 'part') return 'part walked'
  return 'planned'
}

/**
 * A stretch of this hike nobody has walked.
 *
 * Named by both ends rather than by its length alone, because "554.2 mi not
 * walked" is a number and "Damascus → Harpers Ferry" is a piece of trail
 * somebody can decide about. The ends are the places the hike already knows
 * (lib/hikes.ts's nameAtMile) - what a hiker could actually get to at
 * either end is #791's question, and this row does not pretend to answer it.
 */
function GapRow({
  piece,
  units,
  onPlan,
}: {
  piece: Extract<HikePiece, { kind: 'gap' }>
  units: UnitSystem
  onPlan: () => void
}) {
  return (
    <div className="hike-zoom__gap">
      <span className="hike-zoom__gap-top">
        <span className="hike-zoom__gap-figure">
          {formatDistance(piece.span.to - piece.span.from, units)} not walked
        </span>
        <span className="hike-zoom__badge hike-zoom__badge--gap">gap</span>
      </span>
      <span className="hike-zoom__gap-ends">
        {placeLabel(piece.from)} → {placeLabel(piece.to)}
      </span>
      <button type="button" className="hike-zoom__gap-plan" onClick={onPlan}>
        Plan this stretch
      </button>
    </div>
  )
}
