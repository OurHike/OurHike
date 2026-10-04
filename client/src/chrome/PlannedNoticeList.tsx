// The notices that touch a hike the hiker has planned for the next 7 days
// (#1805, decision 66).
//
// What chrome/NoticeList.tsx is for two organizations, this is for every
// club conditions/notices.json carries - and with 129 clubs a list of
// everything is the feed features/ORG_NOTICES.md §9 warns about. So the list
// is the maintainer's rule, lib/plannedNotices.ts's: per planned hike, the
// placed notices that meet its route, then the unplaced ones from the clubs
// that maintain its trails. Nothing else.
//
// THE EMPTY STATE SAYS WHY, and offers nothing in its place. With no hike
// planned in the window there is no route to touch, and the honest answer is
// that sentence and how to change it - never a feed of every club, and never
// a silent blank a hiker could read as "no notices". The notices the map
// draws still open their own sheet when tapped.
//
// FACTS AND A LINK (decision 55): a title, the club, the dates, where, and
// the club's own page. The organization's name is read from the registry
// (ORG_NOTICES.md §6) and never written here.

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

function Row({ notice, org }: { notice: TrailNotice; org: string }) {
  const { text, warn } = tag(notice)
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
  const where = [notice.locality, own].filter((part) => part !== '' && part !== null)

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
        <span className="atc-notices__title">{notice.title || `${org} notice`}</span>
      </p>
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
  const { stretch, onRoute, fromClubs } = hike
  const count = onRoute.length + fromClubs.length
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
