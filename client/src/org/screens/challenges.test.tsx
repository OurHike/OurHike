/**
 * The console's Challenges page and its Finishers sub-page (#1780, frame 2a).
 *
 * WHAT THESE HOLD, beyond "it renders": the guardrail's rules that survive into
 * the console (features/CHALLENGES.md, "The guardrail argument") - a count the
 * club sees and never a hiker, no comparison, no name on screen - and the
 * contract's principle that a place is a published POI id and never a typed
 * position, which on this screen is an absence: there is no field to type
 * one into. An absence is the thing a later "just add a mile field" would
 * break without any other test noticing.
 */

import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  Challenges,
  finishLabel,
  newChallengeId,
  placesLabel,
  windowLabel,
} from './Challenges'
import { ChallengeFinishers } from './ChallengeFinishers'
import { ApiError } from '../../lib/api'
import { DEMO_CHALLENGES, DEMO_REGISTRY, DEMO_ROSTER, DEMO_SLUG } from '../demoOrg'
import type {
  ChallengeDefinition,
  ChallengePublishResult,
  OrgChallengeRow,
} from '../orgApi'

afterEach(cleanup)

const TRAILS = DEMO_REGISTRY.flatMap((park) => park.trails)

/** Words the guardrail keeps off every challenge screen: comparison, pressure,
 *  and the ATC's own name for its stamp programme. */
const FORBIDDEN = /leaderboard|rank|streak|other hikers|stamp|passport/i

function drawChallenges(over: Partial<Parameters<typeof Challenges>[0]> = {}) {
  const onPublish = vi.fn<Parameters<typeof Challenges>[0]['onPublish']>(async () => ({
    pull_request: null,
    detail: 'ok',
  }))
  const onOpenFinishers = vi.fn()
  render(
    <Challenges
      orgSlug={DEMO_SLUG}
      rows={DEMO_CHALLENGES}
      trails={TRAILS}
      canEdit
      onPublish={onPublish}
      onPreview={() => {}}
      onOpenFinishers={onOpenFinishers}
      {...over}
    />,
  )
  return { onPublish, onOpenFinishers }
}

function editor(): HTMLElement {
  return screen.getByRole('region', { name: 'Editing' })
}

/** Every form control on screen with the words that label it. */
function labelledControls(): { control: Element; label: string }[] {
  return [...document.querySelectorAll('input, select, textarea')].map((control) => ({
    control,
    label: [
      control.closest('label')?.textContent ?? '',
      control.getAttribute('aria-label') ?? '',
      control.getAttribute('placeholder') ?? '',
      control.getAttribute('name') ?? '',
    ].join(' '),
  }))
}

describe('the Challenges table', () => {
  it('draws the five columns frame 2a draws', () => {
    drawChallenges()

    const headers = screen.getAllByRole('columnheader').map((th) => th.textContent)
    expect(headers).toEqual(['Challenge', 'Window', 'Places', 'Finished at', 'Hikers in'])
    // One row per challenge, plus the header row.
    expect(screen.getAllByRole('row')).toHaveLength(DEMO_CHALLENGES.length + 1)
  })

  it('draws the three tiles that say what a challenge may be made of', () => {
    drawChallenges()

    expect(screen.getByText('Your trails only')).toBeInTheDocument()
    expect(screen.getByText('Places, not taps')).toBeInTheDocument()
    expect(screen.getByText('Ships with the data')).toBeInTheDocument()
    expect(screen.getByText(/never reach the map/)).toBeInTheDocument()
  })

  it('says "fewer than 25" when the server sent no number, never a zero', () => {
    drawChallenges()

    const row = screen.getByRole('row', { name: /bridges and arches/i })
    expect(within(row).getByText('fewer than 25')).toBeInTheDocument()
    expect(within(row).queryByText('0')).toBeNull()
  })

  it('says "not live" for a challenge no phone has, rather than a count', () => {
    drawChallenges()

    const row = screen.getByRole('row', { name: /North Woods/i })
    expect(within(row).getByText('not live')).toBeInTheDocument()
    expect(within(row).getByText(/draft/)).toBeInTheDocument()
  })

  it('shows a hikers-in figure the server did send', () => {
    drawChallenges()

    const row = screen.getByRole('row', { name: /Park Drive loop/i })
    expect(within(row).getByText('64')).toBeInTheDocument()
    expect(within(row).getByText('all 4')).toBeInTheDocument()
  })

  it('contains none of the words the guardrail keeps off a challenge screen', () => {
    drawChallenges()

    expect(document.body.textContent).not.toMatch(FORBIDDEN)
  })

  it('offers the empty state, not an empty table, to a club with none', () => {
    drawChallenges({ rows: [] })

    expect(screen.getByText('No challenges yet')).toBeInTheDocument()
    expect(screen.queryByRole('table')).toBeNull()
  })
})

