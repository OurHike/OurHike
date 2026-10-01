import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PoiChallenges } from './PoiChallenges'
import { ATC_CHALLENGE, RECORD_CHALLENGE } from '../lib/challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag } from '../lib/challengeProgress'

afterEach(cleanup)

const MCAFEE = 'atc_viewpoints:95a18f95-b78f-43bb-843a-4b9b82fecb76'
const TODAY = '2027-07-14'
const joined = join(
  EMPTY_CHALLENGE_STATE,
  ATC_CHALLENGE.id,
  new Date('2027-06-01T12:00:00Z'),
)

function card(state = joined, onTag = vi.fn(), onJoin = vi.fn()) {
  render(
    <PoiChallenges
      poiIds={[MCAFEE]}
      challenges={[ATC_CHALLENGE, RECORD_CHALLENGE]}
      state={state}
      today={TODAY}
      onTag={onTag}
      onUntag={vi.fn()}
      onJoin={onJoin}
    />,
  )
  return { onTag, onJoin }
}

describe('a place card’s challenges', () => {
  it('lists each item at this place on a joined list, credited to its club', () => {
    card()
    expect(
      screen.getByRole('heading', { name: 'On the A.T. Summer Bucket List' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Take the McAfee Knob shuttle/)).toBeInTheDocument()
    expect(screen.getByText(/Hike the “Triple Crown” of Virginia/)).toBeInTheDocument()
    expect(screen.getAllByText('A.T. Summer Bucket List · ATC')).toHaveLength(2)
  })

  it('tags the place it is on - for a Triple Crown, this peak', async () => {
    const { onTag } = card()
    await userEvent.click(
      screen.getByRole('button', { name: /Tag it: Hike the “Triple Crown”/ }),
    )
    expect(onTag).toHaveBeenCalledWith(
      ATC_CHALLENGE,
      ATC_CHALLENGE.items.find((item) => item.id === 'virginia-triple-crown'),
      MCAFEE,
    )
  })

  it('reads "done" where the day’s walk tagged it, rather than offering a pill', () => {
    const walked = tag(
      joined,
      ATC_CHALLENGE,
      ATC_CHALLENGE.items.find((item) => item.id === 'mcafee-knob')!,
      {
        at: new Date(),
        how: 'gps',
      },
    ).state
    card(walked)
    expect(screen.getByText('done')).toBeInTheDocument()
  })

  it('offers to join a list the hiker is not on, and nothing else about it', async () => {
    const { onJoin } = card()
    await userEvent.click(
      screen.getByRole('button', { name: 'Join Three Roanoke peaks (test)' }),
    )
    expect(onJoin).toHaveBeenCalledWith(RECORD_CHALLENGE.id)
  })

  it('draws nothing for a place on no list', () => {
    const { container } = render(
      <PoiChallenges
        poiIds={['atc_shelters:elsewhere']}
        challenges={[ATC_CHALLENGE]}
        state={joined}
        today={TODAY}
        onTag={vi.fn()}
        onUntag={vi.fn()}
        onJoin={vi.fn()}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})

describe('a place card, before and after joining', () => {
  it('lets a hiker read a list before joining it', async () => {
    const onOpen = vi.fn()
    render(
      <PoiChallenges
        poiIds={[MCAFEE]}
        challenges={[ATC_CHALLENGE]}
        state={EMPTY_CHALLENGE_STATE}
        today={TODAY}
        onTag={vi.fn()}
        onUntag={vi.fn()}
        onJoin={vi.fn()}
        onOpen={onOpen}
      />,
    )
    await userEvent.click(
      screen.getByRole('button', { name: /On the A\.T\. Summer Bucket List/ }),
    )
    expect(onOpen).toHaveBeenCalledWith(ATC_CHALLENGE.id)
  })
})
