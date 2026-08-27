// Every notice the app is holding, from every organization, in one list.
//
// Was AtcNoticeList.tsx, and the rename is the change (#1083). The surface
// itself was already right - features/ATC_TRAIL_UPDATES.md ended its open
// questions with "**Where the suppressed ones go.** 'List entry' still has no
// surface", and this is that surface. What was wrong was that it could only
// ever hold one organization's notices, in structure as much as in wording:
//
//  - it sorted by `start_mile_marker`, a field only the A.T. has;
//  - it said "Appalachian Trail Conservancy" in five places as a literal.
//
// features/ORG_NOTICES.md §6 is the rule the second one broke: the org's name
// is read from the registry, never written in the client, because "a string in
// a component is how the app ends up telling a hiker that NYNJTC's closure is
// ATC's word."
//
// ONE FLAT LIST, NEWEST FIRST, SCOPED TO WHERE THE HIKER IS LOOKING. Both
// halves of that are a maintainer's call (2026-08-27) and lib/notices.ts
// carries the argument for each, including the one it overrules: this file's
// own `byMile` comment, which said date order "would put a notice edited
// yesterday above one two miles ahead". That worry is real and it is answered
// by the scoping rather than by the sort - the notice two miles ahead is in
// the extent and the one four hundred miles away is not.
//
// WHAT THIS IS NOT. It is not any organization's notice. The artifacts carry
// facts and a link and deliberately not their prose - `pipeline/sources.json`
// records why for each of them, and #458 is where the maintainer settled the
// conservative reading for ATC on their own judgement as an ATC trail
// volunteer. So every row ends at the publisher's page, and the header says so
// rather than leaving a reader to infer that a list this complete-looking is
// complete. Showing everything OurHike holds and being honest that OurHike
// does not hold everything are the same requirement, not competing ones.

import { useState } from 'react'
import { isSafeLink, longDate, mile } from '../lib/atcNoticeText'
import {
  noticeBandId,
  noticeOrgLabel,
  noticeUpdatedAt,
  scopedNotices,
  type MileExtent,
  type TrailNotice,
} from '../lib/notices'
import type { Stewards } from '../lib/stewards'

export interface NoticeListProps {
  /** Every notice the app holds, from every publisher, in whatever order it
   *  read them. */
  notices: readonly TrailNotice[]
  /**
   * The band ids the map is drawing right now.
   *
   * Passed in rather than re-derived from the notice. The map's own filters
   * would give the answer this build INTENDS, and `trailSlice` can still
   * refuse a mile that falls outside this build's centerline - so a list that
   * worked it out itself would tell a hiker to look for a dot that is not
   * there. The shell already holds the drawn collections, so the true answer
   * is free.
   */
  drawnIds: ReadonlySet<string>
  /**
   * When a person last checked each organization's notices against that
   * organization's page.
   *
   * A map, and the difference between an absent KEY and a null VALUE is
   * load-bearing:
   *
   *   key present, a date   somebody reviews this source, and this is when.
   *   key present, null     somebody reviews it and this build cannot say when.
   *   key ABSENT            nobody reviews this source at all.
   *
   * The third is NYNJTC's real state and `pipeline/export_nynjtc_alerts.py`
   * makes it deliberately: that artifact carries no `reviewed_at`, and its
   * absence "is load-bearing rather than an omission - nobody has checked
   * NYNJTC's, so there is no such date to carry, and inventing one would claim
   * a review that did not happen."
   */
  reviewedAt: ReadonlyMap<string, Date | null>
  /** The published registry, which is where every organization's name comes
   *  from. An empty list is ordinary - see lib/stewards.ts - and renders the
   *  raw source key rather than a guess. */
  stewards: Stewards
  /**
   * The stretch of trail the map is currently showing, or null.
   *
   * Notices outside it are held back rather than dropped - the count is
   * printed and one tap shows them. Null scopes nothing, which is the state
   * before the centerline has loaded and the behaviour this screen had before
   * the rule existed.
   */
  extent: MileExtent | null
  /** The shell's clock, so "posted today" moves with it. */
  now: Date
  onClose: () => void
}

/** `the ATC` -> `the ATC's`. Kept here rather than in a util because it is one
 *  rule with one caller, and because the rule is about ENGLISH and not about
 *  notices: an organization whose name already ends in s takes the bare
 *  apostrophe. None of the registered organizations does today; the branch is
 *  there so the first one that registers does not read wrong. */
function possessive(name: string): string {
  return name.endsWith('s') ? `${name}’` : `${name}’s`
}

/** The extent of a notice that has one, or null. Only `at_miles` carries a
 *  mile, which is why this narrows rather than taking two numbers. */
function extent(notice: TrailNotice): string | null {
  if (notice.place.kind !== 'at_miles') return null
  const { start, end } = notice.place
  return start === end ? `mi ${mile(start)}` : `mi ${mile(start)} – ${mile(end)}`
}

