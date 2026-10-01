import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChallengeCampCard } from './ChallengeCampCard'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import {
  EMPTY_CHALLENGE_STATE,
  campCardShows,
  dayHasEnded,
  join,
  joinedChallenges,
  matchDay,
} from '../lib/challengeProgress'

afterEach(cleanup)

const TODAY = '2027-07-14'
const state = join(
  EMPTY_CHALLENGE_STATE,
  ATC_CHALLENGE.id,
  new Date('2027-06-01T12:00:00Z'),
)
const SHELTERS = [
  { id: 'atc_shelters:campbell', type: 'shelter', name: 'Campbell Shelter', mile: 713.9 },
]

function passed(startMile: number, endMile: number) {
  return matchDay({
    joined: joinedChallenges([ATC_CHALLENGE], state),
    state,
    todayRanges: [{ startMile, endMile }],
    trail: 'AT',
    pois: SHELTERS,
    today: TODAY,
  })
}

describe('the camp card', () => {
  it('lists only the places the day passed, with their miles', () => {
    render(
      <ChallengeCampCard
        candidates={passed(710, 716)}
        today={TODAY}
        onTagAll={vi.fn()}
        onNotTonight={vi.fn()}
      />,
    )
    expect(screen.getByText('From today’s walk')).toBeInTheDocument()
    expect(screen.getByText(/Take the McAfee Knob shuttle/)).toBeInTheDocument()
    expect(screen.getByText('Campbell Shelter')).toBeInTheDocument()
    // Katahdin, Springer and every town are on the list and were not passed.
    expect(screen.queryByText(/Katahdin|Springer|Monson/)).toBeNull()
  })

  it('carries no numeral for anything missed, and no count of the day at all', () => {
    const { container } = render(
      <ChallengeCampCard
        candidates={passed(710, 716)}
        today={TODAY}
        onTagAll={vi.fn()}
        onNotTonight={vi.fn()}
      />,
    )
    // The only digits on the card are the mile markers of what was passed.
    const withoutMiles = (container.textContent ?? '').replace(/mi [\d,.]+/g, '')
    expect(withoutMiles).not.toMatch(/\d/)
    expect(container.textContent).not.toMatch(/missed|skipped|you haven[’']t|left/i)
  })

  it('renders nothing when nothing was passed', () => {
    const { container } = render(
      <ChallengeCampCard
        candidates={passed(1000, 1001)}
        today={TODAY}
        onTagAll={vi.fn()}
        onNotTonight={vi.fn()}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('answers with Tag all or Not tonight', async () => {
    const onTagAll = vi.fn()
    const onNotTonight = vi.fn()
    render(
      <ChallengeCampCard
        candidates={passed(710, 716)}
        today={TODAY}
        onTagAll={onTagAll}
        onNotTonight={onNotTonight}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Tag all' }))
    await userEvent.click(screen.getByRole('button', { name: 'Not tonight' }))
    expect(onTagAll).toHaveBeenCalledOnce()
    expect(onNotTonight).toHaveBeenCalledOnce()
  })
})

describe('when Today asks', () => {
  const candidates = passed(710, 716)

  it('asks only once the day is over', () => {
    expect(
      campCardShows({ dayEnded: false, answeredDay: null, today: TODAY, candidates }),
    ).toBe(false)
    expect(
      campCardShows({ dayEnded: true, answeredDay: null, today: TODAY, candidates }),
    ).toBe(true)
  })

  it('does not ask again after Not tonight, until tomorrow', () => {
    expect(
      campCardShows({ dayEnded: true, answeredDay: TODAY, today: TODAY, candidates }),
    ).toBe(false)
    expect(
      campCardShows({
        dayEnded: true,
        answeredDay: TODAY,
        today: '2027-07-15',
        candidates,
      }),
    ).toBe(true)
  })

  it('never asks about nothing', () => {
    expect(
      campCardShows({ dayEnded: true, answeredDay: null, today: TODAY, candidates: [] }),
    ).toBe(false)
  })

  it('counts a called day or a logged walk as over, and otherwise waits for the evening', () => {
    const noon = new Date('2027-07-14T12:00:00')
    const evening = new Date('2027-07-14T19:00:00')
    expect(dayHasEnded({ now: noon, calledToday: false, walkLoggedToday: false })).toBe(
      false,
    )
    expect(dayHasEnded({ now: noon, calledToday: true, walkLoggedToday: false })).toBe(
      true,
    )
    expect(dayHasEnded({ now: noon, calledToday: false, walkLoggedToday: true })).toBe(
      true,
    )
    expect(
      dayHasEnded({ now: evening, calledToday: false, walkLoggedToday: false }),
    ).toBe(true)
  })
})

describe('the camp card, read aloud', () => {
  it('asks in a heading, and labels a draft list as a draft', () => {
    render(
      <ChallengeCampCard
        candidates={passed(710, 716)}
        today={TODAY}
        onTagAll={vi.fn()}
        onNotTonight={vi.fn()}
      />,
    )
    expect(screen.getByRole('heading', { name: /You passed places/ })).toBeInTheDocument()
    expect(
      screen.getAllByText('Draft · not yet confirmed by the ATC').length,
    ).toBeGreaterThan(0)
  })
})
