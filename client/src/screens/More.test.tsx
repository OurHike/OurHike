import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { More } from './More'
import { DEFAULT_PREFERENCES } from '../lib/userPreferences'

// The tab that owns reporting. Settings has its own tests; what is left here is
// the contribute section on top of it, and the outbox count in particular -
// that number is the only thing telling someone with no signal that their
// report still exists.

const PROPS = {
  account: null as { email: string } | null,
  reporterType: 'thru' as const,
  onSignIn: vi.fn(),
  onSignOut: vi.fn(),
  preferences: DEFAULT_PREFERENCES,
  onChange: vi.fn(),
  lastSyncedAt: null,
  onSync: vi.fn(),
  onExport: vi.fn(),
  onStartReport: vi.fn(),
  queuedReportCount: 0,
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('More', () => {
  it('offers the way into reporting', async () => {
    const user = userEvent.setup()
    render(<More {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /report a problem/i }))

    expect(PROPS.onStartReport).toHaveBeenCalledTimes(1)
  })

  it('says nothing about an outbox that is empty', () => {
    render(<More {...PROPS} />)

    expect(screen.queryByRole('status')).toBe(null)
  })

  it('counts a single waiting report in the singular', () => {
    render(<More {...PROPS} queuedReportCount={1} />)

    expect(screen.getByRole('status')).toHaveTextContent('1 report waiting to send.')
  })

  it('counts several in the plural', () => {
    render(<More {...PROPS} queuedReportCount={3} />)

    expect(screen.getByRole('status')).toHaveTextContent('3 reports waiting to send.')
  })

  it('still renders the settings underneath it', () => {
    render(<More {...PROPS} />)

    expect(screen.getByRole('heading', { name: 'You' })).toBeInTheDocument()
  })
})

// --- A report that will never send (#243) --------------------------------
//
// "Waiting to send" is true right up until it is not, and a phone with a
// wrong clock has every report refused - so without this the app tells
// someone their report is on its way, indefinitely, while it never moves.

const STUCK = [
  {
    id: 'r1',
    reason: 'The server would not accept it. Check your phone’s date and time.',
  },
]

