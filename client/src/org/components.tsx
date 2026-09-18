/**
 * The shared surfaces every organization screen is built from.
 *
 * **NINE COMPONENTS, NOT TWENTY-THREE COPIES**, which is the design's one
 * structural note and the reason this file exists rather than each screen
 * drawing its own table. The demo org at `/for-orgs/demo/` mounts these same
 * components through the embeds: *"the moment the demo gets its own copies it
 * starts lying about the product."*
 *
 * They are in one file rather than eight because they are one vocabulary -
 * a reader working out why a blaze renders as a hatched square should not
 * have to open three files to find out, and none of them is big enough to
 * earn its own.
 */

import { formatDistance, type UnitSystem } from '../lib/units'
import { useMemo, useState } from 'react'
import './orgConsole.css'
import type { CoverageGap, OrgPark, OrgSection, Workday } from './orgApi'

/* ------------------------------------------------------------------ *
 * Page Header
 * ------------------------------------------------------------------ */

export function PageHeader({
  eyebrow,
  title,
  sub,
  glyph,
  actions,
}: {
  eyebrow: string
  title: string
  sub?: React.ReactNode
  /** An inline SVG path, drawn in the ring beside the title. */
  glyph?: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <header className="org-head">
      {glyph ? (
        <span className="org-head__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24">{glyph}</svg>
        </span>
      ) : null}
      <div className="org-head__words">
        <span className="org-eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        {sub ? <p className="org-head__sub">{sub}</p> : null}
      </div>
      {actions ? <div className="org-inline">{actions}</div> : null}
    </header>
  )
}

/* ------------------------------------------------------------------ *
 * Blaze swatch
 * ------------------------------------------------------------------ */

/** Every blaze string we can actually render, by its mapped name.
 *
 *  Drawn from the design system's blaze tokens, which exist because **a blaze
 *  colour in a map or a table is data rather than decoration**: it is the
 *  colour of the paint on the tree, and a hiker at a junction is matching it
 *  against what they can see.
 *
 *  An organization's own string that is not in here renders HATCHED with the
 *  string beside it, never as a guessed colour. A wrong swatch sends somebody
 *  down the wrong trail; an unmapped one asks them to read a word.
 */
export const BLAZE_COLORS: Readonly<Record<string, string>> = {
  white: 'var(--blaze-white)',
  blue: 'var(--blaze-blue)',
  yellow: 'var(--blaze-yellow)',
  orange: 'var(--blaze-orange)',
  red: 'var(--alert-red)',
  green: 'var(--forest-500)',
}

export function Blaze({ mapped, raw }: { mapped: string | null; raw: string | null }) {
  const color = mapped ? BLAZE_COLORS[mapped] : undefined
  if (!raw && !mapped) return null
  return (
    <>
      <span
        className={color ? 'org-blaze' : 'org-blaze org-blaze--unmapped'}
        style={color ? { background: color } : undefined}
        aria-hidden="true"
      />
      <span className="org-mono">{raw ?? mapped}</span>
    </>
  )
}

/* ------------------------------------------------------------------ *
 * Registry Table
 * ------------------------------------------------------------------ */

export interface RegistryRow {
  readonly parkName: string
  readonly parkKind: string
  readonly trailName: string
  readonly blazeRaw: string | null
  readonly blazeMapped: string | null
  readonly section: OrgSection
}

/** Every section in an org's registry, flattened with its two parents.
 *
 *  Flattened here rather than rendered nested because the table is the thing
 *  admins read line by line at sign-off, and a nested table cannot be paged,
 *  sorted or isolated by row.
 */
export function registryRows(parks: readonly OrgPark[]): RegistryRow[] {
  const rows: RegistryRow[] = []
  for (const park of parks) {
    for (const trail of park.trails) {
      for (const section of trail.sections) {
        rows.push({
          parkName: park.name,
          parkKind: park.kind,
          // A trail with no name is legitimate - it is a route on a map - so
          // this says so rather than inventing one.
          trailName: trail.name ?? '(unnamed route)',
          blazeRaw: trail.blaze_value_raw,
          blazeMapped: trail.blaze_mapped,
          section,
        })
      }
    }
  }
  return rows
}

