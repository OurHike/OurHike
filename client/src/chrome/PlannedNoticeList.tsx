// The notices that touch a hike the hiker has planned for the next 7 days
// (#1805, decision 66).
//
// What chrome/NoticeList.tsx is for two organizations, this is for every
// club conditions/notices.json carries - and with 129 clubs a list of
// everything is the feed features/ORG_NOTICES.md §9 warns about. So the list
// is the maintainer's rule, lib/plannedNotices.ts's: per planned hike, the
// placed notices that meet its route, then an agency's state-wide ones for a
// state the route is in on that agency's trails (decision 76, each saying
// "All of Utah"), then the unplaced ones from the clubs that maintain its
// trails. Nothing else.
//
// THE EMPTY STATE SAYS WHY, and offers nothing in its place. With no hike
// planned in the window there is no route to touch, and the honest answer is
// that sentence and how to change it - never a feed of every club, and never
// a silent blank a hiker could read as "no notices". The notices the map
// draws still open their own sheet when tapped.
//
// FACTS AND A LINK (decision 55): a title, the source's own category under it
// (decision 78), the club, the dates, where, and the club's own page. The
// organization's name is read from the registry (ORG_NOTICES.md §6) and never
// written here.

import { longDate } from '../lib/atcNoticeText'
import { HAZARD_ADVISORIES } from '../lib/hazardAreas'
import { noticeOrgLabel, noticeUpdatedAt, type TrailNotice } from '../lib/notices'
import type { PlannedHikeNotices, PlannedNotices } from '../lib/plannedNotices'
import { isSafeLink } from '../lib/safeLink'
import { possessive, type Stewards } from '../lib/stewards'

export interface PlannedNoticeListProps {
  planned: PlannedNotices
  stewards: Stewards
  /** When conditions/notices.json was baked, for the age line. */
  generatedAt: Date | null
  onClose: () => void
}

/** "Sat 10 Oct" from an ISO day, read as the calendar day it names. */
function shortDay(day: string): string {
  const [year, month, date] = day.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, date)).toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

function dates(from: string, to: string): string {
  return from === to ? shortDay(from) : `${shortDay(from)} – ${shortDay(to)}`
}

/** The tag a row leads with: what kind of notice, in two words at most. */
function tag(notice: TrailNotice): { text: string; warn: boolean } {
  if (notice.obstructs_trail) return { text: 'Closure', warn: true }
  if (notice.hazard !== null && notice.hazard !== undefined) {
    return { text: 'Advisory', warn: true }
  }
  return { text: 'Notice', warn: false }
}

/** A label as compared for a repeat: no case, and runs of spaces as one. */
function sameWords(a: string, b: string): boolean {
  const fold = (text: string) =>
    text.trim().replace(/\s+/g, ' ').toLocaleLowerCase('en-US')
  return fold(a) === fold(b)
}

/**
 * The notice's own category, for the line under its title (decision 78), or
 * null where there is nothing to add.
 *
 * The source's word and never OurHike's: USFS's recreation sites send their
 * `openstatus` as it stands ("closed", "temporarily closed", "unreachable",
 * "not cleared", "unknown"), and other layers send "Closure Order", "No
 * Hunting" or a fire's name. Only the first letter is raised, here at the
 * display and never in the published file, so "closed" reads "Closed" as the
 * approved frame (card N2, frame A) draws it and the rest stays as the source
 * wrote it.
 *
 * NOT REPEATED where the row already says it: a category equal to the title
 * the row shows, or to its tag's word, ignoring case and spacing. Equal only,
 * never "contained in": "Little Giant Fire" under "Little Giant Fire Closure
 * Superseding" still names the fire, and "Closure" under a Notice tag is the
 * source calling it a closure where OurHike's tag does not, a fact the tag
 * alone would hide. Measured 2026-10-05 on UA's file from soak run 536: 18 of
 * 7,392 rows had a category equal to their title (USFS R06's fire closure
 * lines), none had one equal to its own tag, and 30 had a "Closure" or
 * "Advisory" under a Notice tag, which show.
 */
function categoryLine(
  notice: TrailNotice,
  title: string,
  tagText: string,
): string | null {
  const category = notice.category?.trim() ?? ''
  if (category === '') return null
  if (sameWords(category, title) || sameWords(category, tagText)) return null
  return category.charAt(0).toLocaleUpperCase('en-US') + category.slice(1)
}

/** "All of Utah", "All of Oregon and Washington": where a state-wide notice
 *  applies (decision 76), from the shapes the phone matched it by, or ''. */
function allOf(notice: TrailNotice): string {
  const names = (notice.state_areas ?? []).map((area) => area.name)
  if (names.length === 0) return ''
  const last = names[names.length - 1]
  return `All of ${names.length === 1 ? last : `${names.slice(0, -1).join(', ')} and ${last}`}`
}