describe('More, when a report was refused for good', () => {
  it('says so, in words, rather than leaving it in the waiting count', () => {
    render(<More {...PROPS} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent('1 report could not be sent.')
  })

  it('shows the reason, because "failed" alone is not actionable', () => {
    render(<More {...PROPS} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent(/date and time/i)
  })

  it('promises the writing is not lost, which is the fear this creates', () => {
    render(<More {...PROPS} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent(/nothing has been lost/i)
  })

  it('keeps the two counts apart', () => {
    // One waiting for signal, one refused. Rolling them together is the bug.
    render(<More {...PROPS} queuedReportCount={1} stuckReports={STUCK} />)

    expect(screen.getByRole('status')).toHaveTextContent('1 report waiting to send.')
    expect(screen.getByRole('alert')).toHaveTextContent('1 report could not be sent.')
  })

  it('pluralises', () => {
    render(<More {...PROPS} stuckReports={[...STUCK, { id: 'r2', reason: 'Nope.' }]} />)

    expect(screen.getByRole('alert')).toHaveTextContent('2 reports could not be sent.')
  })

  it('offers a retry, for the cause a hiker can actually fix', async () => {
    const user = userEvent.setup()
    const onRetryReport = vi.fn()
    render(<More {...PROPS} stuckReports={STUCK} onRetryReport={onRetryReport} />)

    await user.click(screen.getByRole('button', { name: /try again/i }))

    expect(onRetryReport).toHaveBeenCalledWith('r1')
  })

  it('offers a way out, so a doomed report is not permanent furniture', async () => {
    const user = userEvent.setup()
    const onDiscardReport = vi.fn()
    render(<More {...PROPS} stuckReports={STUCK} onDiscardReport={onDiscardReport} />)

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    await user.click(screen.getByRole('button', { name: /yes, delete it/i }))

    expect(onDiscardReport).toHaveBeenCalledWith('r1')
  })

  it('asks before deleting, because Delete sits beside Try again in the same coat', async () => {
    // The two buttons are styled identically, one is safe and one destroys
    // text written days ago - and the note below promises nothing is lost
    // "until you delete it". That promise must not hinge on a cold thumb.
    const user = userEvent.setup()
    const onDiscardReport = vi.fn()
    render(<More {...PROPS} stuckReports={STUCK} onDiscardReport={onDiscardReport} />)

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onDiscardReport).not.toHaveBeenCalled()

    // The safe answer disarms and puts the ordinary buttons back.
    await user.click(screen.getByRole('button', { name: /keep it/i }))
    expect(onDiscardReport).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
  })

  it('says nothing when nothing is stuck', () => {
    render(<More {...PROPS} queuedReportCount={2} />)

    expect(screen.queryByRole('alert')).toBe(null)
  })
})

describe('the moderation entry (#235)', () => {
  it('is absent for an ordinary hiker', () => {
    // Offered on a guess, it costs a 403 the person cannot act on and an app
    // that looks broken. `onOpenModeration` being undefined IS "not a
    // moderator" as far as this screen is concerned.
    render(<More {...PROPS} />)

    expect(screen.queryByRole('button', { name: /moderation/i })).toBeNull()
  })

  it('appears, and opens the queue, when there is somewhere to go', () => {
    const onOpenModeration = vi.fn()
    render(<More {...PROPS} onOpenModeration={onOpenModeration} />)

    screen.getByRole('button', { name: /moderation queue/i }).click()

    expect(onOpenModeration).toHaveBeenCalled()
  })
})

// --- Four sections instead of one long scroll (#796, features/MORE_TAB.md) -

describe('the four sections', () => {
  it('starts on You, where the hike and report entries already lived', () => {
    render(<More {...PROPS} />)

    expect(screen.getByRole('tab', { name: 'You', selected: true })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'You' })).toBeInTheDocument()
  })

  it('offers all four sections, in order', () => {
    render(<More {...PROPS} />)

    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'You',
      'Map & Display',
      'Safety & Privacy',
      'About',
    ])
  })

  it('shows the map preferences only after switching to Map & Display', async () => {
    const user = userEvent.setup()
    render(<More {...PROPS} />)

    expect(screen.queryByRole('heading', { name: 'The map' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Map & Display' }))

    expect(screen.getByRole('heading', { name: 'The map' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Display' })).toBeInTheDocument()
  })

  it('shows safety and privacy only after switching to that tab', async () => {
    const user = userEvent.setup()
    render(<More {...PROPS} />)

    expect(
      screen.queryByRole('heading', { name: 'Safety & privacy' }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Safety & Privacy' }))

    expect(screen.getByRole('heading', { name: 'Safety & privacy' })).toBeInTheDocument()
  })

  it('shows the reference material only after switching to About', async () => {
    const user = userEvent.setup()
    render(<More {...PROPS} />)

    await user.click(screen.getByRole('tab', { name: 'About' }))

    expect(screen.getByRole('heading', { name: 'Your data' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'About this build' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Report a bug' })).toBeInTheDocument()
  })
})

// #378. About is where somebody goes looking for it, and it is the only tab a
// hiker can reach that could carry it - so the wiring is worth a test of its
// own even though screens/AboutBuild.test.tsx covers the rows.
describe('About this build, from the About tab', () => {
  it('says which build the app is running, without being passed one', async () => {
    const user = userEvent.setup()
    render(<More {...PROPS} />)
    await user.click(screen.getByRole('tab', { name: 'About' }))

    expect(screen.getByRole('heading', { name: 'About this build' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /copy build details/i }),
    ).toBeInTheDocument()
  })
})

describe('the download link, from the About tab', () => {
  it('offers the way to the download, since there is no tab to send anyone to', async () => {
    const user = userEvent.setup()
    const onOpenDownloads = vi.fn()
    render(<More {...PROPS} onOpenDownloads={onOpenDownloads} />)
    await user.click(screen.getByRole('tab', { name: 'About' }))

    await user.click(screen.getByRole('button', { name: /choose what to download/i }))

    expect(onOpenDownloads).toHaveBeenCalledTimes(1)
  })

  it('admits a download still running with its window shut', async () => {
    // The other home of the same link, and the screen someone comes back to
    // an hour later to ask whether the thing they started ever finished.
    const user = userEvent.setup()
    render(
      <More
        {...PROPS}
        onOpenDownloads={vi.fn()}
        downloadActivity={{ kind: 'downloading', doneBytes: 1, totalBytes: 4 }}
      />,
    )
    await user.click(screen.getByRole('tab', { name: 'About' }))

    expect(screen.getByText('Downloading 25%')).toBeVisible()
  })

  it('puts it at the foot of the About tab, below every group', async () => {
    // A once-a-season errand, so it is findable by anyone who scrolls looking
    // for it and out of the way of the rows that get used.
    const user = userEvent.setup()
    const { container } = render(<More {...PROPS} onOpenDownloads={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: 'About' }))

    const link = screen.getByRole('button', { name: /choose what to download/i })
    expect(container.querySelector('.settings')?.lastElementChild).toBe(link)
  })
})

// --- Where the sync panel sits (#894) --------------------------------------
//
// Which tab shows which group is this file's job. The panel's own copy is
// tested in AccountSync.test.tsx; what matters here is that it appears where
// a hiker asking "what happens to my things" is already looking - beside the
// account - and that it does not appear when there is nothing to say.

const SYNCING = {
  syncStatus: {
    lastSyncedAt: new Date('2026-08-21T09:00:00Z'),
    neverSent: ['Grayson Highlands'],
    unsentEdits: [],
    preferencesUnsent: false,
    hikeUnsent: false,
  },
  syncEnabled: true,
  onToggleSync: vi.fn(),
  now: new Date('2026-08-21T12:00:00Z'),
}

describe('what the account has (#894)', () => {
  it('sits in the You tab, under the account it depends on', () => {
    render(<More {...PROPS} account={{ email: 'hiker@example.org' }} {...SYNCING} />)

    expect(
      screen.getByRole('heading', { name: /what your account has/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('Grayson Highlands')).toBeInTheDocument()
  })

  it('says nothing at all to a hiker who is signed out', () => {
    // There is no account for anything to have reached, and a panel reading
    // "never synced" over a signed-out phone would describe a failure where
    // there is only the app's ordinary premise.
    render(<More {...PROPS} {...SYNCING} />)

    expect(screen.queryByRole('heading', { name: /what your account has/i })).toBe(null)
  })

  it('says nothing when the shell could not read the sync bookkeeping', () => {
    // Null status is "we could not ask", and this screen would rather say
    // nothing than say the reassuring thing on no evidence.
    render(
      <More
        {...PROPS}
        account={{ email: 'hiker@example.org' }}
        {...SYNCING}
        syncStatus={undefined}
      />,
    )

    expect(screen.queryByRole('heading', { name: /what your account has/i })).toBe(null)
  })

  it('keeps the conditions bucket’s own last-synced row in the About tab', async () => {
    // Two different clocks in two different places, deliberately.
    const user = userEvent.setup()
    render(<More {...PROPS} account={{ email: 'hiker@example.org' }} {...SYNCING} />)

    expect(screen.queryByText('Last synced')).toBe(null)

    await user.click(screen.getByRole('tab', { name: /about/i }))

    expect(screen.getByText('Last synced')).toBeInTheDocument()
    expect(screen.queryByText('Last sent')).toBe(null)
  })
})

const ACCOUNT_DATA = {
  onExportAccount: vi.fn().mockResolvedValue(undefined),
  onDeleteAccount: vi.fn(),
}

describe('taking your data, or leaving (#895)', () => {
  it('sits in the You tab, below the sync panel', () => {
    // Export first, delete second, both from one screen - and the
    // irreversible control furthest from the thumb that opened the tab.
    render(
      <More
        {...PROPS}
        account={{ email: 'hiker@example.org' }}
        {...SYNCING}
        {...ACCOUNT_DATA}
      />,
    )

    expect(
      screen.getByRole('heading', { name: /taking your data, or leaving/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /download everything of yours/i }),
    ).toBeInTheDocument()
  })

  it('says nothing at all to a hiker who is signed out', () => {
    // There is no account to take back or to delete, and offering a button
    // that would 401 is worse than offering none.
    render(<More {...PROPS} {...SYNCING} {...ACCOUNT_DATA} />)

    expect(screen.queryByRole('heading', { name: /taking your data/i })).toBe(null)
  })

  it('stays on screen after the deletion signs the hiker out', () => {
    // The receipt is unmountable by construction otherwise: deleting signs
    // them out, `account` goes null, and the one screen a hiker is owed
    // disappears in the same tick it was earned.
    render(<More {...PROPS} {...SYNCING} {...ACCOUNT_DATA} accountDeleted />)

    expect(
      screen.getByRole('heading', { name: /taking your data, or leaving/i }),
    ).toBeInTheDocument()
  })

  it('says nothing on a surface that cannot actually run the deletion', () => {
    // The same rule the sync panel follows: a control with no handler behind
    // it must not be drawn, because there is no honest thing for it to do.
    render(<More {...PROPS} account={{ email: 'hiker@example.org' }} {...SYNCING} />)

    expect(screen.queryByRole('heading', { name: /taking your data/i })).toBe(null)
  })
})