describe('the columns, as words', () => {
  it('writes a window the way the column reads it', () => {
    expect(windowLabel({ opens: null, closes: null })).toBe('no end')
    expect(windowLabel({ opens: '2027-06-01', closes: '2027-10-31' })).toBe(
      'Jun 1–Oct 31, 2027',
    )
    expect(windowLabel({ opens: '2026-11-01', closes: '2027-03-01' })).toBe(
      'Nov 1, 2026–Mar 1, 2027',
    )
    expect(windowLabel(null)).toBe('—')
  })

  it('writes a challenge with no finish line as a record, not as zero', () => {
    const definition = DEMO_CHALLENGES[0].definition as ChallengeDefinition
    expect(finishLabel({ ...definition, finish: null })).toBe('record only')
    expect(finishLabel({ ...definition, finish: { count: 2 } })).toBe('2')
  })

  it('counts workdays as workdays and at-home items not at all', () => {
    expect(placesLabel(DEMO_CHALLENGES[2].definition)).toBe('3 workdays')
    const definition = DEMO_CHALLENGES[1].definition as ChallengeDefinition
    const withHome: ChallengeDefinition = {
      ...definition,
      items: [
        ...definition.items,
        {
          id: 'read-a-book',
          section: 'crossings',
          title: 'Read',
          match: { kind: 'self_report' },
        },
      ],
    }
    expect(placesLabel(withHome)).toBe('5')
  })
})

