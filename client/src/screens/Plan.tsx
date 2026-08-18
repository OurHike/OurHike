// The Plan tab (#756): the multi-day plan as a timeline of terrain rows -
// wireframe 1b, the treatment marked CHOSEN, at phone width.
//
// The one physical encoding: ROW HEIGHT = WALKING HOURS
// (lib/planDisplay.ts), so a hard day is bigger on the screen and a
// section's shape can be felt by scrolling it. Each walking row carries its
// own slice of the published elevation profile, drawn with the elevation
// ribbon's geometry - and, like the ribbon, normalised to its own window:
// the silhouette is shape, the printed figures are the numbers.
//
// WHAT IS DELIBERATELY NOT HERE, because this surface is where it would
// arrive uninvited (V2_PLAN.md group T's standing trap): no progress bar,
// no "behind schedule", no comparison of any day against the plan, no
// score. "Was 17.1 mi" territory belongs to the cascade (#758) and even
// there it is a fact about the plan, not a verdict on the hiker. A zero
// says "no walking" - terrain, not judgement.
//
// A SCREEN, NOT A DIALOG - it replaces the map when its tab is active, so
// there is nothing behind it to dim (HikePicker.tsx's convention). The two
// sheets it hosts (a tapped day's actions, the target sheet the shell
// passes in) dock to the screen's own bottom edge.

import { useMemo, useState, type ReactNode } from 'react'
import { ribbonSamples, type ElevationProfile } from '../lib/elevationProfile'
import { formatNaismithMinutes } from '../lib/naismith'
import {
  planDayViews,
  planSections,
  planDirection,
  type HikePlan,
  type PlanDayView,
  type PlanSection,
} from '../lib/plan'
import { dayDateLabel, dayRowHeight, MIN_ROW_PX, stopLabel } from '../lib/planDisplay'
import { legFigures, type LegFigures } from '../lib/route'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'
import './plan.css'

export interface PlanScreenProps {
  plan: HikePlan | null
  /** The published profile, for row heights and terrain slices. Null - an
   *  old download - drops the terrain and the hour-proportional heights
   *  rather than faking either. */
  elevation: ElevationProfile | null
  units: UnitSystem
  /** Open the route builder on the map - the empty state's one action. */
  onStartOnMap: () => void
  /** Reopen the target sheet over this plan's route. */
  onChangeTarget: () => void
  onInsertZeroAfter: (dayIndex: number) => void
  onRemoveDay: (dayIndex: number) => void
  onTogglePinned: (dayIndex: number) => void
  /** Flip resupply on the stop day `dayIndex` ends at. */
  onToggleEndResupply: (dayIndex: number) => void
  onDeletePlan: () => void
  /** The target sheet, when the shell has it open over this screen. */
  targetSheet?: ReactNode
}