function Notice({
  notice,
  org,
  onMap,
}: {
  notice: TrailNotice
  org: string
  onMap: boolean
}) {
  const updatedAt = noticeUpdatedAt(notice)
  const range = extent(notice)
  const where = [notice.locality, range].filter((part) => part !== '' && part !== null)

  return (
    <li className="atc-notices__item">
      {/* The organization's own category, verbatim, for the reason
          AtcUpdateSheet.tsx gives: mapping it onto ClosureReason would render
          a Detour as "Closed", which is a claim they did not make.

          NULL IS A REAL VALUE HERE and it is NYNJTC's on every row - they file
          every alert under one category and publish no per-alert vocabulary,
          so there is nothing true to print. An absent line, never a borrowed
          word from ATC's list. */}
      {notice.category !== null && (
        <p className="atc-notices__category">{notice.category}</p>
      )}

      <p className="atc-notices__title">{notice.title}</p>

      {where.length > 0 && <p className="closure-sheet__range">{where.join(' · ')}</p>}

      {/* The reviewer's answer to the one question a category cannot be read
          for (lib/atcUpdates.ts, `obstructs_trail`). Both branches are stated:
          "the trail is passable" is a thing a hiker wants to have been told,
          not the absence of a warning. */}
      <p className="atc-notices__passability">
        {notice.review_state === 'unreviewed'
          ? `OurHike hasn’t checked this one yet — read ${possessive(org)} page.`
          : notice.obstructs_trail
            ? `${org} says this stops a hiker walking through.`
            : `${org} didn’t report the trail itself blocked here.`}
      </p>

      <p className="closure-sheet__meta">
        {updatedAt === null ? org : `${org} — updated ${longDate(updatedAt)}`}
      </p>

      {/* Where a notice with no mark on the map says so. A hiker who read this
          list, walked the miles and saw nothing red would otherwise be
          entitled to conclude the notice had been lifted. */}
      {!onMap && (
        <p className="atc-notices__offmap">Not drawn on the map &mdash; read it here.</p>
      )}

      {isSafeLink(notice.source_url) && (
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

export function NoticeList({
  notices,
  drawnIds,
  reviewedAt,
  stewards,
  extent,
  now,
  onClose,
}: NoticeListProps) {
  const [showEverything, setShowEverything] = useState(false)
  const scoped = scopedNotices(notices, extent, drawnIds, now)
  const ordered = showEverything
    ? scopedNotices(notices, null, drawnIds, now).shown
    : scoped.shown
  const orgOf = noticeOrgLabel(stewards)

  // The organizations actually present, in the order the list shows them.
  // Read off the rows rather than off the registry: this list is about what
  // the app is HOLDING, and a steward with no notices has nothing to say here.
  const present: string[] = []
  for (const notice of ordered) {
    if (!present.includes(notice.source_key)) present.push(notice.source_key)
  }

  // With one publisher the heading names them, which is
  // features/ATC_TRAIL_UPDATES.md's "an ATC update must be visibly ATC's"
  // still holding rather than being generalized away. With two it cannot, and
  // the rows carry it instead.
  const soleOrg =
    present.length === 1 ? orgOf({ source_key: present[0] } as TrailNotice) : null
  const heading =
    ordered.length === 1
      ? `1 ${soleOrg ?? 'trail'} notice`
      : `${ordered.length} ${soleOrg ?? 'trail'} notices`

  return (
    <div
      className="atc-notices"
      role="dialog"
      aria-label="Every trail notice OurHike holds"
    >
      <div className="legend__head">
        <h2 className="legend__title">{heading}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {/* First, not last. A reader who takes this list for the notices
          themselves has been misled by the time they reach a footnote. */}
      <p className="closure-sheet__limit" role="note">
        Everything the organizations that look after these trails have posted that OurHike
        holds a copy of &mdash; including the ones the map does not draw. OurHike carries
        each one&rsquo;s facts and a link, never their notice in full, so what each one
        actually says is on their page.
      </p>

      {ordered.length === 0 ? (
        // "Nothing here" and "we could not ask" are different statements, and
        // this component can only honestly make the first. The shell does not
        // mount it at all when the fetch failed.
        <p className="atc-notices__empty">
          {notices.length === 0
            ? 'OurHike is holding no trail notices.'
            : 'No trail notices on the stretch you are looking at.'}
        </p>
      ) : (
        <ul className="atc-notices__list">
          {ordered.map((notice) => (
            <Notice
              key={notice.notice_id}
              notice={notice}
              org={orgOf(notice)}
              onMap={drawnIds.has(noticeBandId(notice))}
            />
          ))}
        </ul>
      )}

      {/* NEVER SILENTLY DROPPED. The scoping is a convenience for a hiker
          reading one stretch of a 2,197-mile trail; a notice the app is
          holding and does not mention is the failure this whole screen exists
          to prevent. So the count is printed and one tap shows them. */}
      {scoped.hidden > 0 && !showEverything && (
        <button
          type="button"
          className="atc-notices__show-all"
          onClick={() => setShowEverything(true)}
        >
          {scoped.hidden === 1
            ? 'Show 1 more, elsewhere on the trail'
            : `Show ${scoped.hidden} more, elsewhere on the trail`}
        </button>
      )}
      {showEverything && scoped.hidden > 0 && (
        <p className="atc-notices__section-note">
          Showing every notice OurHike holds, including the ones off the stretch you are
          looking at.
        </p>
      )}

      {/* The second age, last and plain - the same placement and the same
          reasoning as the single-notice sheet. It is the one a hiker only
          needs when something looks wrong.

          One line per organization present, because "when did OurHike last
          check" has a different answer for each of them, and NYNJTC's answer
          is "never" rather than "we cannot tell". */}
      {present.map((sourceKey) => {
        const org = orgOf({ source_key: sourceKey } as TrailNotice)
        const reviewed = reviewedAt.get(sourceKey)
        return (
          <p className="closure-sheet__age" key={sourceKey}>
            {!reviewedAt.has(sourceKey)
              ? `Nobody at OurHike has checked ${possessive(org)} notices.`
              : reviewed === null || reviewed === undefined
                ? `OurHike can’t tell when it last checked ${possessive(org)} notices.`
                : `OurHike last checked ${possessive(org)} notices on ${longDate(reviewed)}.`}
          </p>
        )
      })}
    </div>
  )
}
