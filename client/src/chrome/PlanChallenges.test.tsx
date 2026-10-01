import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PlanChallenges } from './PlanChallenges'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import {
  EMPTY_CHALLENGE_STATE,
  join,
  planRows,
  suggestion,
} from '../lib/challengeProgress'

afterEach(cleanup)

const TODAY = '2027-07-14'
const DAYS = [
  { dayNumber: 5, startMile: 699, endMile: 713.9 },
  { dayNumber: 6, startMile: 713.9, endMile: 728 },
]
// Plan.test.tsx's standing rule, carried onto this card: no rendering of a
// plan may contain "behind", "ahead of" or a score.
const SCORING = /%|behind|ahead of|on track|streak|complete/i

describe('a plan’s challenge places', () => {
  it('lays a joined challenge’s places on their days, with their miles', () => {
    const { container } = render(
      <PlanChallenges
        rows={planRows(ATC_CHALLENGE, DAYS, TODAY)}
        state={join(EMPTY_CHALLENGE_STATE, ATC_CHALLENGE.id, new Date())}
        suggestion={null}
        today={TODAY}
        onJoin={vi.fn()}
        onHide={vi.fn()}
        onOpen={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'Challenge places on this route' }),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Day 6').length).toBeGreaterThan(0)
    expect(
      screen.getByText(
        'Every place of “Hike the “Triple Crown” of Virginia: McAfee Knob, Tinker Cliffs, and Dragon’s Tooth.” is on this route.',
      ),
    ).toBeInTheDocument()
    expect(container.textContent).not.toMatch(SCORING)
  })

  it('suggests one challenge, three rows and how many more, with Join and Hide', async () => {
    const picked = suggestion({
      challenges: [ATC_CHALLENGE],
      state: EMPTY_CHALLENGE_STATE,
      days: DAYS,
      hikeKey: 'trip-1',
      today: TODAY,
      maintainedMiles: () => 0,
    })
    const onJoin = vi.fn()
    const onHide = vi.fn()
    const { container } = render(
      <PlanChallenges
        rows={[]}
        state={EMPTY_CHALLENGE_STATE}
        suggestion={picked}
        today={TODAY}
        onJoin={onJoin}
        onHide={onHide}
        onOpen={vi.fn()}
      />,
    )
    expect(screen.getByText('Challenge on your route')).toBeInTheDocument()
    expect(container.querySelectorAll('.challenge-plan__row')).toHaveLength(3)
    expect(screen.getByText('+1 more on this hike')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Join' }))
    await userEvent.click(screen.getByRole('button', { name: 'Hide' }))
    expect(onJoin).toHaveBeenCalledWith(ATC_CHALLENGE.id)
    expect(onHide).toHaveBeenCalledWith(ATC_CHALLENGE.id)
    expect(container.textContent).not.toMatch(SCORING)
  })
})

describe('the suggestion, read before joining', () => {
  it('opens the challenge from its name and from "more"', async () => {
    const picked = suggestion({
      challenges: [ATC_CHALLENGE],
      state: EMPTY_CHALLENGE_STATE,
      days: DAYS,
      hikeKey: 'trip-1',
      today: TODAY,
      maintainedMiles: () => 0,
    })
    const onOpen = vi.fn()
    render(
      <PlanChallenges
        rows={[]}
        state={EMPTY_CHALLENGE_STATE}
        suggestion={picked}
        today={TODAY}
        onJoin={vi.fn()}
        onHide={vi.fn()}
        onOpen={onOpen}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: ATC_CHALLENGE.name }))
    expect(onOpen).toHaveBeenCalledWith(ATC_CHALLENGE.id)
  })
})