export function PlanScreen({
  plan,
  elevation,
  units,
  onStartOnMap,
  onChangeTarget,
  onInsertZeroAfter,
  onRemoveDay,
  onTogglePinned,
  onToggleEndResupply,
  onDeletePlan,
  targetSheet,
}: PlanScreenProps) {
  const [selectedDay, setSelectedDay] = useState<number | null>(null)
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const views = useMemo(() => (plan === null ? [] : planDayViews(plan)), [plan])
  const sections = useMemo(() => planSections(views), [views])

  // One figures pass for every walking day - heights, terrain and labels all
  // read from it, so they cannot disagree about what a day costs.
  const figures = useMemo(() => {
    const byIndex = new Map<number, LegFigures>()
    if (elevation === null) return byIndex
    for (const day of views) {
      if (!day.zero) {
        byIndex.set(day.index, legFigures(elevation, day.start.mile, day.end.mile))
      }
    }
    return byIndex
  }, [views, elevation])

  if (plan === null || views.length === 0) {
    return (
      <div className="plan">
        <header className="plan__head">
          <h1 className="plan__title">Plan</h1>
          <span className="plan__head-note">nothing saved</span>
        </header>

        <div className="plan__empty">
          {/* Three blazes, decoration only - the app's own voice lives in
              the words beside them. */}
          <div className="plan__blazes" aria-hidden="true">
            <span className="plan__blaze plan__blaze--white" />
            <span className="plan__blaze plan__blaze--orange" />
            <span className="plan__blaze plan__blaze--blue" />
          </div>
          <p className="plan__empty-voice">
            No plan yet. You could just walk north and find out.
          </p>
          <p className="plan__empty-note">
            Or drop two points on the map and it&rsquo;ll tell you what&rsquo;s between
            them.
          </p>
          <button type="button" className="plan__primary" onClick={onStartOnMap}>
            Start on the map
          </button>
        </div>
        {targetSheet}
      </div>
    )
  }

  const direction = planDirection(plan)
  const selected = selectedDay === null ? null : (views[selectedDay] ?? null)

  return (
    <div className="plan">
      <header className="plan__head">
        <h1 className="plan__title">
          {stopLabel(views[0].start)} → {stopLabel(views[views.length - 1].end)}
        </h1>
        <span className="plan__head-note">
          {direction === null ? '' : `${direction} · `}
          {views.length} days
          {finishLabel(views) === null ? '' : ` · finish ≈ ${finishLabel(views)}`}
        </span>
      </header>

      {elevation !== null && (
        <p className="plan__legend">
          <span className="plan__legend-swatch" aria-hidden="true" />
          row height = walking hours
        </p>
      )}

      {sections.map((section, sectionIndex) => (
        <section className="plan__section" key={section.days[0].id}>
          <header className="plan__section-head">
            <div className="plan__section-title-row">
              <h2 className="plan__section-title">
                {stopLabel(section.days[0].start)} →{' '}
                {stopLabel(section.days[section.days.length - 1].end)}
              </h2>
              {sections.length > 1 && (
                <span className="plan__section-count">
                  SEC {sectionIndex + 1}/{sections.length}
                </span>
              )}
            </div>
            <p className="plan__section-stats">
              <span>{formatDistance(section.distanceMi, units, 'whole')}</span>
              <span>{section.days.length} days</span>
              {sectionAscent(section, figures) !== null && (
                <span>
                  {formatElevation(sectionAscent(section, figures) as number, units)} ↑
                </span>
              )}
              {section.days[section.days.length - 1].end.resupply && (
                <span className="plan__section-food">{section.foodDays} days food</span>
              )}
            </p>
          </header>

          <ol className="plan__days">
            {section.days.map((day) => (
              <li key={day.id}>
                <DayRow
                  day={day}
                  figures={figures.get(day.index)}
                  carryOut={
                    day.end.resupply
                      ? (sections[sectionIndex + 1]?.foodDays ?? null)
                      : null
                  }
                  units={units}
                  elevation={elevation}
                  onSelect={() => setSelectedDay(day.index)}
                />
              </li>
            ))}
          </ol>
        </section>
      ))}

      <div className="plan__foot">
        <button type="button" className="plan__foot-action" onClick={onChangeTarget}>
          {targetLabel(plan, units)}
        </button>
        <button
          type="button"
          className="plan__foot-action plan__foot-action--danger"
          onClick={() => {
            if (!confirmingDelete) {
              setConfirmingDelete(true)
              return
            }
            setConfirmingDelete(false)
            onDeletePlan()
          }}
        >
          {confirmingDelete ? 'Tap again to delete the plan' : 'Delete plan'}
        </button>
      </div>

      {selected !== null && (
        <DayActions
          day={selected}
          onInsertZeroAfter={() => {
            onInsertZeroAfter(selected.index)
            setSelectedDay(null)
          }}
          onRemoveDay={() => {
            onRemoveDay(selected.index)
            setSelectedDay(null)
          }}
          onTogglePinned={() => {
            onTogglePinned(selected.index)
            setSelectedDay(null)
          }}
          onToggleEndResupply={() => {
            onToggleEndResupply(selected.index)
            setSelectedDay(null)
          }}
          onClose={() => setSelectedDay(null)}
        />
      )}
      {targetSheet}
    </div>
  )
}

/** The last day's date as "30 Aug", or null on an undated plan. */
function finishLabel(views: PlanDayView[]): string | null {
  const last = views[views.length - 1]?.date
  if (last === null || last === undefined) return null
  const date = new Date(`${last}T00:00:00Z`)
  const month = date.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' })
  return `${date.getUTCDate()} ${month}`
}

function sectionAscent(
  section: PlanSection,
  figures: Map<number, LegFigures>,
): number | null {
  let total = 0
  for (const day of section.days) {
    if (day.zero) continue
    const f = figures.get(day.index)
    if (f === undefined) return null
    total += f.ascentFt
  }
  return total
}

function targetLabel(plan: HikePlan, units: UnitSystem): string {
  if ('walkingHours' in plan.target) {
    return `Target: ${plan.target.walkingHours}h walking`
  }
  return `Target: ${formatDistance(plan.target.miles, units, 'trimmed')} per day`
}

interface DayRowProps {
  day: PlanDayView
  figures: LegFigures | undefined
  /** Days of food out of this row's resupply stop, or null when the row is
   *  not a resupply (or the plan ends here). */
  carryOut: number | null
  units: UnitSystem
  elevation: ElevationProfile | null
  onSelect: () => void
}