function Row({ notice, org }: { notice: TrailNotice; org: string }) {
  const { text, warn } = tag(notice)
  const title = notice.title || `${org} notice`
  const category = categoryLine(notice, title, text)
  const updatedAt = noticeUpdatedAt(notice)
  const hazard =
    notice.hazard === null || notice.hazard === undefined
      ? null
      : HAZARD_ADVISORIES[notice.hazard]
  const own = [
    notice.starts_on && `from ${notice.starts_on}`,
    notice.ends_on && `until ${notice.ends_on}`,
  ]
    .filter(Boolean)
    .join(' ')
  const where = [allOf(notice), notice.locality, own].filter(
    (part) => part !== '' && part !== null,
  )

  return (
    <li className="atc-notices__item">
      <p className="planned-notices__tagline">
        <span
          className={
            warn
              ? 'planned-notices__tag planned-notices__tag--warn'
              : 'planned-notices__tag'
          }
        >
          {text}
        </span>{' '}
        <span className="atc-notices__title">{title}</span>
      </p>
      {category !== null && <p className="planned-notices__category">{category}</p>}
      {hazard !== null && <p className="closure-sheet__range">{hazard.heading}</p>}
      {where.length > 0 && <p className="closure-sheet__range">{where.join(' · ')}</p>}
      <p className="closure-sheet__meta">
        {updatedAt === null ? org : `${org} — updated ${longDate(updatedAt)}`}
      </p>
      {notice.carried_since && (
        <p className="atc-notices__offmap">
          OurHike couldn’t re-read {possessive(org)} notices since{' '}
          {longDate(new Date(notice.carried_since))}, so this is the last it read.
        </p>
      )}
      {notice.source_url !== null && isSafeLink(notice.source_url) && (
        <a
          className="closure-sheet__link"
          href={notice.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Read {possessive(org)} notice
        </a>
      )}
    </li>
  )
}

function Hike({
  hike,
  orgOf,
}: {
  hike: PlannedHikeNotices
  orgOf: (notice: TrailNotice) => string
}) {
  const { stretch, onRoute, fromClubs, stateWide } = hike
  const count = onRoute.length + stateWide.length + fromClubs.length
  return (
    <section className="planned-notices__hike" aria-label={stretch.label}>
      <h3 className="planned-notices__hike-title">
        {stretch.label}
        <span className="planned-notices__dates">
          {' '}
          · {dates(stretch.from, stretch.to)}
        </span>
      </h3>
      {stretch.kind === 'long_hike' && (
        <p className="closure-sheet__range">
          The stretch you plan to walk in the next 7 days.
        </p>
      )}
      {!stretch.routeResolved && (
        <p className="atc-notices__offmap">
          {stretch.kind === 'day_hike'
            ? 'The trail network for this hike isn’t on this phone yet, so notices are matched to the points you tapped, joined by straight lines.'
            : 'The trail line isn’t loaded yet, so only notices placed by mile are matched.'}
        </p>
      )}
      {count === 0 ? (
        <p className="atc-notices__empty">No notices touch this hike.</p>
      ) : (
        <>
          {onRoute.length > 0 && (
            <ul className="atc-notices__list" aria-label="On your route">
              {onRoute.map((notice) => (
                <Row key={notice.notice_id} notice={notice} org={orgOf(notice)} />
              ))}
            </ul>
          )}
          {stateWide.length > 0 && (
            <ul className="atc-notices__list" aria-label="For the whole state">
              {stateWide.map((notice) => (
                <Row key={notice.notice_id} notice={notice} org={orgOf(notice)} />
              ))}
            </ul>
          )}
          {fromClubs.length > 0 && (
            <>
              <p className="atc-notices__section-note">
                From the clubs that look after these trails. Not placed on the map, so
                read where each one applies.
              </p>
              <ul className="atc-notices__list" aria-label="From the clubs on your route">
                {fromClubs.map((notice) => (
                  <Row key={notice.notice_id} notice={notice} org={orgOf(notice)} />
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  )
}

export function PlannedNoticeList({
  planned,
  stewards,
  generatedAt,
  onClose,
}: PlannedNoticeListProps) {
  const orgOf = noticeOrgLabel(stewards)
  return (
    <div
      className="atc-notices"
      role="dialog"
      aria-label="Notices for your planned hikes"
    >
      <div className="legend__head">
        <h2 className="legend__title">Notices for your hikes</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="closure-sheet__limit" role="note">
        Notices that touch a hike you plan to start in the next 7 days, from the clubs and
        agencies that look after the trails. OurHike carries each one’s facts and a link,
        never the notice in full.
      </p>

      {planned.empty !== null ? (
        <div className="planned-notices__empty">
          <p className="atc-notices__empty">
            {planned.empty === 'nothing_planned'
              ? 'You have no hike planned, so there are no notices to pick for one.'
              : 'None of your planned hikes has a day in the next 7 days.'}
          </p>
          <p className="closure-sheet__range">
            Plan a day hike or a long hike with dates, and the notices on its trails show
            here.
            {planned.undated > 0 &&
              (planned.undated === 1
                ? ' One of your plans has no dates yet.'
                : ` ${planned.undated} of your plans have no dates yet.`)}
          </p>
          <p className="closure-sheet__range">
            Notices drawn on the map open when you tap them.
          </p>
        </div>
      ) : (
        planned.hikes.map((hike) => (
          <Hike key={hike.stretch.id} hike={hike} orgOf={orgOf} />
        ))
      )}

      <p className="closure-sheet__age">
        {generatedAt === null
          ? 'OurHike can’t tell when these notices were gathered.'
          : `Gathered by OurHike on ${longDate(generatedAt)}.`}
      </p>
    </div>
  )
}