describe('the editor', () => {
  it('opens on the first challenge and loads the row somebody selects', async () => {
    drawChallenges()
    expect(within(editor()).getByRole('heading')).toHaveTextContent(
      'Park Drive loop, end to end',
    )

    await userEvent.click(screen.getByRole('row', { name: /North Woods/i }))

    expect(within(editor()).getByRole('heading')).toHaveTextContent(
      'Give a day to the North Woods',
    )
    expect(screen.getByRole('row', { name: /North Woods/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(within(editor()).getByRole('button', { name: 'Workdays' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('opens on the challenge the address named', () => {
    drawChallenges({ initialId: 'demo-ramble-bridges-and-arches' })

    expect(within(editor()).getByRole('heading')).toHaveTextContent(
      "The Ramble's bridges and arches",
    )
  })

  it("offers only the organization's own trails", () => {
    drawChallenges()

    const trail = within(editor()).getByRole('combobox', { name: /^Trail/ })
    const offered = within(trail)
      .getAllByRole('option')
      .map((option) => option.textContent)
    expect(offered).toEqual(TRAILS.map((t) => t.name))
  })

  it('has no field for a mile or a coordinate anywhere, even with an item open', async () => {
    drawChallenges({ initialId: 'demo-ramble-bridges-and-arches' })
    await userEvent.click(within(editor()).getByText(/notes and photos/))
    await userEvent.click(within(editor()).getByRole('button', { name: 'Bow Bridge' }))

    // The item's own fields are open, so this is the widest the editor gets.
    expect(within(editor()).getByLabelText(/note/i)).toBeInTheDocument()
    const typedPosition = labelledControls().filter(({ label }) =>
      /mile|latitude|longitude|\blat\b|\blon\b|coordinate/i.test(label),
    )
    expect(typedPosition).toEqual([])
    expect(
      screen.getByText(/chosen from your published waypoints when this file is reviewed/),
    ).toBeInTheDocument()
  })

  it('sends the edited definition and shows the pull request it opened', async () => {
    const onPublish = vi.fn(async (): Promise<ChallengePublishResult> => ({
      pull_request: 'https://github.com/OurHike/OurHike/pull/1',
      detail: 'Opened for your codeowners.',
    }))
    drawChallenges({ onPublish })

    const finish = within(editor()).getByRole('spinbutton', { name: /Finished at/ })
    await userEvent.clear(finish)
    await userEvent.type(finish, '3')
    await userEvent.click(
      screen.getByRole('button', { name: 'Publish with next refresh' }),
    )

    expect(onPublish).toHaveBeenCalledTimes(1)
    const [id, sent] = onPublish.mock.calls[0] as unknown as [string, ChallengeDefinition]
    expect(id).toBe('demo-drive-loop-end-to-end')
    expect(sent.finish?.count).toBe(3)
    expect(sent.items).toHaveLength(4)
    const link = await screen.findByRole('link', { name: /Open the pull request/ })
    expect(link).toHaveAttribute('href', 'https://github.com/OurHike/OurHike/pull/1')
    expect(link.closest('.org-callout')).toHaveAttribute('data-tone', 'good')
  })

  it("shows the server's own refusal, not the request line", async () => {
    const cap = 'Ask OurHike to remove one you no longer need before saving another.'
    const onPublish = vi.fn(async (): Promise<ChallengePublishResult> => {
      throw new ApiError(409, 'POST /clubs/demo/challenges/x failed: 409', {
        detail: cap,
      })
    })
    drawChallenges({ onPublish })

    await userEvent.click(
      screen.getByRole('button', { name: 'Publish with next refresh' }),
    )

    const said = await screen.findByText(cap)
    expect(said.closest('.org-callout')).toHaveAttribute('data-tone', 'stop')
    expect(screen.queryByText(/failed: 409/)).toBeNull()
  })

  it('says what the server said when no pull request was opened', async () => {
    const onPublish = vi.fn(async (): Promise<ChallengePublishResult> => ({
      pull_request: null,
      detail: 'The registry opener is switched off on this deployment.',
    }))
    drawChallenges({ onPublish })

    await userEvent.click(
      screen.getByRole('button', { name: 'Publish with next refresh' }),
    )

    const said = await screen.findByText(/opener is switched off/)
    expect(said.closest('.org-callout')).toHaveAttribute('data-tone', 'info')
    expect(screen.queryByRole('link', { name: /pull request/ })).toBeNull()
  })

  it('refuses a finish line the items could never reach, and says why', async () => {
    const { onPublish } = drawChallenges()

    const finish = within(editor()).getByRole('spinbutton', { name: /Finished at/ })
    await userEvent.clear(finish)
    await userEvent.type(finish, '9')

    expect(screen.getByText(/a finish at 9 could never be reached/)).toBeInTheDocument()
    const publish = screen.getByRole('button', { name: 'Publish with next refresh' })
    expect(publish).toBeDisabled()
    await userEvent.click(publish)
    expect(onPublish).not.toHaveBeenCalled()
  })

  it('offers a reward only with a finish line to claim it at', async () => {
    drawChallenges()

    const finish = within(editor()).getByRole('spinbutton', { name: /Finished at/ })
    await userEvent.clear(finish)

    expect(
      within(editor()).getByRole('combobox', { name: /When someone finishes/ }),
    ).toBeDisabled()
    expect(screen.getByText(/needs a finish line to be claimed at/)).toBeInTheDocument()
  })

  it('holds a challenge whose file did not arrive shut, rather than overwriting it', () => {
    const row: OrgChallengeRow = { ...DEMO_CHALLENGES[0], definition: undefined }
    drawChallenges({ rows: [row] })

    expect(screen.getByText(/did not come with this challenge/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Publish with next refresh' }),
    ).toBeDisabled()
  })

  it('names a new challenge after its org, so two clubs cannot collide', async () => {
    // `resolve` in pipeline/lib/challenges.py drops a second file carrying an
    // id it has seen, across every organization.
    expect(newChallengeId('ramapo-trail-conference', 'Workdays')).toBe(
      'ramapo-trail-conference-workdays',
    )
    expect(newChallengeId('atc', 'ATC summer list')).toBe('atc-summer-list')

    const { onPublish } = drawChallenges()
    await userEvent.click(screen.getByRole('button', { name: '+ New challenge' }))
    await userEvent.type(
      within(editor()).getByRole('textbox', { name: 'Name' }),
      'Loch walk',
    )
    await userEvent.click(
      screen.getByRole('button', { name: 'Publish with next refresh' }),
    )

    expect(onPublish.mock.calls[0]?.[0]).toBe(`${DEMO_SLUG}-loch-walk`)
  })

  it('refuses a new challenge whose name would overwrite an existing one', async () => {
    const taken: OrgChallengeRow = {
      ...DEMO_CHALLENGES[0],
      challenge_id: `${DEMO_SLUG}-loch-walk`,
    }
    const { onPublish } = drawChallenges({ rows: [taken] })
    await userEvent.click(screen.getByRole('button', { name: '+ New challenge' }))
    await userEvent.type(
      within(editor()).getByRole('textbox', { name: 'Name' }),
      'Loch walk',
    )

    expect(screen.getByText(/already exists/)).toBeInTheDocument()
    const publish = screen.getByRole('button', { name: 'Publish with next refresh' })
    expect(publish).toBeDisabled()
    await userEvent.click(publish)
    expect(onPublish).not.toHaveBeenCalled()
  })

  it('opens the selected challenge’s finishers', async () => {
    const { onOpenFinishers } = drawChallenges()

    await userEvent.click(within(editor()).getByRole('button', { name: /Finishers/ }))

    expect(onOpenFinishers).toHaveBeenCalledWith('demo-drive-loop-end-to-end')
  })

  it('offers nothing to press to somebody who cannot edit', () => {
    drawChallenges({ canEdit: false })

    expect(screen.queryByRole('button', { name: 'Publish with next refresh' })).toBeNull()
    expect(screen.queryByRole('button', { name: /New challenge/ })).toBeNull()
  })
})

describe('Finishers', () => {
  function drawFinishers(
    challengeId: string | null,
    fetchEntries: (id: string) => Promise<string> = async () => '',
    save = vi.fn(),
  ) {
    render(
      <ChallengeFinishers
        rows={DEMO_CHALLENGES}
        challengeId={challengeId}
        onPick={() => {}}
        onBack={() => {}}
        fetchEntries={fetchEntries}
        save={save}
      />,
    )
    return save
  }

  it('shows the two counts and the floor rule, and says a count is all it is', () => {
    drawFinishers('demo-ramble-bridges-and-arches')

    expect(screen.getByRole('heading', { name: 'Finishers' })).toBeInTheDocument()
    expect(screen.getByText('fewer than 25')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Hikers in is a count only. No names reach you until someone sends an entry.',
      ),
    ).toBeInTheDocument()
  })

  it('renders no name, even once a file full of them has been saved', async () => {
    const csv =
      'name,email,mailing_address,items\n"Ada Walker",ada@example.org,,bow-bridge;oak-bridge\n'
    const save = drawFinishers('demo-ramble-bridges-and-arches', async () => csv)

    await userEvent.click(screen.getByRole('button', { name: 'Download entries (CSV)' }))

    expect(save).toHaveBeenCalledTimes(1)
    expect(save.mock.calls[0][1]).toBe(csv)
    expect(await screen.findByText(/^Saved /)).toBeInTheDocument()
    const text = document.body.textContent ?? ''
    expect(text).not.toContain('Ada Walker')
    expect(text).not.toContain('ada@example.org')
    for (const person of DEMO_ROSTER) {
      if (person.full_name) expect(text).not.toContain(person.full_name)
    }
  })

  it('says a draft takes no entries, and still offers the download', () => {
    drawFinishers('demo-north-woods-workdays')

    expect(screen.getByText('A draft takes no entries.')).toBeInTheDocument()
    expect(screen.getByText('not live')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download entries (CSV)' })).toBeEnabled()
  })

  it('says why nothing was downloaded rather than saving an empty file', async () => {
    const save = drawFinishers('demo-drive-loop-end-to-end', async () => {
      throw new Error('Only an admin of this organization can read its entries.')
    })

    await userEvent.click(screen.getByRole('button', { name: 'Download entries (CSV)' }))

    expect(await screen.findByText(/Only an admin/)).toBeInTheDocument()
    expect(save).not.toHaveBeenCalled()
  })

  it('contains none of the words the guardrail keeps off a challenge screen', () => {
    drawFinishers(null)

    expect(document.body.textContent).not.toMatch(FORBIDDEN)
  })
})

describe('when the list could not be read', () => {
  it('says so, and offers nothing that could overwrite a challenge it cannot see', () => {
    drawChallenges({ rows: [], rowsUnread: true })
    expect(screen.getByText('Could not read your challenges')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '+ New challenge' })).toBeNull()
    expect(screen.queryByText('No challenges yet')).toBeNull()
  })

  it('says a stale Finishers address names no challenge, rather than showing another one', () => {
    render(
      <ChallengeFinishers
        rows={DEMO_CHALLENGES}
        challengeId="no-such-challenge"
        onPick={() => {}}
        onBack={() => {}}
        fetchEntries={async () => ''}
        save={vi.fn()}
      />,
    )
    expect(screen.getByText('That challenge is not here')).toBeInTheDocument()
  })
})
