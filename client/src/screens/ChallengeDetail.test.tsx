import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChallengeDetail, type ChallengeDetailProps } from './ChallengeDetail'
import { Challenges } from './Challenges'
import { ChallengeBrowse } from './ChallengeBrowse'
import { ATC_CHALLENGE, RECORD_CHALLENGE } from '../lib/challenges.fixtures'
import {
  EMPTY_CHALLENGE_STATE,
  join,
  tag,
  type ChallengeState,
} from '../lib/challengeProgress'

afterEach(cleanup)

// features/VOLUNTEERING.md §5 as the handoff restates it for challenges:
// never comparative, never a lack-state. A screen that grew any of these
// words has grown the thing the guardrail forbids.
const FORBIDDEN =
  /other hikers|behind|streak|\brank|leaderboard|you haven[’']t|left to go|remaining/i

const TODAY = '2027-07-14'
const item = (challenge: typeof ATC_CHALLENGE, id: string) =>
  challenge.items.find((entry) => entry.id === id)!

function joinedWith(challenge: typeof ATC_CHALLENGE, ...ids: string[]): ChallengeState {
  let state = join(EMPTY_CHALLENGE_STATE, challenge.id, new Date('2027-06-01T12:00:00Z'))
  for (const id of ids) {
    state = tag(state, challenge, item(challenge, id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how: 'hand',
    }).state
  }
  return state
}

function detail(overrides: Partial<ChallengeDetailProps> = {}) {
  const props: ChallengeDetailProps = {
    challenge: ATC_CHALLENGE,
    state: joinedWith(ATC_CHALLENGE, 'springer-mountain'),
    today: TODAY,
    walked: [],
    signedIn: false,
    onJoin: vi.fn(),
    onLeave: vi.fn(),
    onTag: vi.fn(),
    onUntag: vi.fn(),
    onSetNote: vi.fn(),
    onSendEntry: vi.fn(),
    ...overrides,
  }
  return { props, ...render(<ChallengeDetail {...props} />) }
}

describe('one challenge', () => {
  it('names a draft as a draft, in the label every surface carries', () => {
    detail()
    expect(screen.getByText('Draft · not yet confirmed by the ATC')).toBeInTheDocument()
  })

  it('counts against the club’s own finish line and nothing else', () => {
    detail()
    expect(screen.getByText(/1 of 5 for the drawing/)).toBeInTheDocument()
  })

  it('lists the named places south to north under On the trail', () => {
    const { container } = detail()
    const titles = [...container.querySelectorAll('.challenge-row__title')].map(
      (node) => node.textContent,
    )
    expect(titles[0]).toMatch(/Springer Mountain/)
    expect(titles.at(-1)).toMatch(/Katahdin/)
  })

  it('hands a hand-taggable row to onTag, and names the item on its button', async () => {
    const { props } = detail()
    await userEvent.click(
      screen.getByRole('button', { name: /Tag it: Take the McAfee Knob shuttle/ }),
    )
    expect(props.onTag).toHaveBeenCalledWith(item(ATC_CHALLENGE, 'mcafee-knob'))
  })

  it('never renders a sealed mystery title before its reveal date', async () => {
    detail({ today: '2027-07-19' })
    await userEvent.click(screen.getByRole('button', { name: 'Mystery' }))
    expect(screen.queryByText(/Jefferson Rock/)).toBeNull()
    expect(screen.getByText('Sealed until Jul 20')).toBeInTheDocument()
    expect(screen.getByText('Sealed · announced by the ATC')).toBeInTheDocument()
  })

  it('reveals a mystery title on its day, marked as a mystery', async () => {
    detail({ today: '2027-07-20' })
    await userEvent.click(screen.getByRole('button', { name: 'Mystery' }))
    expect(screen.getByText('Watch the sun set from Jefferson Rock.')).toBeInTheDocument()
    expect(screen.getByText(/Mystery #1 · revealed Jul 20/)).toBeInTheDocument()
  })

  it('offers Join, not tags, to a hiker who has not joined', () => {
    detail({ state: EMPTY_CHALLENGE_STATE })
    expect(screen.getByRole('button', { name: 'Join' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Tag it/ })).toBeNull()
  })

  it('never says anything comparative or about what is not done, in any filter', async () => {
    const { container } = detail()
    for (const pill of ['On the trail', 'Learn', 'Anywhere', 'Protect', 'Mystery']) {
      await userEvent.click(screen.getByRole('button', { name: pill }))
      expect(container.textContent).not.toMatch(FORBIDDEN)
    }
  })
})

describe('the finish', () => {
  const finished = () =>
    joinedWith(
      ATC_CHALLENGE,
      'springer-mountain',
      'mcafee-knob',
      'katahdin',
      'trivia-quiz',
      'pick-up-litter',
    )

  it('takes no entry for a draft, and says why in a sentence', async () => {
    detail({ state: finished(), signedIn: true })
    await userEvent.click(screen.getByRole('button', { name: 'Your finish' }))
    expect(
      screen.getByText(
        /The ATC has not confirmed this list yet, so there is nobody to send an entry to/,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Enter the drawing' })).toBeNull()
  })

  it('lists what the club would receive before a published challenge’s entry is sent', async () => {
    const published = {
      ...ATC_CHALLENGE,
      status: 'published' as const,
      window: { opens: null, closes: null },
    }
    const { props } = detail({ challenge: published, state: finished(), signedIn: true })
    await userEvent.click(screen.getByRole('button', { name: 'Your finish' }))
    const receives = screen
      .getByText('What the ATC receives')
      .closest('.challenge-receives') as HTMLElement
    expect(within(receives).getByText('Your name')).toBeInTheDocument()
    expect(
      within(receives).getByText(/No GPS track, no photos, no register lines/),
    ).toBeInTheDocument()

    const send = screen.getByRole('button', { name: 'Enter the drawing' })
    expect(send).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Name'), 'Sam Roe')
    await userEvent.type(screen.getByLabelText('Email'), 'sam@example.org')
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(send)
    expect(props.onSendEntry).toHaveBeenCalledWith(
      expect.objectContaining({
        challenge_id: published.id,
        name: 'Sam Roe',
        email: 'sam@example.org',
        consented: true,
      }),
    )
  })

  it('shows a record’s walk with no form and no sign-in, and never invents a name for the club', async () => {
    const state = joinedWith(RECORD_CHALLENGE, 'dragons-tooth', 'mcafee', 'tinker')
    const withFinish = { ...RECORD_CHALLENGE, finish: { count: 3, label: null } }
    const { props } = detail({ challenge: withFinish, state, signedIn: true })
    await userEvent.click(screen.getByRole('button', { name: 'See your finish' }))
    expect(
      screen.getByRole('heading', { name: /You walked Three Roanoke peaks/ }),
    ).toBeInTheDocument()
    await userEvent.click(
      screen.getByRole('button', { name: 'Let the club know you finished' }),
    )
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/Your name/), 'Sam Roe')
    await userEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(props.onSendEntry).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Sam Roe', finished_only: true, item_ids: [] }),
    )
  })
})

describe('the list of joined challenges', () => {
  it('draws the finish line as a count and a bar, and names a closing date rather than counting down', () => {
    const { container } = render(
      <Challenges
        joined={[ATC_CHALLENGE]}
        state={joinedWith(ATC_CHALLENGE, 'springer-mountain')}
        onOffer={1}
        onOpen={vi.fn()}
        onBrowse={vi.fn()}
      />,
    )
    expect(screen.getByText('ATC · until Sep 1')).toBeInTheDocument()
    expect(screen.getByText('1 of 5 for the drawing')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\bwk\b|weeks? left|days? left/i)
    expect(container.textContent).not.toMatch(FORBIDDEN)
  })

  it('shows no total across challenges', () => {
    const { container } = render(
      <Challenges
        joined={[ATC_CHALLENGE, RECORD_CHALLENGE]}
        state={join(
          joinedWith(ATC_CHALLENGE, 'springer-mountain'),
          RECORD_CHALLENGE.id,
          new Date(),
        )}
        onOffer={0}
        onOpen={vi.fn()}
        onBrowse={vi.fn()}
      />,
    )
    // Two cards, each in its own unit; no line anywhere adds them up.
    expect(container.querySelectorAll('.challenge-card')).toHaveLength(2)
    expect(container.textContent).not.toMatch(/total|in all|altogether/i)
  })
})

describe('Browse', () => {
  it('puts a challenge touching the plan first, with how many of its places the plan passes', () => {
    render(
      <ChallengeBrowse
        challenges={[ATC_CHALLENGE, RECORD_CHALLENGE]}
        state={EMPTY_CHALLENGE_STATE}
        chosenTrail="AT"
        days={[{ dayNumber: 1, startMile: 700, endMile: 725 }]}
        planName="Pearisburg → Daleville"
        today={TODAY}
        units="imperial"
        onOpen={vi.fn()}
        onJoin={vi.fn()}
      />,
    )
    expect(screen.getByText('On your plan · Pearisburg → Daleville')).toBeInTheDocument()
    expect(screen.getByText('4 places on your plan')).toBeInTheDocument()
  })

  it('says nothing about how many hikers joined anything', () => {
    const { container } = render(
      <ChallengeBrowse
        challenges={[ATC_CHALLENGE, RECORD_CHALLENGE]}
        state={EMPTY_CHALLENGE_STATE}
        chosenTrail="AT"
        days={[]}
        planName={null}
        today={TODAY}
        units="imperial"
        onOpen={vi.fn()}
        onJoin={vi.fn()}
      />,
    )
    expect(container.textContent).not.toMatch(/hikers?\b|popular|joined by|people/i)
    expect(container.textContent).not.toMatch(FORBIDDEN)
  })
})