export const REGISTRY_PAGE_SIZE = 25

export function RegistryTable({
  parks,
  selectedSectionId,
  onSelect,
  footnote,
}: {
  parks: readonly OrgPark[]
  selectedSectionId?: string | null
  onSelect?: (section: OrgSection | null) => void
  footnote?: string
}) {
  const rows = useMemo(() => registryRows(parks), [parks])
  const [page, setPage] = useState(1)
  const pages = Math.max(1, Math.ceil(rows.length / REGISTRY_PAGE_SIZE))
  const here = Math.min(page, pages)
  const shown = rows.slice((here - 1) * REGISTRY_PAGE_SIZE, here * REGISTRY_PAGE_SIZE)

  if (rows.length === 0) {
    return (
      <div className="org-empty">
        <h3>No sections yet</h3>
        <p>
          Nothing has been read from your GIS yet. The hike registry is where that
          happens, and nothing reaches a hiker until three of your codeowners agree it is
          right.
        </p>
      </div>
    )
  }

  return (
    <div className="org-card org-card--flush">
      <div className="org-table__scroll">
        <table className="org-table">
          <thead>
            <tr>
              <th scope="col">Park or system</th>
              <th scope="col">Trail</th>
              <th scope="col">Blaze</th>
              <th scope="col">Section</th>
              <th scope="col">From → to</th>
              <th scope="col">Miles</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => {
              const selected = selectedSectionId === row.section.id
              return (
                <tr
                  key={row.section.id}
                  data-selectable={onSelect ? '' : undefined}
                  aria-selected={selected}
                  onClick={
                    onSelect ? () => onSelect(selected ? null : row.section) : undefined
                  }
                >
                  <td>{row.parkName}</td>
                  <td className="org-table__name">{row.trailName}</td>
                  <td>
                    <Blaze mapped={row.blazeMapped} raw={row.blazeRaw} />
                  </td>
                  <td className="org-table__name">{row.section.name}</td>
                  <td className="org-mono">
                    {row.section.start_anchor ?? '?'} → {row.section.end_anchor ?? '?'}
                  </td>
                  <td className="org-table__num">
                    {row.section.miles === null ? '—' : row.section.miles.toFixed(1)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="org-table__foot">
        <span>{footnote ?? `Showing ${shown.length} of ${rows.length} sections`}</span>
        <div className="org-table__pager">
          <button
            type="button"
            className="org-btn org-btn--ghost org-btn--small"
            disabled={here <= 1}
            onClick={() => setPage(here - 1)}
          >
            ‹ Back
          </button>
          <span className="org-mono">
            Page {here} of {pages}
          </span>
          <button
            type="button"
            className="org-btn org-btn--ghost org-btn--small"
            disabled={here >= pages}
            onClick={() => setPage(here + 1)}
          >
            Next ›
          </button>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * Section map
 * ------------------------------------------------------------------ */

/** A section's geometry, drawn schematically.
 *
 *  **These are layout, not cartography.** Production draws the org's own GIS
 *  through the map stack; this renders a section's stored GeoJSON into a box
 *  so a row can be isolated and looked at. Where a section has no geometry -
 *  which is legitimate, because a section can be described before it is
 *  drawn - it says so rather than drawing a straight line between two points
 *  it made up.
 */
/** What a drawn section is saying about itself.
 *
 *  `covered` and `gap` are facts about role rows. `vacant` is narrower and
 *  worth its own colour: somebody holds the section, but the role they report
 *  to is empty - so a report reaches a maintainer and stops there. Folding it
 *  into `covered` would let an organization read a solid line as "handled".
 */
export type SectionTone = 'covered' | 'gap' | 'vacant'

const TONE_STROKE: Readonly<Record<SectionTone, string>> = {
  covered: 'var(--brand-primary)',
  gap: 'var(--fg-warn, #b8541c)',
  vacant: 'var(--fg-3)',
}

export function SectionMap({
  sections,
  highlightId,
  caption,
  tone,
  legend = false,
}: {
  sections: readonly OrgSection[]
  highlightId?: string | null
  caption?: string
  /** Colour per section. Omitted means every drawn line is the same. */
  tone?: (section: OrgSection) => SectionTone
  /** Draw the key. `true` uses the coverage report's words; pass three of
   *  your own where the same three colours mean something else - on Your
   *  Tread the pale line is "somebody else's", not "supervisor vacant", and
   *  a shared legend would have told a maintainer the wrong thing about
   *  every mile they do not hold. */
  legend?: boolean | { covered: string; gap: string; vacant: string }
}) {
  const drawn = sections
    .map((section) => ({ section, points: parseLine(section.geometry) }))
    .filter((entry) => entry.points.length > 1)

  if (drawn.length === 0) {
    return (
      <div className="org-empty">
        <h3>No geometry to draw</h3>
        <p>
          These sections are described but not drawn yet. A section can carry its name and
          its anchors before its line arrives — the coverage report and the roster both
          work either way.
        </p>
      </div>
    )
  }

  const all = drawn.flatMap((entry) => entry.points)
  const xs = all.map((p) => p[0])
  const ys = all.map((p) => p[1])
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const spanX = maxX - minX || 1
  const spanY = maxY - minY || 1

  const project = ([lon, lat]: [number, number]): string => {
    const x = ((lon - minX) / spanX) * 520 + 20
    // Latitude increases northward and SVG y increases downward.
    const y = ((maxY - lat) / spanY) * 200 + 20
    return `${x.toFixed(1)} ${y.toFixed(1)}`
  }

  return (
    <div className="org-card">
      <svg viewBox="0 0 560 240" role="img" aria-label={caption ?? 'Sections on the map'}>
        {drawn.map(({ section, points }) => {
          const lit =
            highlightId === undefined ||
            highlightId === null ||
            highlightId === section.id
          const stroke = tone ? TONE_STROKE[tone(section)] : 'var(--brand-primary)'
          return (
            <polyline
              key={section.id}
              points={points.map(project).join(' ')}
              fill="none"
              stroke={lit ? stroke : 'var(--border-2)'}
              strokeWidth={lit ? 3 : 2}
              strokeDasharray={tone && tone(section) === 'vacant' ? '7 5' : undefined}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )
        })}
      </svg>
      {legend ? (
        <div className="org-inline">
          <span className="org-mono" style={{ color: TONE_STROKE.covered }}>
            — {legend === true ? 'role assigned' : legend.covered}
          </span>
          <span className="org-mono" style={{ color: TONE_STROKE.gap }}>
            — {legend === true ? 'no role assigned' : legend.gap}
          </span>
          <span className="org-mono" style={{ color: TONE_STROKE.vacant }}>
            -- {legend === true ? 'supervisor vacant' : legend.vacant}
          </span>
        </div>
      ) : null}
      {caption ? <p className="org-mono">{caption}</p> : null}
    </div>
  )
}

/** A GeoJSON LineString's coordinates, or [] for anything else.
 *
 *  Every failure returns [] on purpose. This runs over data an organization
 *  supplied, and a section whose geometry is malformed should draw nothing
 *  rather than take the screen down.
 */
export function parseLine(geometry: string | null): [number, number][] {
  if (!geometry) return []
  try {
    const parsed: unknown = JSON.parse(geometry)
    const coords = (parsed as { coordinates?: unknown })?.coordinates
    if (!Array.isArray(coords)) return []
    return coords.filter(
      (point): point is [number, number] =>
        Array.isArray(point) &&
        point.length >= 2 &&
        typeof point[0] === 'number' &&
        typeof point[1] === 'number' &&
        Number.isFinite(point[0]) &&
        Number.isFinite(point[1]),
    )
  } catch {
    return []
  }
}

/* ------------------------------------------------------------------ *
 * Console Tiles
 * ------------------------------------------------------------------ */

export interface ConsoleTile {
  readonly key: string
  readonly label: string
  readonly value: React.ReactNode
  readonly meta?: React.ReactNode
  readonly action?: React.ReactNode
}

/** Org home's grid of what an organization has published.
 *
 *  Each tile is what a hiker sees today, and editing one opens a proposal -
 *  the same pull request the registry went through the first time. The
 *  action is therefore always a verb about proposing, never about saving.
 */
export function ConsoleTiles({ tiles }: { tiles: readonly ConsoleTile[] }) {
  return (
    <div className="org-grid org-grid--three">
      {tiles.map((tile) => (
        <div className="org-tile" key={tile.key}>
          <span className="org-tile__label">{tile.label}</span>
          <span className="org-tile__value">{tile.value}</span>
          {tile.meta ? <span className="org-tile__meta">{tile.meta}</span> : null}
          {tile.action ? <span className="org-tile__action">{tile.action}</span> : null}
        </div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * Coverage Badge
 * ------------------------------------------------------------------ */

/**
 * Sections with no role attached, as a number somebody can act on.
 *
 * **This is a recruiting line, not an alarm.** A new gap is flagged and never
 * escalated: most fill within a season, and treating each as an incident
 * trains people to ignore the report. The wording follows - "looking for" and
 * not "unmaintained" - and no hiker is ever shown it.
 */
/**
 * The coverage badge, as `site/public/embed/v1/ourhike.js` draws it.
 *
 * THIS IS THE CONSOLE'S PREVIEW OF AN EMBED, so what it may draw is decided
 * by what the embed draws and not by what reads well here. It used to draw a
 * gap count - "3 of 12 sections looking for somebody" - which was wrong twice
 * over by 2026-09-18: the embed had been rebuilt as the design's scoreboard,
 * and the gap count had never worked in public anyway, because it read the
 * gated `/clubs/{slug}/coverage` and an anonymous visitor got a 401.
 *
 * It stays a gap count nowhere. `features/ORG_ONBOARDING.md` has the reason
 * the coverage report is gated: a public list of which miles nobody is
 * looking after is a list of miles to avoid. A preview offering one teaches
 * an organization to expect it on their own homepage.
 *
 * The three figures come from the public `GET /clubs/{slug}/scoreboard`.
 * `screens/embedsCoverage.test.tsx` holds this to the embed, and
 * `test/orgEmbeds.test.ts` holds the embed to the same three labels.
 */
export function CoverageBadge({
  miles,
  volunteers,
  hours,
}: {
  /** Miles maintained, summed from the org's own registry. */
  miles: number
  /** How many people hold an assignment today - a count, never a list. */
  volunteers: number
  /** Confirmed hours since the season started. Confirmed, not logged: an
   *  hour nobody stood behind is not a figure to print on a donate page. */
  hours: number
}) {
  return (
    <div className="org-tile">
      <span className="org-tile__label">Miles maintained</span>
      <span className="org-tile__value">
        <strong>{miles}</strong>
      </span>
      <span className="org-tile__label">Active volunteers</span>
      <span className="org-tile__value">
        <strong>{volunteers}</strong>
      </span>
      <span className="org-tile__label">Hours this season</span>
      <span className="org-tile__value">
        <strong>{hours}</strong>
      </span>
      <span className="org-tile__meta">
        Counted from their own registry when this page loaded.
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * Workdays Widget
 * ------------------------------------------------------------------ */

const DAY_FORMAT = new Intl.DateTimeFormat('en-US', {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
})

export function formatWorkdayRange(starts: string, ends: string): string {
  const from = new Date(`${starts}T00:00:00`)
  const to = new Date(`${ends}T00:00:00`)
  if (starts === ends) return DAY_FORMAT.format(from)
  return `${DAY_FORMAT.format(from)} – ${DAY_FORMAT.format(to)}`
}

/**
 * Upcoming workdays, and where each one's signup actually goes.
 *
 * **The mirrored case is not an afterthought and is not hidden.** An
 * organization with a working calendar is authoritative on it, so a mirrored
 * workday says "Sign up on their site" and links there. Rendering one button
 * that quietly does two different things is how somebody ends up believing
 * they are on a roster they never reached.
 */
export function WorkdaysWidget({
  workdays,
  onSignUp,
  emptyNote,
}: {
  workdays: readonly Workday[]
  onSignUp?: (workday: Workday) => void
  emptyNote?: string
}) {
  if (workdays.length === 0) {
    return (
      <div className="org-empty">
        <h3>Nothing on the calendar</h3>
        <p>
          {emptyNote ??
            'No workdays in the window. That is the honest answer rather than an empty list pretending to be a filter result.'}
        </p>
      </div>
    )
  }

  return (
    <div className="org-stack">
      {workdays.map((workday) => {
        const mirrored =
          workday.source === 'mirrored' || workday.signup_mode === 'contact'
        const where = workday.signup_url ?? workday.signup_contact ?? null
        return (
          <div className="org-card" key={workday.id}>
            <div className="org-inline">
              <span className="org-mono">
                {formatWorkdayRange(workday.starts_on, workday.ends_on)}
              </span>
              {workday.status === 'cancelled' ? (
                <span className="org-pill" data-tone="stopped">
                  called off
                </span>
              ) : null}
              {mirrored ? (
                <span className="org-pill" data-tone="quiet">
                  their own calendar
                </span>
              ) : null}
            </div>
            <p className="org-table__name" style={{ marginTop: 6 }}>
              {workday.title}
            </p>
            {workday.meet_point ? (
              <p className="org-panel__note">{workday.meet_point}</p>
            ) : null}
            {workday.description ? (
              <p className="org-panel__note">{workday.description}</p>
            ) : null}
            <div className="org-inline" style={{ marginTop: 10 }}>
              {workday.status === 'cancelled' ? (
                <span className="org-mono">
                  This one was called off. Nothing to sign up to.
                </span>
              ) : mirrored && where ? (
                <a className="org-btn org-btn--ghost org-btn--small" href={where}>
                  Sign up on their site
                </a>
              ) : onSignUp ? (
                <button
                  type="button"
                  className="org-btn org-btn--small"
                  onClick={() => onSignUp(workday)}
                >
                  Put your hand up
                </button>
              ) : null}
              <span className="org-mono">
                {workday.confirmed_count} confirmed
                {workday.cap === null ? '' : ` of ${workday.cap}`} ·{' '}
                {workday.interested_count} interested
              </span>
            </div>
            {!mirrored && workday.status !== 'cancelled' ? (
              <p className="org-mono" style={{ marginTop: 8 }}>
                Putting your hand up tells them you are interested. They answer — it is
                not a place on a roster until they say so.
              </p>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * Hike Finder
 * ------------------------------------------------------------------ */

export interface FinderHike {
  readonly id: string
  readonly name: string
  readonly features: string
  readonly park: string
  readonly region: string
  readonly miles: number
  readonly time: string
  readonly route: string
  readonly difficulty: 'Easy' | 'Moderate' | 'Strenuous'
}

/** The field set is #1427's, measured rather than invented.
 *
 *  That issue took the whole NYNJTC hike list from the Hike Finder export and
 *  recorded the twelve labelled fields every detail page carries - Length,
 *  Difficulty, Estimated Time, Route Type, Park, Region, Features among them.
 *  These six columns are that set narrowed to what fits a table, which is why
 *  this component's shape is one of the two things on these screens that is
 *  not @unvalidated.
 */
/** The length filter's four buckets, in the hiker's own unit.
 *
 *  The EDGES are miles because the data is - `FinderHike.miles` and
 *  `OrgSection.miles` both are - and the LABELS are whatever the hiker chose
 *  in Settings. Writing "Under 3 miles" into the label would put a distance
 *  on screen that `lib/units.ts` never saw, which is the whole of #619's
 *  rule and what `unitDisplay.test.ts` catches. Converting the edges too
 *  would move the buckets when somebody switches units, so a hike could fall
 *  out of "3 to 6" by a Settings change alone.
 */
export const LENGTH_BAND_EDGES = [null, [null, 3], [3, 6], [6, null]] as const

export function lengthBandLabels(units: UnitSystem): string[] {
  const at = (miles: number) => formatDistance(miles, units, 'trimmed')
  return ['Any length', `Under ${at(3)}`, `${at(3)} to ${at(6)}`, `Over ${at(6)}`]
}

export function HikeFinder({
  hikes,
  orgName,
  units,
}: {
  hikes: readonly FinderHike[]
  orgName: string
  units: UnitSystem
}) {
  const [region, setRegion] = useState('All regions')
  const [difficulty, setDifficulty] = useState('Any difficulty')
  const [bandIndex, setBandIndex] = useState(0)
  const [page, setPage] = useState(1)

  const regions = useMemo(
    () => [
      'All regions',
      ...Array.from(new Set(hikes.map((hike) => hike.region))).sort(),
    ],
    [hikes],
  )

  const matching = useMemo(
    () =>
      hikes.filter((hike) => {
        if (region !== 'All regions' && hike.region !== region) return false
        if (difficulty !== 'Any difficulty' && hike.difficulty !== difficulty)
          return false
        const edge = LENGTH_BAND_EDGES[bandIndex]
        if (edge !== null) {
          const [low, high] = edge
          if (low !== null && hike.miles < low) return false
          if (high !== null && hike.miles > high) return false
        }
        return true
      }),
    [hikes, region, difficulty, bandIndex],
  )

  const perPage = 6
  const pages = Math.max(1, Math.ceil(matching.length / perPage))
  const here = Math.min(page, pages)
  const shown = matching.slice((here - 1) * perPage, here * perPage)

  const reset = () => {
    setRegion('All regions')
    setDifficulty('Any difficulty')
    setBandIndex(0)
    setPage(1)
  }

  return (
    <div className="org-card org-card--flush">
      <div className="org-row" style={{ padding: 14 }}>
        <label className="org-field">
          <span className="org-field__label">Region</span>
          <select
            className="org-select"
            value={region}
            onChange={(event) => {
              setRegion(event.target.value)
              setPage(1)
            }}
          >
            {regions.map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="org-field">
          <span className="org-field__label">Difficulty</span>
          <select
            className="org-select"
            value={difficulty}
            onChange={(event) => {
              setDifficulty(event.target.value)
              setPage(1)
            }}
          >
            {['Any difficulty', 'Easy', 'Moderate', 'Strenuous'].map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="org-field">
          <span className="org-field__label">Length</span>
          <select
            className="org-select"
            value={bandIndex}
            onChange={(event) => {
              setBandIndex(Number(event.target.value))
              setPage(1)
            }}
          >
            {lengthBandLabels(units).map((option, index) => (
              <option key={option} value={index}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="org-btn org-btn--ghost org-btn--small"
          onClick={reset}
        >
          Clear
        </button>
      </div>

      <div className="org-table__scroll">
        <table className="org-table">
          <thead>
            <tr>
              <th scope="col">Hike</th>
              <th scope="col">Park</th>
              <th scope="col">Length</th>
              <th scope="col">Time</th>
              <th scope="col">Route</th>
              <th scope="col">Difficulty</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((hike) => (
              <tr key={hike.id}>
                <td>
                  <span className="org-table__name">{hike.name}</span>
                  <br />
                  <span className="org-mono">{hike.features}</span>
                </td>
                <td>{hike.park}</td>
                <td className="org-table__num">{formatDistance(hike.miles, units)}</td>
                <td className="org-table__num">{hike.time}</td>
                <td>{hike.route}</td>
                <td>
                  <span className="org-pill" data-tone="quiet">
                    {hike.difficulty}
                  </span>
                </td>
              </tr>
            ))}
            {shown.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  Nothing matches those three together. Clear one and try again.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="org-table__foot">
        <span>
          Showing {shown.length === 0 ? 0 : (here - 1) * perPage + 1}–
          {(here - 1) * perPage + shown.length} of {matching.length} hikes
        </span>
        <div className="org-table__pager">
          <button
            type="button"
            className="org-btn org-btn--ghost org-btn--small"
            disabled={here <= 1}
            onClick={() => setPage(here - 1)}
          >
            ‹ Back
          </button>
          <span className="org-mono">
            Page {here} of {pages}
          </span>
          <button
            type="button"
            className="org-btn org-btn--ghost org-btn--small"
            disabled={here >= pages}
            onClick={() => setPage(here + 1)}
          >
            Next ›
          </button>
        </div>
      </div>
      <p className="org-mono" style={{ padding: '0 14px 12px' }}>
        Published by <strong>{orgName}</strong> · drawn by OurHike
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ *
 * Tread Card
 * ------------------------------------------------------------------ */

export interface TreadThanks {
  readonly words: string
  readonly where: string
  readonly category: string
}

/**
 * One stretch a volunteer looks after, and what is waiting on it.
 *
 * **A thanks names a place and a category, never a person.** Rule 4 is not a
 * setting on this card; there is no field for a hiker's name because nothing
 * upstream carries one. Whoever covers the section sees it, and so do their
 * supervisors, and nobody else learns who maintains which mile.
 */
export function TreadCard({
  name,
  eyebrow,
  sub,
  note,
  thanks,
  openReports,
  children,
}: {
  name: string
  eyebrow: string
  sub?: string
  note?: string
  thanks?: readonly TreadThanks[]
  openReports?: number
  children?: React.ReactNode
}) {
  return (
    <section className="org-card org-panel">
      <span className="org-eyebrow">{eyebrow}</span>
      <div className="org-panel__head">
        <h2>{name}</h2>
        {openReports ? (
          <span className="org-pill" data-tone="waiting">
            {openReports} open {openReports === 1 ? 'report' : 'reports'}
          </span>
        ) : null}
      </div>
      {sub ? <p className="org-panel__note">{sub}</p> : null}
      {note ? <p className="org-mono">{note}</p> : null}
      {thanks && thanks.length > 0 ? (
        <div className="org-stack">
          <span className="org-eyebrow">
            {thanks.length} {thanks.length === 1 ? 'thanks' : 'thanks'} on your paths
          </span>
          {thanks.map((entry, index) => (
            <div className="org-callout" data-tone="good" key={index}>
              <span>
                “{entry.words}” · left near {entry.where}, {entry.category}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      {children}
    </section>
  )
}

/* ------------------------------------------------------------------ *
 * Phone Frame
 * ------------------------------------------------------------------ */

/**
 * A 390px screen, drawn as one.
 *
 * **These are a separate design, not the desktop screens made narrow.** The
 * design says so and so does #929's Registry.tsx before it. A maintainer
 * standing at a blowdown and a supervisor in a trailhead car park need fewer
 * things, bigger, working with no signal - which is a different screen rather
 * than the same one at a different width.
 *
 * The frame is a device outline in a desktop page, so it is decorative and
 * hidden from assistive technology; what is INSIDE it is real content and is
 * not.
 */
export function PhoneFrame({
  label,
  note,
  children,
}: {
  label: string
  note?: string
  children: React.ReactNode
}) {
  return (
    <figure className="org-phone">
      <span className="org-eyebrow">{label}</span>
      <div className="org-phone__body">{children}</div>
      {note ? <figcaption className="org-mono">{note}</figcaption> : null}
    </figure>
  )
}

/** The gap list, as the coverage report draws it. */
export function CoverageGaps({ gaps }: { gaps: readonly CoverageGap[] }) {
  if (gaps.length === 0) {
    return (
      <div className="org-callout" data-tone="good">
        <span>
          <strong>Every section here has somebody on it.</strong> That is worth knowing
          and worth not celebrating too hard — it is true today, and a hand-off next month
          makes it a question again.
        </span>
      </div>
    )
  }
  return (
    <div className="org-card org-card--flush">
      <table className="org-table">
        <thead>
          <tr>
            <th scope="col">Section</th>
            <th scope="col">Trail</th>
            <th scope="col">Region</th>
            <th scope="col">Miles</th>
          </tr>
        </thead>
        <tbody>
          {gaps.map((gap) => (
            <tr key={gap.section_id}>
              <td className="org-table__name">{gap.section_name}</td>
              <td>{gap.trail_name ?? '(unnamed route)'}</td>
              <td>{gap.region ?? '—'}</td>
              <td className="org-table__num">
                {gap.miles === null ? '—' : gap.miles.toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
