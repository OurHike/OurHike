// The sheet for an ATC trail update, and the reason it is not ClosureSheet.
//
// features/ATC_TRAIL_UPDATES.md §4 is the requirement, and #461 is the issue.
// The rule it enforces is one sentence: **OurHike did not verify this; the
// ATC published it, and those are different statements.** A sheet that said
// "Closed · mi 476.6 – 485.8" and nothing else would be OurHike asserting a
// closure it never checked - which misrepresents the ATC as much as it
// misleads the hiker, and is the failure OurHikeValues.md #4 exists to
// prevent.
//
// Three things here are therefore not optional detail:
//
// **The ATC's name, on the claim.** Not in a map corner, not in a settings
// screen - on the thing being claimed, next to the date they last edited it.
//
// **Both dates, because there are two and they differ.** ATC's own
// `updated_at` is when the notice was last true as far as they know; our
// `reviewedAt` is when a person last checked our copy against their page. A
// notice ATC edited yesterday that nobody here has looked at since May is a
// real state, and the honest thing is to say so rather than to show whichever
// date flatters the app.
//
// **The link, which is load-bearing rather than a nicety.** The artifact
// carries facts and not ATC's prose - their paragraphs are their writing, and
// pipeline/sources.json's `licence` field records why we stop at the facts -
// so this link IS the detail. A hiker who needs to know what the detour
// actually is has nowhere else to go, which is exactly why the scheme is
// checked before it is rendered.

import type { AtcUpdate } from '../lib/atcUpdates'

export interface AtcUpdateSheetProps {
  update: AtcUpdate
  /** When a person last checked the reviewed file against ATC's page, or null
   *  if the artifact does not say. */
  reviewedAt: Date | null
  onClose: () => void
}

function longDate(value: Date): string {
  return value.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

function mile(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/**
 * The date ATC last edited this notice, or null if it is unreadable.
 *
 * Null rather than a fallback. "Updated —" invites the reader to supply their
 * own guess, and an invented date on a safety notice is worse than an absent
 * one: the whole point of showing it is that the hiker can judge how old the
 * claim is.
 */
function atcUpdatedAt(update: AtcUpdate): Date | null {
  const parsed = new Date(update.updated_at)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

/**
 * Whether a URL may be rendered as a link.
 *
 * The same `http(s)`-only rule ClosureSheet applies to `reroute_url`, for the
 * same reason - a `javascript:` URL on a safety sheet is why that validation
 * exists. `pipeline/lib/atc_updates.py` refuses one on the way in as well, so
 * this is the second line rather than the only one; a check that only exists
 * at the far end is one a future second producer walks straight past.
 */
function isSafeLink(url: string): boolean {
  try {
    const scheme = new URL(url, window.location.href).protocol
    return scheme === 'http:' || scheme === 'https:'
  } catch {
    return false
  }
}

export function AtcUpdateSheet({ update, reviewedAt, onClose }: AtcUpdateSheetProps) {
  const updatedAt = atcUpdatedAt(update)
  const range =
    update.start_mile_marker === update.end_mile_marker
      ? `mi ${mile(update.start_mile_marker)}`
      : `mi ${mile(update.start_mile_marker)} – ${mile(update.end_mile_marker)}`

  return (
    <div
      className="closure-sheet"
      role="dialog"
      aria-label="Appalachian Trail Conservancy trail update"
    >
      <div className="legend__head">
        {/* ATC's own category, verbatim. Not mapped onto ClosureReason: that
            enum would render a Detour as "Closed", which is a claim they did
            not make. */}
        <h2 className="legend__title">{update.category}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {/* Their headline, which is the most specific thing the artifact is
          allowed to carry. */}
      <p className="closure-sheet__status">{update.title}</p>

      <p className="closure-sheet__range">
        {update.states.length > 0 ? `${update.states.join(', ')} · ${range}` : range}
      </p>

      {/* The attribution, and the whole point of a separate component. */}
      <p className="closure-sheet__meta">
        {updatedAt === null
          ? 'Appalachian Trail Conservancy'
          : `Appalachian Trail Conservancy — updated ${longDate(updatedAt)}`}
      </p>

      {isSafeLink(update.source_url) && (
        <a
          className="closure-sheet__link"
          href={update.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Read the ATC&rsquo;s notice
        </a>
      )}

      <p className="closure-sheet__limit" role="note">
        This is the ATC&rsquo;s notice, not OurHike&rsquo;s. OurHike has not checked the
        trail itself, and does not work out detours &mdash; follow their notice, or the
        signage on the ground.
      </p>

      {/* The second age. Deliberately last and deliberately plain: it is the
          one a hiker only needs when something looks wrong. */}
      <p className="closure-sheet__age">
        {reviewedAt === null
          ? 'OurHike cannot tell when it last checked ATC’s updates.'
          : `OurHike last checked ATC’s updates on ${longDate(reviewedAt)}.`}
      </p>
    </div>
  )
}
