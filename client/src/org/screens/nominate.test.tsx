/**
 * The two screens where a hiker offers somebody else's data and a club answers.
 *
 * The property worth a test is not that they render. It is that **the review
 * step is real** - the maintainer's 2026-09-17 condition on harvesting a club's
 * contacts was that the hiker keeps or abandons each one, and the backend
 * implements that literally by storing nothing until the submit. A screen that
 * listed three contacts nobody could uncheck would satisfy the letter of that
 * and none of its substance, and no test that only looked for the names would
 * notice.
 *
 * The second is the refusal. A screen that buries "no thank you" is a screen
 * that collects consent from people who gave up.
 */

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Nominate } from './Nominate'
import { Proposal } from './Proposal'
import { orgApi, type NominateReading, type Proposal as ProposalView } from '../orgApi'

const READING: NominateReading = {
  website: 'https://carolinamountainclub.org',
  read_at_all: true,
  pages_read: 3,
  org_name: 'Carolina Mountain Club',
  summary: 'Asheville, NC.',
  sources: [
    {
      label: 'ArcGIS FeatureServer',
      url: 'https://services.arcgis.com/abc/CMC_Trails/FeatureServer/0',
      verdict: 'usable',
      detail: '214 line features',
    },
  ],
  contacts: [
    {
      name: 'Dale Whitford',
      role: 'Volunteer coordinator',
      email: 'volunteers@carolinamountainclub.org',
      source_page: 'https://carolinamountainclub.org/get-involved',
    },
    {
      name: 'Priya Raghavan',
      role: 'GIS',
      email: 'maps@carolinamountainclub.org',
      source_page: 'https://carolinamountainclub.org/maps',
    },
  ],
  membership_url: null,
  donation_url: null,
  licence_note: null,
  tokens_used: 160,
}

const PROPOSAL: ProposalView = {
  org_name: 'Carolina Mountain Club',
  website: 'https://carolinamountainclub.org',
  proposed_by_display: 'A hiker on OurHike',
  proposed_at: '2026-09-17T10:00:00Z',
  sources: READING.sources,
  contacts: READING.contacts.map((contact) => ({ ...contact, responded: false })),
  approvals_required: 3,
  approvals_so_far: 0,
  state: 'emailed',
}

// This suite runs with `globals: false`, which is what stops Testing
// Library registering its own auto-cleanup - so without this every render
// stacks on the last one and `getByRole` finds two of everything.
afterEach(cleanup)

/** The prefill `/for-orgs/nominate/` sends, set where the screen reads it.
 *  It is a query parameter rather than a prop because it is not part of the
 *  route - see lib/orgRoute.ts - so the screen reads `location` itself. */
function arriveWith(website: string) {
  window.history.replaceState(
    null,
    '',
    `/nominate?website=${encodeURIComponent(website)}`,
  )
}

beforeEach(() => {
  arriveWith('https://carolinamountainclub.org')
  vi.restoreAllMocks()
  // Difficulty 1 so the real solver runs and finishes at once - stubbing it
  // would leave the screen's own wiring untested, and the wiring is what
  // breaks (the message the two halves hash has to match).
  vi.spyOn(orgApi, 'nominateChallenge').mockResolvedValue({
    nonce: 'a-nonce',
    difficulty: 1,
    expires_at: 2_000_000_000,
    signature: 'signed',
  })
  vi.spyOn(orgApi, 'nominateRead').mockResolvedValue(READING)
})

async function readTheSite() {
  const person = userEvent.setup()
  render(<Nominate onLeave={vi.fn()} />)
  await person.click(screen.getByRole('button', { name: /read their site/i }))
  await screen.findByText(/Read, not verified/i)
  return person
}

