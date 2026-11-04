// The blaze card (#1962, features/CHALLENGES_BLAZE_CARD.md): the ATC's
// hundred items as a card of tiles in the ATC's four sections, a tile
// turning karma gold for each earned item (the maintainer, 2026-11-04: what
// is earned is trail karma, never a blaze). The frame is features/design/blaze-card/Card.dc.html
// and the component BlazeCard.dc.html.
//
// THE CARD IS A PICTURE; THE LIST IS THE CONTROL (maintainer, 2026-11-03).
// At its own size the tiles are 26 px and carry no handler: each SECTION is
// one button, and a tap on it opens the list at that section, where every
// item is a row a thumb and a screen reader can use. Only the expanded state
// puts a handler on a tile, at 56 px. The strip's 8 px tiles (`mini`, the
// Today strip of slice 4) are decoration and the whole card is aria-hidden
// there; its own text is the strip's.
//
// WHAT IT SAYS TO A SCREEN READER: each section button's name is that
// section's one line ("Learn about the A.T., 3 earned of 31"), and the card
// carries one visually hidden sentence for the whole (lib/challengeText.ts
// cardSummary). No numeral for what is missing anywhere (features/
// VOLUNTEERING.md §5 rule 2): a section's size is the ATC's own count.
//
// SIZES ARE PICKED, NOT MEASURED - @unvalidated: 8 / 26 / 56 px are the
// frames' numbers, and what would settle 26 against a thumb is a real hand on
// a real phone, which nobody has tried. 56 is the one size a tile may be
// pressed at, chosen to clear the 44 px minimum with room.

import { useMemo } from 'react'
import {
  isSealed,
  itemTitle,
  type Challenge,
  type ChallengeItem,
} from '../lib/challenges'
import { isItemDone, type ChallengeTag } from '../lib/challengeProgress'
import { cardSummary, titleOrSealed } from '../lib/challengeText'
import { BlazeTile } from './BlazeTile'
import '../screens/challenges.css'

export type BlazeCardSize = 'mini' | 'card' | 'expanded'

export interface BlazeCardProps {
  challenge: Challenge
  tags: readonly ChallengeTag[]
  /** The hiker's local YYYY-MM-DD, for which mystery items are sealed. */
  today: string
  size: BlazeCardSize
  /** The card's size: a tap on a section opens the list at it. */
  onOpenSection?: (sectionId: string) => void
  /** The expanded size: a tap on a tile opens that item's row. */
  onOpenItem?: (item: ChallengeItem) => void
}

export function BlazeCard({
  challenge,
  tags,
  today,
  size,
  onOpenSection,
  onOpenItem,
}: BlazeCardProps) {
  const sections = useMemo(
    () =>
      challenge.sections
        .map((section) => ({
          section,
          items: challenge.items.filter((item) => item.section === section.id),
        }))
        .filter((entry) => entry.items.length > 0),
    [challenge],
  )
  const done = (item: ChallengeItem) => isItemDone(item, challenge.id, tags)
  const mini = size === 'mini'
  const expanded = size === 'expanded'

  return (
    <div
      className={`blaze-card blaze-card--${size}`}
      aria-hidden={mini ? true : undefined}
      data-testid="blaze-card"
    >
      {!mini && <p className="visually-hidden">{cardSummary(challenge, tags)}</p>}
      {sections.map(({ section, items }) => {
        const earned = items.filter(done).length
        const tiles = (
          <span className="blaze-card__tiles" aria-hidden={expanded ? undefined : true}>
            {items.map((item) => {
              const sealed = isSealed(item, today)
              return (
                <BlazeTile
                  key={item.id}
                  icon={item.icon}
                  done={done(item)}
                  sealed={sealed}
                  onPress={
                    expanded && onOpenItem !== undefined
                      ? () => onOpenItem(item)
                      : undefined
                  }
                  label={
                    expanded
                      ? `${done(item) ? 'Earned: ' : ''}${titleOrSealed(item, challenge, today)}`
                      : undefined
                  }
                />
              )
            })}
          </span>
        )
        const label = !mini && (
          <span className="blaze-card__label" aria-hidden="true">
            <span>{section.title}</span>
            <span>{items.length}</span>
          </span>
        )
        const name = `${section.title}, ${earned} earned of ${items.length}`
        if (size === 'card' && onOpenSection !== undefined) {
          return (
            <button
              key={section.id}
              type="button"
              className="blaze-card__section blaze-card__section--press"
              aria-label={name}
              onClick={() => onOpenSection(section.id)}
            >
              {label}
              {tiles}
            </button>
          )
        }
        return (
          <div
            key={section.id}
            className="blaze-card__section"
            role={expanded ? 'group' : undefined}
            aria-label={expanded ? name : undefined}
          >
            {label}
            {tiles}
          </div>
        )
      })}
    </div>
  )
}

/** The title a tile is read by, for a test or a recipe: itemTitle with the
 *  sealed line, as BlazeCard labels its pressable tiles. */
export const blazeTileLabel = (
  item: ChallengeItem,
  challenge: Challenge,
  today: string,
) => itemTitle(item, today) ?? titleOrSealed(item, challenge, today)
