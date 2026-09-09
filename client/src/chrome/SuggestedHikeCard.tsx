// One published route, as a card (#1284) - the Today shelf's 172px card, the
// Find screen's 64px-thumb row, and the results screen's full-bleed hero are
// one component under three class names, so the figures line, the transit
// line and the author line cannot drift between the three surfaces that
// print them.
//
// WHAT A CARD MAY SAY, and where each line comes from:
//
//  - The figures are the route's cached miles and, ONLY when the record
//    carries a climb, the walking time at this hiker's pace - ≈-prefixed,
//    never an arrival clock, and with its baseline beside it whenever the
//    pace is not the standard one (#851). A route whose climb nobody measured
//    prints the distance and says plainly that there is no time. It never
//    prints a time from distance alone: lib/dayHikeShelf.ts's `cachedEstimate`
//    has the reasoning, and it is the direction that gets somebody caught by
//    the dark.
//  - The difficulty is the publisher's own word in a Badge, and no badge at
//    all when they gave none. Never computed here.
//  - The transit icon marks availability only: a route with nothing
//    published renders no icon and no words. An earlier pass drew a
//    struck-through bus in --border-2, which measured 1.9:1 against the card
//    and read as a smudge; a faint "not listed" glyph is worse than silence,
//    and silence is already the app's rule (absent means unknown).
//  - The author line names who published it, in the voice of what kind of
//    publisher they are (lib/suggestedHikes.ts's `authorLine`).
//
// A PHOTO IS A DATA SURFACE, not decoration (features/POI_PHOTOS.md): it
// arrives with its own credit and licence or it does not arrive at all, and
// a route without one gets a plain sunken block of the same size. The credit
// line itself is the detail screen's to print, beside the photo at a size a
// credit can be read at; a 172px card has no honest room for it, and that
// gap is recorded on #1284 rather than papered over.
//
// NOT ALWAYS A BUTTON. The detail a tap opens (wireframe `1g`) exists since
// #1290 and the shell passes `onOpen`, but the prop stays optional: a caller
// with nowhere to send the tap renders the card as an <article> - a thing to
// read, not a control that looks pressable and is not (chrome/LineSheet.tsx's
// rule, PlanKindSheet's unavailable door).

import type { ReactNode } from 'react'
import { Badge } from '../design-system/components'
import type { PaceEstimate, PaceProfile } from '../lib/pace'
import {
  authorLine,
  difficultyLabel,
  hikeEstimate,
  type SuggestedHike,
} from '../lib/suggestedHikes'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'
import { HikeFinderIcon } from './HikeFinderIcon'
import './suggestedHikeCard.css'

export type SuggestedHikeCardVariant = 'shelf' | 'row' | 'hero'

export interface SuggestedHikeCardProps {
  hike: SuggestedHike
  variant: SuggestedHikeCardVariant
  units: UnitSystem
  pace: PaceProfile
  /** Opens the route's detail. Omitted, the card is an article rather than
   *  a button - see the header. */
  onOpen?: (id: string) => void
}

const ROOT_CLASS: Record<SuggestedHikeCardVariant, string> = {
  shelf: 'today__suggested-card',
  row: 'find-hike__row',
  hero: 'find-hike__hero',
}

/** The figures line: distance, then the time or the plain reason there is
 *  none, then - on the two surfaces with room for it - the climb. */
function figuresLine(
  hike: SuggestedHike,
  estimate: PaceEstimate | null,
  units: UnitSystem,
  withClimb: boolean,
): string {
  const parts = [formatDistance(hike.miles, units)]
  if (estimate === null) {
    parts.push('no time — climb unmeasured')
  } else {
    parts.push(estimate.text)
    const climb = hike.climb
    if (withClimb && climb !== undefined && climb !== null) {
      parts.push(`+${formatElevation(climb.gainFt, units)}`)
    }
  }
  return parts.join(' · ')
}

export function SuggestedHikeCard({
  hike,
  variant,
  units,
  pace,
  onOpen,
}: SuggestedHikeCardProps) {
  const estimate = hikeEstimate(hike, pace)
  const shelf = variant === 'shelf'

  const badge =
    hike.difficulty === null ? null : (
      <span className="suggested-hike__badge">
        <Badge tone={hike.difficulty}>{difficultyLabel(hike.difficulty)}</Badge>
      </span>
    )

  const transit =
    hike.transit === undefined ? null : (
      <span className="suggested-hike__transit">
        <HikeFinderIcon
          name="bus"
          className="suggested-hike__transit-icon"
          label="Reachable by public transport"
        />
        {shelf ? (
          // Two lines on the narrow card: the line and where it goes, then
          // the walk from there.
          <span>
            {hike.transit.line}
            {hike.transit.toStop !== '' && ` → ${hike.transit.toStop}`}
            <br />
            {formatDistance(hike.transit.walkMiles, units)} walk
          </span>
        ) : (
          <span>
            {hike.transit.line} · {formatDistance(hike.transit.walkMiles, units)} walk
          </span>
        )}
      </span>
    )

  const photoClass =
    variant === 'shelf'
      ? 'today__suggested-photo'
      : variant === 'row'
        ? 'find-hike__thumb'
        : 'find-hike__hero-photo'
  const photo =
    hike.photo === undefined ? (
      <span className={`${photoClass} suggested-hike__no-photo`} aria-hidden="true" />
    ) : (
      // Decorative to a screen reader; the words beside it carry the card.
      <img className={photoClass} src={hike.photo.url} alt="" />
    )

  const body = (
    <>
      <span className="suggested-hike__name">{hike.name}</span>
      <span className="suggested-hike__figures">
        {figuresLine(hike, estimate, units, !shelf)}
      </span>
      {estimate !== null && estimate.relativeLine !== null && (
        // #851: no surface prints an adjusted time without what it was
        // adjusted from.
        <span className="suggested-hike__baseline">{estimate.relativeLine}</span>
      )}
      {shelf ? (
        <>
          {badge}
          {transit}
        </>
      ) : (
        (badge !== null || transit !== null) && (
          <span className="suggested-hike__facets">
            {badge}
            {transit}
          </span>
        )
      )}
      <span className="suggested-hike__author">{authorLine(hike.author)}</span>
    </>
  )

  const children: ReactNode =
    variant === 'row' ? (
      <>
        {photo}
        <span className="find-hike__row-text">{body}</span>
      </>
    ) : (
      <>
        {photo}
        <span className={shelf ? 'today__suggested-body' : 'find-hike__hero-body'}>
          {body}
        </span>
      </>
    )

  const className = ROOT_CLASS[variant]
  if (onOpen === undefined) {
    return (
      <article className={className} aria-label={hike.name}>
        {children}
      </article>
    )
  }
  return (
    <button type="button" className={className} onClick={() => onOpen(hike.id)}>
      {children}
    </button>
  )
}