describe('the hiker reviews what was found', () => {
  it('shows every address it is proposing, with the page it came off', async () => {
    await readTheSite()
    expect(screen.getByText('volunteers@carolinamountainclub.org')).toBeInTheDocument()
    expect(
      screen.getByText(/Listed on https:\/\/carolinamountainclub\.org\/get-involved/),
    ).toBeInTheDocument()
  })

  it('a dropped contact is not submitted, which is the whole condition', async () => {
    // The maintainer allowed harvesting named people's addresses ON the
    // condition that the hiker can abandon them. The backend stores nothing
    // until this submit, so an address unchecked here is never written down -
    // not hidden, not stored. This test is that promise.
    const submit = vi.spyOn(orgApi, 'nominateSubmit').mockResolvedValue({
      id: 'n1',
      club_slug: 'carolina-mountain-club',
    })
    const person = await readTheSite()

    const boxes = screen.getAllByRole('checkbox')
    await person.click(boxes[boxes.length - 1]!)
    await person.click(screen.getByRole('button', { name: /write to 1 person/i }))

    await waitFor(() => expect(submit).toHaveBeenCalled())
    const sent = submit.mock.calls[0]![0]
    expect(sent.contacts.map((contact) => contact.email)).toEqual([
      'volunteers@carolinamountainclub.org',
    ])
  })

  it('the button says how many people it is about to write to', async () => {
    // A submit labelled "Submit" hides the one consequence that matters. This
    // is real mail to real volunteers who did not ask for it.
    await readTheSite()
    expect(
      screen.getByRole('button', {
        name: /write to 2 people at Carolina Mountain Club/i,
      }),
    ).toBeInTheDocument()
  })

  it('cannot be submitted with nobody to ask', async () => {
    const person = await readTheSite()
    for (const box of screen.getAllByRole('checkbox')) {
      if ((box as HTMLInputElement).checked) await person.click(box)
    }
    expect(screen.getByRole('button', { name: /write to 0 people/i })).toBeDisabled()
  })

  it('says it could not reach the site rather than showing an empty result', async () => {
    // Rendering "we found nothing" for a fetch that failed would be this
    // screen telling a hiker that a club publishes nothing - a claim about
    // somebody's organization that nobody checked.
    vi.spyOn(orgApi, 'nominateRead').mockResolvedValue({
      ...READING,
      read_at_all: false,
      pages_read: 0,
      org_name: null,
      sources: [],
      contacts: [],
    })
    const person = userEvent.setup()
    render(<Nominate onLeave={vi.fn()} />)
    await person.click(screen.getByRole('button', { name: /read their site/i }))
    expect(await screen.findByText(/could not open their site/i)).toBeInTheDocument()
    expect(screen.queryByText(/Read, not verified/i)).not.toBeInTheDocument()
  })

  it('says why the browser is busy rather than spinning', async () => {
    let release: (value: unknown) => void = () => {}
    vi.spyOn(orgApi, 'nominateChallenge').mockReturnValue(
      new Promise((resolve) => {
        release = resolve
      }) as never,
    )
    const person = userEvent.setup()
    render(<Nominate onLeave={vi.fn()} />)
    await person.click(screen.getByRole('button', { name: /read their site/i }))
    expect(await screen.findByRole('status')).toHaveTextContent(/arithmetic/i)
    release({ nonce: 'n', difficulty: 1, expires_at: 2_000_000_000, signature: 's' })
  })
})

describe('the club answers', () => {
  beforeEach(() => {
    vi.spyOn(orgApi, 'proposal').mockResolvedValue(PROPOSAL)
  })

  it('offers the refusal as plainly as the approval', async () => {
    render(<Proposal token="abc123" />)
    expect(
      await screen.findByRole('button', { name: /no thank you/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /this is ours/i })).toBeInTheDocument()
  })

  it('offers the stronger refusal in plain words', async () => {
    render(<Proposal token="abc123" />)
    expect(
      await screen.findByRole('button', { name: /never to ask again/i }),
    ).toBeInTheDocument()
  })

  it('one refusal ends it, without needing three', async () => {
    const decide = vi
      .spyOn(orgApi, 'proposalDecision')
      .mockResolvedValue({ ...PROPOSAL, state: 'declined' })
    const person = userEvent.setup()
    render(<Proposal token="abc123" />)
    await person.click(await screen.findByRole('button', { name: /no thank you/i }))
    await waitFor(() => expect(decide).toHaveBeenCalledWith('abc123', expect.anything()))
    expect(
      await screen.findByText(/Nothing of yours is going anywhere/i),
    ).toBeInTheDocument()
  })

  it('never asking again is sent as a different answer from declining', async () => {
    const decide = vi
      .spyOn(orgApi, 'proposalDecision')
      .mockResolvedValue({ ...PROPOSAL, state: 'declined' })
    const person = userEvent.setup()
    render(<Proposal token="abc123" />)
    await person.click(await screen.findByRole('button', { name: /never to ask again/i }))
    await waitFor(() =>
      expect(decide).toHaveBeenCalledWith('abc123', {
        approve: false,
        never_ask_again: true,
      }),
    )
  })

  it('does not name the hiker who proposed them', async () => {
    // The design's rule in both directions: the club is not handed a way to
    // contact whoever proposed them, and they are never told who declined.
    render(<Proposal token="abc123" />)
    expect(await screen.findByText(/A hiker on OurHike/)).toBeInTheDocument()
  })

  it('says how many approvals it is waiting on', async () => {
    render(<Proposal token="abc123" />)
    expect(await screen.findByText(/0 OF 3/i)).toBeInTheDocument()
  })

  it('an expired link says the same thing as a wrong one', async () => {
    vi.spyOn(orgApi, 'proposal').mockRejectedValue(new Error('404'))
    render(<Proposal token="abc123" />)
    expect(await screen.findByText(/expired, or is not one of ours/i)).toBeInTheDocument()
  })

  it('arriving from the email does not decide anything on its own', async () => {
    // One click in a mail client must not decide an organization's position
    // silently. The link opens the screen; the button is still the button.
    const decide = vi.spyOn(orgApi, 'proposalDecision')
    render(<Proposal token="abc123" refusing />)
    expect(await screen.findByText(/Nothing has happened yet/i)).toBeInTheDocument()
    expect(decide).not.toHaveBeenCalled()
  })
})