function DayRow({ day, figures, carryOut, units, elevation, onSelect }: DayRowProps) {
  const resupply = day.end.resupply

  if (day.zero) {
    return (
      <div className="plan__row">
        <RowGutter day={day} />
        <button type="button" className="plan__day plan__day--zero" onClick={onSelect}>
          <span>Zero · {stopLabel(day.start)}</span>
          <span className="plan__day-figure">no walking</span>
        </button>
      </div>
    )
  }

  const height = figures === undefined ? MIN_ROW_PX : dayRowHeight(figures.minutes)

  return (
    <div className="plan__row">
      <RowGutter day={day} />
      <button
        type="button"
        className={resupply ? 'plan__day plan__day--resupply' : 'plan__day'}
        style={{ height: `${height}px` }}
        onClick={onSelect}
      >
        {!resupply && elevation !== null && (
          <DayTerrain
            elevation={elevation}
            fromMile={day.start.mile}
            toMile={day.end.mile}
          />
        )}
        <span className="plan__day-top">
          <span className="plan__day-title">
            {stopLabel(day.start)} → {stopLabel(day.end)}
            {day.pinned && (
              <span className="plan__day-pin" role="img" aria-label="pinned">
                📌
              </span>
            )}
          </span>
          <span className="plan__day-figure">
            {formatDistance(Math.abs(day.end.mile - day.start.mile), units)}
          </span>
        </span>
        {resupply && carryOut !== null && (
          <span className="plan__day-carry">
            resupply · carry {carryOut} {carryOut === 1 ? 'day' : 'days'} out
          </span>
        )}
        {resupply && carryOut === null && (
          <span className="plan__day-carry">resupply</span>
        )}
        <span className="plan__day-bottom">
          {figures !== undefined && (
            <span className="plan__day-figure">
              {formatNaismithMinutes(figures.minutes)} ·{' '}
              {formatElevation(figures.ascentFt, units)} ↑
            </span>
          )}
          {day.generated && <span className="plan__day-auto">auto</span>}
        </span>
      </button>
    </div>
  )
}

function RowGutter({ day }: { day: PlanDayView }) {
  return (
    <span className="plan__gutter">
      {day.date !== null && <span>{dayDateLabel(day.date)}</span>}
      {day.dayNumber !== null && <span>DAY {day.dayNumber}</span>}
    </span>
  )
}

const TERRAIN_W = 100
const TERRAIN_H = 40

/**
 * One day's slice of the profile, in the elevation ribbon's own geometry -
 * stretched viewBox, per-window vertical normalisation, gaps interpolated
 * in the picture only. X runs in the DIRECTION OF TRAVEL, so a southbound
 * day reads left-to-right the way it will be walked.
 */
function DayTerrain({
  elevation,
  fromMile,
  toMile,
}: {
  elevation: ElevationProfile
  fromMile: number
  toMile: number
}) {
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)
  const samples = ribbonSamples(elevation, { startMile: low, endMile: high })
  if (samples.length < 2) return null

  const southbound = toMile < fromMile
  const span = high - low
  const xFor = (mile: number) => {
    const pct = span === 0 ? 0 : ((mile - low) / span) * TERRAIN_W
    return southbound ? TERRAIN_W - pct : pct
  }

  const elevations = samples.map((s) => s.elevationFt)
  const minFt = Math.min(...elevations)
  const maxFt = Math.max(...elevations)
  const range = maxFt - minFt
  const yFor = (ft: number) =>
    range === 0 ? TERRAIN_H / 2 : TERRAIN_H - ((ft - minFt) / range) * (TERRAIN_H * 0.82)

  const ordered = southbound ? [...samples].reverse() : samples
  const line = ordered
    .map(
      (s, i) =>
        `${i === 0 ? 'M' : 'L'}${xFor(s.mile).toFixed(2)},${yFor(s.elevationFt).toFixed(2)}`,
    )
    .join(' ')
  const area = `${line} L${TERRAIN_W},${TERRAIN_H} L0,${TERRAIN_H} Z`

  return (
    <svg
      className="plan__terrain"
      viewBox={`0 0 ${TERRAIN_W} ${TERRAIN_H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={area} className="plan__terrain-area" />
      <path d={line} className="plan__terrain-line" fill="none" />
    </svg>
  )
}

interface DayActionsProps {
  day: PlanDayView
  onInsertZeroAfter: () => void
  onRemoveDay: () => void
  onTogglePinned: () => void
  onToggleEndResupply: () => void
  onClose: () => void
}

/** The tapped day's actions. A sheet rather than a screen because the
 *  timeline behind it is the context for every choice on it - which day,
 *  between which neighbours. */
function DayActions({
  day,
  onInsertZeroAfter,
  onRemoveDay,
  onTogglePinned,
  onToggleEndResupply,
  onClose,
}: DayActionsProps) {
  const where = day.zero
    ? `Zero at ${stopLabel(day.start)}`
    : `${stopLabel(day.start)} → ${stopLabel(day.end)}`

  return (
    <div className="plan__actions" role="dialog" aria-label="Day actions">
      <p className="plan__actions-title">{where}</p>
      <button type="button" className="plan__action" onClick={onInsertZeroAfter}>
        Add a zero day after this
      </button>
      {!day.zero && (
        <button type="button" className="plan__action" onClick={onToggleEndResupply}>
          {day.end.resupply
            ? `No resupply at ${stopLabel(day.end)}`
            : `Resupply at ${stopLabel(day.end)}`}
        </button>
      )}
      <button type="button" className="plan__action" onClick={onTogglePinned}>
        {day.pinned ? 'Unpin this day' : 'Pin this day — it does not move'}
      </button>
      <button type="button" className="plan__action" onClick={onRemoveDay}>
        {day.zero ? 'Remove this zero' : 'Remove this day'}
      </button>
      <button
        type="button"
        className="plan__action plan__action--quiet"
        onClick={onClose}
      >
        Cancel
      </button>
    </div>
  )
}
