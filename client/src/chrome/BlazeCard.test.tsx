import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BlazeCard } from './BlazeCard'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag, tagsFor } from '../lib/challengeProgress'

afterEach(cleanup)

const TODAY = '2027-07-14'
const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

function earned(...ids: string[]) {
  let state = join(
    EMPTY_CHALLENGE_STATE,
    ATC_CHALLENGE.id,
    new Date('2027-06-01T12:00:00Z'),
  )
  for (const id of ids)
    state = tag(state, ATC_CHALLENGE, item(id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how: 'hand',
    }).state
  return tagsFor(state, ATC_CHALLENGE.id)
}

describe('the blaze card (#1962)', () => {
  it('draws one tile per item in the club’s sections, white once earned', () => {
    const { container } = render(
      <BlazeCard
        challenge={ATC_CHALLENGE}
        tags={earned('springer-mountain', 'trivia-quiz')}
        today={TODAY}
        size="card"
        onOpenSection={vi.fn()}
      />,
    )
    const tiles = container.querySelectorAll('.blaze-tile')
    expect(tiles).toHaveLength(ATC_CHALLENGE.items.length)
    expect(container.querySelectorAll('.blaze-tile--done')).toHaveLength(2)
    // Every tile carries a glyph path: an item with no icon draws `learn`.
    for (const tile of tiles)
      expect(tile.querySelector('svg path')?.getAttribute('d')).toMatch(/^M/)
  })

  it('puts no handler on a tile at the card’s size - a section is the button, named by what is earned', async () => {
    const onOpenSection = vi.fn()
    const { container } = render(
      <BlazeCard
        challenge={ATC_CHALLENGE}
        tags={earned('springer-mountain')}
        today={TODAY}
        size="card"
        onOpenSection={onOpenSection}
      />,
    )
    expect(container.querySelectorAll('button.blaze-tile')).toHaveLength(0)
    const experience = ATC_CHALLENGE.items.filter(
      (entry) => entry.section === 'experience',
    )
    const section = screen.getByRole('button', {
      name: `Experience the A.T., 1 earned of ${experience.length}`,
    })
    await userEvent.click(section)
    expect(onOpenSection).toHaveBeenCalledWith('experience')
    // The tiles themselves are decoration to a screen reader.
    for (const grid of container.querySelectorAll('.blaze-card__tiles'))
      expect(grid).toHaveAttribute('aria-hidden', 'true')
  })

  it('makes every tile a named button only when expanded, and opens the item', async () => {
    const onOpenItem = vi.fn()
    const { container } = render(
      <BlazeCard
        challenge={ATC_CHALLENGE}
        tags={earned('springer-mountain')}
        today={TODAY}
        size="expanded"
        onOpenItem={onOpenItem}
      />,
    )
    expect(container.querySelectorAll('button.blaze-tile')).toHaveLength(
      ATC_CHALLENGE.items.length,
    )
    await userEvent.click(
      screen.getByRole('button', { name: /Take the McAfee Knob shuttle/ }),
    )
    expect(onOpenItem).toHaveBeenCalledWith(item('mcafee-knob'))
    expect(
      screen.getByRole('button', {
        name: /^Earned: Visit the A\.T\.’s southern terminus/,
      }),
    ).toBeInTheDocument()
  })

  it('never renders a sealed mystery title, and marks its tile sealed', () => {
    const { container } = render(
      <BlazeCard
        challenge={ATC_CHALLENGE}
        tags={earned()}
        today="2027-07-19"
        size="expanded"
        onOpenItem={vi.fn()}
      />,
    )
    expect(container.textContent).not.toMatch(/Jefferson Rock/)
    expect(screen.getByRole('button', { name: 'Sealed until Jul 20' })).toHaveClass(
      'blaze-tile--sealed',
    )
  })

  it('says what is earned in one hidden sentence, and never what is not', () => {
    const { container } = render(
      <BlazeCard
        challenge={ATC_CHALLENGE}
        tags={earned('springer-mountain', 'mcafee-knob', 'trivia-quiz')}
        today={TODAY}
        size="card"
        onOpenSection={vi.fn()}
      />,
    )
    const summary = container.querySelector('.visually-hidden')?.textContent ?? ''
    expect(summary).toBe('3 trail karma earned: 1 Learn, 2 Experience.')
    expect(container.textContent).not.toMatch(
      /other hikers|behind|streak|\brank|leaderboard|you haven[’']t|left to go|remaining/i,
    )
  })

  it('is hidden from assistive tech at the strip’s size', () => {
    const { container } = render(
      <BlazeCard challenge={ATC_CHALLENGE} tags={earned()} today={TODAY} size="mini" />,
    )
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
    expect(container.querySelectorAll('button')).toHaveLength(0)
  })
})