describe('the demo path, which is what the preview photographs', () => {
  // THESE ARE THE SHOT RECIPES' SELECTORS, asserted here rather than
  // discovered in CI. `preview-shots/org-nominate-review.mjs` waits on the
  // text "WHO AT THE CLUB WE WOULD ASK" and clicks a button matching /Write to
  // 3 people/; `org-proposal-refusal.mjs` waits on /No thank you/ and scrolls
  // to /never to ask again/. A recipe whose wait never resolves fails the
  // preview job with a timeout and no useful message, twenty minutes after
  // the push.
  it('the nominate screen reaches the review without a backend', async () => {
    arriveWith('https://demo.ourhike.org')
    const person = userEvent.setup()
    render(<Nominate onLeave={vi.fn()} />)
    await person.click(screen.getByRole('button', { name: /read their site/i }))
    expect(await screen.findByText('WHO AT THE CLUB WE WOULD ASK')).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: /Write to 3 people at Blue Ridge Footpath Society/,
      }),
    ).toBeInTheDocument()
  })

  it('the demo shows a role nobody published a name against', async () => {
    arriveWith('https://demo.ourhike.org')
    // The design's own example, and the case worth photographing: absent is
    // not an empty string and not a guess.
    const person = userEvent.setup()
    render(<Nominate onLeave={vi.fn()} />)
    await person.click(screen.getByRole('button', { name: /read their site/i }))
    expect(await screen.findByText('Board president')).toBeInTheDocument()
  })

  it('the demo reading never asks the server for anything', async () => {
    arriveWith('https://demo.ourhike.org')
    const challenge = vi.spyOn(orgApi, 'nominateChallenge')
    const read = vi.spyOn(orgApi, 'nominateRead')
    const person = userEvent.setup()
    render(<Nominate onLeave={vi.fn()} />)
    await person.click(screen.getByRole('button', { name: /read their site/i }))
    await screen.findByText('WHO AT THE CLUB WE WOULD ASK')
    expect(challenge).not.toHaveBeenCalled()
    expect(read).not.toHaveBeenCalled()
  })

  it('the proposal screen opens on the demo token', async () => {
    const fetched = vi.spyOn(orgApi, 'proposal')
    render(<Proposal token="demo" />)
    expect(
      await screen.findByRole('button', { name: /No thank you/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /never to ask again/ })).toBeInTheDocument()
    expect(fetched).not.toHaveBeenCalled()
  })

  it('the demo proposal answers itself rather than 404ing', async () => {
    const decide = vi.spyOn(orgApi, 'proposalDecision')
    const person = userEvent.setup()
    render(<Proposal token="demo" />)
    await person.click(await screen.findByRole('button', { name: /No thank you/ }))
    expect(
      await screen.findByText(/Nothing of yours is going anywhere/i),
    ).toBeInTheDocument()
    expect(decide).not.toHaveBeenCalled()
  })
})
