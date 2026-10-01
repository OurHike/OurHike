import { afterEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChallengeDetail, type ChallengeDetailProps } from './ChallengeDetail'
import { Challenges } from './Challenges'
import { ChallengeBrowse } from './ChallengeBrowse'
import { ATC_CHALLENGE, RECORD_CHALLENGE } from '../lib/challenges.fixtures'
import {
  EMPTY_CHALLENGE_STATE,
  join,
  removeTag,
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
    expect(props.onTag).toHaveBeenCalledWith(
      item(ATC_CHALLENGE, 'mcafee-knob'),
      undefined,
    )
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
        /The ATC has not confirmed this list yet, so there is nobody to send anything to/,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Enter the drawing' })).toBeNull()
  })

  it('lists what the club would receive before a published challenge’s entry is sent', async () => {
    const published = {
      ...ATC_CHALLENGE,
      status: 'published' as const,
      takesEntries: true,
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
        // The publisher's domain, which the server makes the club prove.
        org_domain: 'appalachiantrail.org',
        name: 'Sam Roe',
        email: 'sam@example.org',
        consented: true,
      }),
    )
  })

  it('shows a record’s walk with no form and no sign-in, and never invents a name for the club', async () => {
    const state = joinedWith(RECORD_CHALLENGE, 'dragons-tooth', 'mcafee', 'tinker')
    const withFinish = {
      ...RECORD_CHALLENGE,
      status: 'published' as const,
      finish: { count: 3, label: null },
    }
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
        today={TODAY}
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

// The adversarial review of 2026-09-30 (features/CHALLENGES.md): the holes a
// hiker could fall into on these screens, each held closed.
describe('holes the review found, closed', () => {
  it('offers no new tag outside the window, and says when it opens', () => {
    detail({ today: '2027-05-01' })
    expect(screen.queryByRole('button', { name: /^Tag it/ })).toBeNull()
    expect(screen.getByText(/Opens May 15\. Tags count from then\./)).toBeInTheDocument()
  })

  it('offers each peak of a Triple Crown its own Tag it, before the item is done', async () => {
    const { props } = detail()
    const crown = item(ATC_CHALLENGE, 'virginia-triple-crown')
    const peaks = crown.match.kind === 'places_all' ? crown.match.places : []
    await userEvent.click(
      screen.getByRole('button', { name: `Tag it: ${peaks[1].name}` }),
    )
    expect(props.onTag).toHaveBeenCalledWith(crown, peaks[1].poi)
  })

  it('asks before leaving, and leaves only on the second press', async () => {
    const { props } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Leave this challenge' }))
    expect(props.onLeave).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Stay' }))
    await userEvent.click(screen.getByRole('button', { name: 'Leave this challenge' }))
    await userEvent.click(screen.getByRole('button', { name: 'Leave' }))
    expect(props.onLeave).toHaveBeenCalledTimes(1)
  })

  it('opens the tagged place with focus on it, closes on Escape, and gives focus back', async () => {
    detail({
      state: joinedWith(ATC_CHALLENGE, 'springer-mountain'),
      onRemoveTag: vi.fn(),
    })
    const row = screen
      .getAllByRole('button', { name: /Springer Mountain/ })
      .find((button) => button.classList.contains('challenge-row__open'))!
    await userEvent.click(row)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(row).toHaveFocus()
  })

  it('takes a tag back from the tagged place, however it was made', async () => {
    const state = tag(
      join(EMPTY_CHALLENGE_STATE, ATC_CHALLENGE.id, new Date('2027-06-01T12:00:00Z')),
      ATC_CHALLENGE,
      item(ATC_CHALLENGE, 'mcafee-knob'),
      { at: new Date('2027-07-02T15:00:00Z'), how: 'gps' },
    ).state
    const onRemoveTag = vi.fn()
    detail({ state, onRemoveTag })
    await userEvent.click(
      screen.getByRole('button', { name: /Take the McAfee Knob shuttle/ }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Remove this tag' }))
    expect(onRemoveTag).toHaveBeenCalledWith(
      item(ATC_CHALLENGE, 'mcafee-knob'),
      undefined,
    )
  })

  it('puts focus on the title when Remove takes the row it came from away', async () => {
    // The removal re-renders the row as text, so the button that opened the
    // sheet is gone; focus must not fall to <body>.
    const start = tag(
      join(EMPTY_CHALLENGE_STATE, ATC_CHALLENGE.id, new Date('2027-06-01T12:00:00Z')),
      ATC_CHALLENGE,
      item(ATC_CHALLENGE, 'mcafee-knob'),
      { at: new Date('2027-07-02T15:00:00Z'), how: 'gps' },
    ).state
    function Harness() {
      const [state, setState] = useState(start)
      return (
        <ChallengeDetail
          challenge={ATC_CHALLENGE}
          state={state}
          today={TODAY}
          walked={[]}
          signedIn={false}
          onJoin={vi.fn()}
          onLeave={vi.fn()}
          onTag={vi.fn()}
          onUntag={vi.fn()}
          onSetNote={vi.fn()}
          onSendEntry={vi.fn()}
          onRemoveTag={(removed, poi) =>
            setState((current) => removeTag(current, ATC_CHALLENGE.id, removed.id, poi))
          }
        />
      )
    }
    render(<Harness />)
    await userEvent.click(
      screen.getByRole('button', { name: /Take the McAfee Knob shuttle/ }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Remove this tag' }))
    expect(
      screen.getByRole('heading', { level: 1, name: ATC_CHALLENGE.name }),
    ).toHaveFocus()
  })

  it('says why a record cannot tell its club after the window closed, rather than going quiet', async () => {
    const state = joinedWith(RECORD_CHALLENGE, 'dragons-tooth', 'mcafee', 'tinker')
    const closed = {
      ...RECORD_CHALLENGE,
      window: { opens: null, closes: '2027-07-01' },
      finish: { count: 3, label: null },
    }
    detail({ challenge: closed, state, signedIn: true })
    await userEvent.click(screen.getByRole('button', { name: 'See your finish' }))
    expect(screen.getByText('Entries closed on Jul 1.')).toBeInTheDocument()
  })

  it('points at the club’s own rules when it does not take entries through OurHike', async () => {
    const published = {
      ...ATC_CHALLENGE,
      status: 'published' as const,
      window: { opens: null, closes: null },
    }
    detail({
      challenge: published,
      state: joinedWith(
        ATC_CHALLENGE,
        'springer-mountain',
        'mcafee-knob',
        'katahdin',
        'trivia-quiz',
        'pick-up-litter',
      ),
      signedIn: true,
    })
    await userEvent.click(screen.getByRole('button', { name: 'Your finish' }))
    expect(screen.getByText(/collects entries itself/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Email')).toBeNull()
  })

  it('shows a refused entry’s reason and gives the form back, rather than saying it went', async () => {
    const published = {
      ...ATC_CHALLENGE,
      status: 'published' as const,
      takesEntries: true,
      window: { opens: null, closes: null },
    }
    const base = joinedWith(
      ATC_CHALLENGE,
      'springer-mountain',
      'mcafee-knob',
      'katahdin',
      'trivia-quiz',
      'pick-up-litter',
    )
    const state = {
      ...base,
      sent: [
        {
          challengeId: ATC_CHALLENGE.id,
          at: '2027-07-14T20:00:00Z',
          kind: 'entry' as const,
          outboxId: 'q1',
        },
      ],
    }
    const onForgetEntry = vi.fn()
    detail({
      challenge: published,
      state,
      signedIn: true,
      entryState: {
        kind: 'refused',
        reason: 'Entries for this challenge closed on September 1, 2027.',
      },
      onForgetEntry,
    })
    await userEvent.click(screen.getByRole('button', { name: 'Your finish' }))
    expect(
      screen.getByText(/did not take it: Entries for this challenge closed/),
    ).toBeInTheDocument()
    expect(screen.queryByText(/^Sent /)).toBeNull()
    await userEvent.click(
      screen.getByRole('button', { name: 'Change it and send again' }),
    )
    expect(onForgetEntry).toHaveBeenCalled()
  })

  it('refuses an address the server would refuse before it leaves the phone', async () => {
    const published = {
      ...ATC_CHALLENGE,
      status: 'published' as const,
      takesEntries: true,
      window: { opens: null, closes: null },
    }
    detail({
      challenge: published,
      state: joinedWith(
        ATC_CHALLENGE,
        'springer-mountain',
        'mcafee-knob',
        'katahdin',
        'trivia-quiz',
        'pick-up-litter',
      ),
      signedIn: true,
    })
    await userEvent.click(screen.getByRole('button', { name: 'Your finish' }))
    await userEvent.type(screen.getByLabelText('Name'), 'Sam Roe')
    await userEvent.type(screen.getByLabelText('Email'), 'sam@gmail')
    await userEvent.click(screen.getByRole('checkbox'))
    expect(screen.getByRole('button', { name: 'Enter the drawing' })).toBeDisabled()
    expect(
      screen.getByText('That does not look like an email address.'),
    ).toBeInTheDocument()
  })
})

describe('the list, when the published list changes under it', () => {
  it('says a joined challenge left the published list, rather than shrinking silently', () => {
    render(
      <Challenges
        joined={[]}
        state={EMPTY_CHALLENGE_STATE}
        today={TODAY}
        missing={1}
        onOffer={0}
        onOpen={vi.fn()}
        onBrowse={vi.fn()}
      />,
    )
    expect(screen.getByText(/no longer in the published list/)).toBeInTheDocument()
  })

  it('names a window that has not opened as opening, not as "until"', () => {
    render(
      <Challenges
        joined={[ATC_CHALLENGE]}
        state={join(EMPTY_CHALLENGE_STATE, ATC_CHALLENGE.id, new Date())}
        today="2027-01-10"
        onOffer={0}
        onOpen={vi.fn()}
        onBrowse={vi.fn()}
      />,
    )
    expect(screen.getByText('ATC · opens May 15')).toBeInTheDocument()
  })
})

describe('Browse, empty', () => {
  it('offers a way out when the filters leave nothing', async () => {
    render(
      <ChallengeBrowse
        challenges={[ATC_CHALLENGE]}
        state={EMPTY_CHALLENGE_STATE}
        chosenTrail={null}
        days={[]}
        planName={null}
        today="2030-01-01"
        units="imperial"
        onOpen={vi.fn()}
        onJoin={vi.fn()}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Open now' }))
    expect(screen.getByText(/Nothing matches these filters/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show every challenge' }))
    expect(screen.getByText(ATC_CHALLENGE.name)).toBeInTheDocument()
  })
})
