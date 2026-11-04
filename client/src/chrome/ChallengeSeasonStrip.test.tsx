import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChallengeSeasonStrip } from './ChallengeSeasonStrip'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag } from '../lib/challengeProgress'

afterEach(cleanup)

const TODAY = '2027-07-14'
const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!
const FORBIDDEN =
  /other hikers|behind|streak|\brank|leaderboard|you haven[’']t|left to go|remaining|to go/i

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
  return state
}

describe('the season strip at the bottom of Today (#1964)', () => {
  it('says how many blazes, where, and the club’s finish line in the club’s words', async () => {
    const onOpen = vi.fn()
    const { container } = render(
      <ChallengeSeasonStrip
        challenge={ATC_CHALLENGE}
        state={earned('springer-mountain', 'mcafee-knob', 'trivia-quiz')}
        today={TODAY}
        onOpen={onOpen}
      />,
    )
    expect(screen.getByText('Your summer on the A.T.')).toBeInTheDocument()
    expect(container.querySelector('.season__count')).toHaveTextContent('3 blazes')
    expect(container.querySelector('.season__where')).toHaveTextContent(
      'GA · VA · 1 at home',
    )
    expect(container.querySelector('.season__meta')).toHaveTextContent(
      'A.T. Summer Bucket List · ATC · 5 enters the drawing',
    )
    expect(container.querySelector('.blaze-card--mini')).toHaveAttribute(
      'aria-hidden',
      'true',
    )
    await userEvent.click(screen.getByRole('button'))
    expect(onOpen).toHaveBeenCalledOnce()
  })

  it('carries no numeral for what is missing, and nothing comparative', () => {
    const { container } = render(
      <ChallengeSeasonStrip
        challenge={ATC_CHALLENGE}
        state={earned('springer-mountain')}
        today={TODAY}
        onOpen={vi.fn()}
      />,
    )
    const text = container.textContent ?? ''
    expect(text).not.toMatch(FORBIDDEN)
    // 1 blaze, the fixture's finish line of 5 (the ATC's own rule), and no
    // other number at all.
    expect(text.match(/\d+/g)).toEqual(['1', '5'])
  })

  it('shows 0 blazes on the day of joining, as a sentence rather than a gap', () => {
    const { container } = render(
      <ChallengeSeasonStrip
        challenge={ATC_CHALLENGE}
        state={earned()}
        today={TODAY}
        onOpen={vi.fn()}
      />,
    )
    expect(container.querySelector('.season__count')).toHaveTextContent('0 blazes')
    expect(container.querySelector('.season__where')).toBeNull()
  })
})
