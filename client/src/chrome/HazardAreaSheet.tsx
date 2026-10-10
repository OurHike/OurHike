// The card over a tapped hunting area, shooting site or burned area (#1805,
// decision 67).
//
// The mock the maintainer chose (decisions-64-67-mock.html §4, option A):
// the kind of area as the heading, an Advisory tag, one or two sentences of
// what to do, and that the trail stays open - about the area, the thing the
// hiker tapped (`areaBody`, decision 99), where a tapped stretch's sheet says
// "This stretch…" (`body`). Then who published the area, its own
// dates where it gives them, and its page. Never "closed": an area a hiker
// walks into is not a closure, and lib/hazardAreas.ts says why that line is
// held in both the pipeline and here.
//
// The publisher is named, never "the layer" or "the agency": "layer" is a GIS
// word a hiker does not use, and "the agency" was a second name for the
// organization the meta line already names (the word-choice review of #1805,
// 2026-10-09).

import { longDate } from '../lib/atcNoticeText'
import { HAZARD_ADVISORIES, hazardDates } from '../lib/hazardAreas'
import { noticeOrgLabel, noticeUpdatedAt, type TrailNotice } from '../lib/notices'
import { isSafeLink } from '../lib/safeLink'
import { possessive, type Stewards } from '../lib/stewards'

export interface HazardAreaSheetProps {
  notice: TrailNotice
  stewards: Stewards
  onClose: () => void
}

export function HazardAreaSheet({ notice, stewards, onClose }: HazardAreaSheetProps) {
  const org = noticeOrgLabel(stewards)(notice)
  const advisory =
    notice.hazard === null || notice.hazard === undefined
      ? null
      : HAZARD_ADVISORIES[notice.hazard]
  const updatedAt = noticeUpdatedAt(notice)
  if (advisory === null) return null

  return (
    <div className="closure-sheet" role="dialog" aria-label={advisory.heading}>
      <div className="legend__head">
        <h2 className="legend__title">
          {advisory.heading}{' '}
          <span className="planned-notices__tag planned-notices__tag--warn">
            Advisory
          </span>
        </h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="closure-sheet__status">{advisory.areaBody}</p>

      <p className="closure-sheet__range">
        {[notice.title, notice.category, notice.locality]
          .filter((part): part is string => typeof part === 'string' && part !== '')
          .join(' · ')}
      </p>
      <p className="closure-sheet__range">{hazardDates(notice, org)}</p>

      <p className="closure-sheet__meta">
        {updatedAt === null
          ? `From ${org}`
          : `From ${org} — updated ${longDate(updatedAt)}`}
      </p>

      {notice.source_url !== null && isSafeLink(notice.source_url) && (
        <a
          className="closure-sheet__link"
          href={notice.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Read {possessive(org)} page
        </a>
      )}

      <p className="closure-sheet__limit" role="note">
        {org} drew this area; the advice is OurHike’s. OurHike hasn’t checked it on the
        ground.
      </p>
    </div>
  )
}
