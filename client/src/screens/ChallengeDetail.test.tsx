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

  it('opens on the club’s first section and numbers every row 1-100 in the club’s order', async () => {
    const { container } = detail()
    const numbersShown = () =>
      [...container.querySelectorAll('.challenge-row__number')].map((node) =>
        Number(node.textContent),
      )
    // Learn is the ATC's first section, so the first row is the first item.
    expect(screen.getByRole('button', { name: 'Learn' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    const learn = ATC_CHALLENGE.items.filter((entry) => entry.section === 'learn')
    expect(numbersShown()).toEqual(
      learn.map((entry) => ATC_CHALLENGE.items.indexOf(entry) + 1),
    )
    // Experience keeps the published order too - never re-sorted by mile.
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    const experience = ATC_CHALLENGE.items.filter(
      (entry) => entry.section === 'experience',
    )
    expect(numbersShown()).toEqual(
      experience.map((entry) => ATC_CHALLENGE.items.indexOf(entry) + 1),
    )
    expect(screen.queryByRole('button', { name: 'On the trail' })).toBeNull()
  })

  it('lists only what is earned under Done, and draws no Done pill before anything is', async () => {
    const { container } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Done' }))
    const titles = [...container.querySelectorAll('.challenge-row__title')].map(
      (node) => node.textContent,
    )
    expect(titles).toHaveLength(1)
    expect(titles[0]).toMatch(/Springer Mountain/)
    cleanup()
    detail({ state: join(EMPTY_CHALLENGE_STATE, ATC_CHALLENGE.id, new Date()) })
    expect(screen.queryByRole('button', { name: 'Done' })).toBeNull()
  })

  it('prints no sub-line under an at-home item, and a place under a place', async () => {
    const { container } = detail()
    const row = (title: RegExp) =>
      [...container.querySelectorAll('.challenge-row')].find((node) =>
        title.test(node.querySelector('.challenge-row__title')?.textContent ?? ''),
      )!
    expect(row(/trivia quiz/).querySelector('.challenge-row__meta')).toBeNull()
    expect(container.textContent).not.toMatch(/at home/)
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    expect(
      row(/McAfee Knob shuttle/).querySelector('.challenge-row__meta'),
    ).toHaveTextContent('McAfee Knob Summit')
  })

  it('hands a hand-earnable row to onTag, and names the item on its button', async () => {
    const { props } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    await userEvent.click(
      screen.getByRole('button', { name: /Earn it: Take the McAfee Knob shuttle/ }),
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

  it('offers Join, not Earn it, to a hiker who has not joined', () => {
    detail({ state: EMPTY_CHALLENGE_STATE })
    expect(screen.getByRole('button', { name: 'Join' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Earn it/ })).toBeNull()
  })

  it('never says anything comparative or about what is not done, in any filter', async () => {
    const { container } = detail()
    for (const pill of ['Learn', 'Experience', 'Protect', 'Mystery', 'Done']) {
      await userEvent.click(screen.getByRole('button', { name: pill }))
      expect(container.textContent).not.toMatch(FORBIDDEN)
    }
  })
})

describe('the blaze card in the header (#1962)', () => {
  it('draws the card with no tile button at its own size, and a section tap picks that pill', async () => {
    const { container } = detail()
    expect(container.querySelector('.blaze-card--card')).not.toBeNull()
    expect(container.querySelectorAll('button.blaze-tile')).toHaveLength(0)
    expect(container.querySelector('.challenge-strip')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /^Protect the A\.T\., / }))
    expect(screen.getByRole('button', { name: 'Protect' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('makes the tiles buttons only when made bigger, and a tile opens its own sheet', async () => {
    const { container } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Bigger tiles' }))
    expect(container.querySelector('.blaze-card--expanded')).not.toBeNull()
    expect(container.querySelectorAll('button.blaze-tile').length).toBe(
      ATC_CHALLENGE.items.length,
    )
    await userEvent.click(
      screen.getByRole('button', { name: /^Take the McAfee Knob shuttle/ }),
    )
    expect(
      screen.getByRole('dialog', { name: /Take the McAfee Knob shuttle/ }),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    await userEvent.click(screen.getByRole('button', { name: 'Smaller tiles' }))
    expect(container.querySelectorAll('button.blaze-tile')).toHaveLength(0)
  })
})

describe('earning from the list asks where only when it can mean something (#1963)', () => {
  const blazePhoto = () => item(ATC_CHALLENGE, 'white-blaze-photo')

  it('earns a couch item with one tap and no question', async () => {
    const { props } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Learn' }))
    await userEvent.click(
      screen.getByRole('button', { name: /Earn it: Take our A\.T\. trivia/ }),
    )
    expect(props.onTag).toHaveBeenCalledWith(
      item(ATC_CHALLENGE, 'trivia-quiz'),
      undefined,
    )
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('asks where for an on-trail at-home item, opening on "On the trail, somewhere" with no fix', async () => {
    const { props } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    await userEvent.click(
      screen.getByRole('button', { name: /Earn it: Take a photo of a white blaze/ }),
    )
    expect(props.onTag).not.toHaveBeenCalled()
    const sheet = screen.getByRole('dialog', { name: 'Where did it happen?' })
    expect(within(sheet).queryByRole('button', { name: /^Here/ })).toBeNull()
    expect(sheet.textContent).not.toMatch(/location/i)
    await userEvent.selectOptions(
      within(sheet).getByRole('combobox', { name: 'Which state' }),
      'VA',
    )
    await userEvent.click(within(sheet).getByRole('button', { name: 'Earn it here' }))
    expect(props.onTag).toHaveBeenCalledWith(blazePhoto(), undefined, {
      kind: 'state',
      state: 'VA',
    })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('offers Here when the shell has a fix inside the corridor, and hands its mile back', async () => {
    const { props } = detail({ fixMile: 714.9 })
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    await userEvent.click(
      screen.getByRole('button', { name: /Earn it: Take a photo of a white blaze/ }),
    )
    const sheet = screen.getByRole('dialog', { name: 'Where did it happen?' })
    expect(within(sheet).getByRole('button', { name: /^Here/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await userEvent.click(within(sheet).getByRole('button', { name: 'Earn it here' }))
    expect(props.onTag).toHaveBeenCalledWith(blazePhoto(), undefined, {
      kind: 'here',
      mile: 714.9,
    })
  })

  it('earns from the tile through the same question, and Back leaves nothing earned', async () => {
    const { props } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    const row = screen
      .getAllByRole('button', { name: /Take a photo of a white blaze/ })
      .find((button) => button.classList.contains('challenge-row__open'))!
    await userEvent.click(row)
    await userEvent.click(screen.getByRole('button', { name: 'Earn some karma' }))
    const sheet = screen.getByRole('dialog', { name: 'Where did it happen?' })
    await userEvent.click(within(sheet).getByRole('button', { name: '‹ Back' }))
    expect(props.onTag).not.toHaveBeenCalled()
    expect(
      screen.getByRole('dialog', { name: /Take a photo of a white blaze/ }),
    ).toBeInTheDocument()
  })
})

describe('the entry from day one (#1964)', () => {
  it('opens Your entry at 1 of 25 with what the club receives, the one-entry rule and when it opens, and no form', async () => {
    const { props } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Your entry' }))
    expect(screen.getByText(/What the ATC receives/)).toBeInTheDocument()
    expect(
      screen.getByText(/One entry per person — use the email you signed up with/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Each mystery item has a drawing of its own/),
    ).toBeInTheDocument()
    expect(screen.getByText(/The entry opens at 5 for the drawing/)).toBeInTheDocument()
    expect(screen.getByText(/Nothing has been sent/)).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('button', { name: /Enter the drawing/ })).toBeNull()
    expect(props.onSendEntry).not.toHaveBeenCalled()
    expect(document.body.textContent).not.toMatch(FORBIDDEN)
  })

  it('shows a sealed mystery item’s teaser under its sealed line, never its title', async () => {
    detail({ today: '2027-07-19' })
    await userEvent.click(screen.getByRole('button', { name: 'Mystery' }))
    expect(screen.getByText('Something to do before the sun is up.')).toBeInTheDocument()
    expect(screen.queryByText(/Jefferson Rock/)).toBeNull()
    cleanup()
    detail({ today: '2027-07-20' })
    await userEvent.click(screen.getByRole('button', { name: 'Mystery' }))
    expect(screen.queryByText('Something to do before the sun is up.')).toBeNull()
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
    expect(screen.getByText('ATC · until Sep 7')).toBeInTheDocument()
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

// From the reviews of 2026-09-30 and 2026-10-01 (features/CHALLENGES.md, "The
// reviews"): the places a hiker could fall through on these screens.
describe('the window, Triple Crown peaks, the earned-place sheet and a closed list', () => {
  it('offers nothing to earn outside the window, and says when it opens', () => {
    detail({ today: '2027-05-01' })
    expect(screen.queryByRole('button', { name: /^Earn it/ })).toBeNull()
    expect(
      screen.getByText(/Opens May 13\. Trail karma counts from then\./),
    ).toBeInTheDocument()
  })

  it('tells a hiker who has not joined when the list opens, too', () => {
    detail({ today: '2027-05-01', state: EMPTY_CHALLENGE_STATE })
    expect(screen.getByRole('button', { name: 'Join' })).toBeInTheDocument()
    expect(
      screen.getByText(/Opens May 13\. Trail karma counts from then\./),
    ).toBeInTheDocument()
  })

  it('offers each peak of a Triple Crown its own Earn it, before the item is done', async () => {
    const { props } = detail()
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    const crown = item(ATC_CHALLENGE, 'virginia-triple-crown')
    const peaks = crown.match.kind === 'places_all' ? crown.match.places : []
    await userEvent.click(
      screen.getByRole('button', { name: `Earn it: ${peaks[1].name}` }),
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

  it('opens the earned place with focus on it, closes on Escape, and gives focus back', async () => {
    detail({
      state: joinedWith(ATC_CHALLENGE, 'springer-mountain'),
      onRemoveTag: vi.fn(),
    })
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
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

  it('takes an earned item back from its place with one tap, however it was made', async () => {
    const state = tag(
      join(EMPTY_CHALLENGE_STATE, ATC_CHALLENGE.id, new Date('2027-06-01T12:00:00Z')),
      ATC_CHALLENGE,
      item(ATC_CHALLENGE, 'mcafee-knob'),
      { at: new Date('2027-07-02T15:00:00Z'), how: 'gps' },
    ).state
    const onRemoveTag = vi.fn()
    detail({ state, onRemoveTag })
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    await userEvent.click(
      screen.getByRole('button', { name: /Take the McAfee Knob shuttle/ }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Take it back' }))
    expect(onRemoveTag).toHaveBeenCalledWith(
      item(ATC_CHALLENGE, 'mcafee-knob'),
      undefined,
    )
  })

  it('gives focus back to the row after Take it back, which stays a button (#1963)', async () => {
    // Every row opens its tile now, earned or not, so the button that opened
    // the sheet is still there after the earned item is taken back and focus goes
    // back to it - never to <body>.
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
    await userEvent.click(screen.getByRole('button', { name: 'Experience' }))
    await userEvent.click(
      screen.getByRole('button', { name: /Take the McAfee Knob shuttle/ }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Take it back' }))
    const row = screen
      .getAllByRole('button', { name: /Take the McAfee Knob shuttle/ })
      .find((button) => button.classList.contains('challenge-row__open'))!
    expect(row).toHaveFocus()
    expect(document.activeElement).not.toBe(document.body)
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
    // Read with the field, not only beside it.
    expect(screen.getByRole('textbox', { name: /email/i })).toHaveAccessibleDescription(
      'That does not look like an email address.',
    )
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
    expect(screen.getByText('ATC · opens May 13')).toBeInTheDocument()
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
