import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { More, type MorePage, type MoreProps } from './More'
import { DEFAULT_PREFERENCES } from '../lib/userPreferences'
import type { DownloadStatus } from './DownloadCard'

// The screen that owns reporting, the volunteer surface's door, and - since
// the five-destination shape (#1054) - the first honest answer to "is the map
// on this phone". Settings has its own tests; what is tested here is the home
// screen's summaries, the storage card, which page shows which group, and the
// outbox counts in particular - those are the only thing telling someone with
// no signal that their report still exists.

const NOT_DOWNLOADED: DownloadStatus = { state: 'not-downloaded' }

const PROPS = {
  page: 'home' as MorePage,
  onNavigate: vi.fn(),
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
  hikingStatus: NOT_DOWNLOADED,
}

/** More with the page as live state, for the tests that walk between pages -
 *  the shell owns the page in App.tsx, so the controlled component needs a
 *  stand-in shell to navigate at all. */
function MoreWalkable(props: Partial<MoreProps>) {
  const [page, setPage] = useState<MorePage>('home')
  return <More {...PROPS} {...props} page={page} onNavigate={setPage} />
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

// --- The home screen: five rows that answer before they are tapped ---------

describe('More, the home screen', () => {
  it('offers five destinations, in order', () => {
    const { container } = render(<More {...PROPS} />)

    expect(
      Array.from(container.querySelectorAll('.more__row-title')).map(
        (title) => title.textContent,
      ),
    ).toEqual([
      'You',
      'The map',
      'Safety & privacy',
      'Volunteer & report',
      'Where this map comes from',
    ])
  })

  it('summarises the account state on the You row', () => {
    render(<More {...PROPS} />)

    expect(screen.getByRole('button', { name: /^You/ })).toHaveTextContent(
      'Not signed in',
    )
  })

  it('summarises the chosen sheet and units on the map row', () => {
    // From the same records the pickers themselves render, so a renamed style
    // cannot be summarised under its old name.
    render(<More {...PROPS} />)

    expect(screen.getByRole('button', { name: /^The map/ })).toHaveTextContent(
      'Field · Feet',
    )
  })

  it('says location is off in the safety summary, when it is', () => {
    render(<More {...PROPS} />)

    expect(screen.getByRole('button', { name: /^Safety/ })).toHaveTextContent(
      'Location off',
    )
  })

  it('says location is on without claiming nothing ever leaves the phone', () => {
    // The prototype's "nothing leaves this phone" is false the moment sync is
    // on; what this row may claim is what Settings' own note promises - the
    // fix is sent only inside a report the hiker files.
    render(
      <More
        {...PROPS}
        preferences={{ ...DEFAULT_PREFERENCES, location_permission_requested: true }}
      />,
    )

    expect(screen.getByRole('button', { name: /^Safety/ })).toHaveTextContent(
      'Location on · sent only with your reports',
    )
  })

  it('walks into a page and back home', async () => {
    const user = userEvent.setup()
    render(<MoreWalkable />)

    await user.click(screen.getByRole('button', { name: /^The map/ }))
    expect(screen.getByRole('heading', { name: 'The map' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'More' }))
    expect(screen.getByRole('heading', { name: 'More' })).toBeInTheDocument()
  })

  it('thanks the volunteers, without counting anything', () => {
    render(<More {...PROPS} />)

    expect(screen.getByText(/volunteers keep this trail open/i)).toBeInTheDocument()
  })
})

// --- The volunteer row's two-count summary (#243) ---------------------------

describe('the volunteer row', () => {
  it('invites when nothing is queued', () => {
    render(<More {...PROPS} />)

    expect(screen.getByRole('button', { name: /^Volunteer & report/ })).toHaveTextContent(
      'Report problems, or lend a hand',
    )
  })

  it('carries the waiting count without the danger coat', () => {
    // "Waiting to send" is the ordinary state of an offline-first outbox, not
    // a fault - the same reasoning .settings__pending gives for staying grey.
    render(<More {...PROPS} queuedReportCount={2} />)

    const row = screen.getByRole('button', { name: /^Volunteer & report/ })
    expect(row).toHaveTextContent('2 reports waiting to send')
    expect(row).not.toHaveClass('more__row--alert')
  })

  it('wears the danger coat only for a report that will never send', () => {
    render(
      <More
        {...PROPS}
        queuedReportCount={2}
        stuckReports={[{ id: 'r1', reason: 'Refused.' }]}
      />,
    )

    const row = screen.getByRole('button', { name: /^Volunteer & report/ })
    expect(row).toHaveTextContent('1 report could not be sent')
    expect(row).toHaveClass('more__row--alert')
  })
})

// --- The storage card -------------------------------------------------------

describe('the storage card', () => {
  it('admits nothing is downloaded, and offers the way to change that', async () => {
    const user = userEvent.setup()
    const onOpenDownloads = vi.fn()
    render(<More {...PROPS} onOpenDownloads={onOpenDownloads} />)

    expect(screen.getByText('Nothing downloaded yet')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /choose what to download/i }))
    expect(onOpenDownloads).toHaveBeenCalledTimes(1)
  })

  it('states the finished download: size, level, and when it completed', () => {
    render(
      <More
        {...PROPS}
        onOpenDownloads={vi.fn()}
        hikingStatus={{
          state: 'downloaded',
          totalBytes: 1_400_000_000,
          completedAt: new Date('2026-08-23T10:00:00Z'),
        }}
      />,
    )

    expect(screen.getByText('1.4 GB')).toBeInTheDocument()
    expect(screen.getByText('The whole trail, standard detail')).toBeInTheDocument()
    expect(screen.getByText(/complete · finished august 23/i)).toBeInTheDocument()
    // The label changes with the state: the next tap changes a download
    // rather than starting one.
    expect(
      screen.getByRole('button', { name: /change what's downloaded/i }),
    ).toBeInTheDocument()
  })

  it('admits a download still running with its window shut', () => {
    // The screen someone comes back to an hour later to ask whether the thing
    // they started ever finished - via the same helpers DownloadsLink uses,
    // so the two doors can never disagree about a percent.
    render(
      <More
        {...PROPS}
        onOpenDownloads={vi.fn()}
        downloadActivity={{ kind: 'downloading', doneBytes: 1, totalBytes: 4 }}
      />,
    )

    expect(screen.getByText('25%')).toBeInTheDocument()
  })

  it('says a stopped transfer kept what arrived', () => {
    render(
      <More
        {...PROPS}
        hikingStatus={{
          state: 'failed',
          receivedBytes: 100_000_000,
          totalBytes: 400_000_000,
        }}
      />,
    )

    expect(screen.getByText(/stopped at 100 MB of 400 MB/i)).toBeInTheDocument()
  })

  it('offers no button on a surface that cannot open the window', () => {
    render(<More {...PROPS} />)

    expect(screen.queryByRole('button', { name: /download/i })).toBe(null)
  })
})

// --- The volunteer & report page --------------------------------------------
//
// The contribute section moved here whole, counts and all, so the roles keep
// announcing beside the controls that answer them: role="status" for a count
// that resolves itself, role="alert" for the one that never will (#243).

const ON_VOLUNTEER = { ...PROPS, page: 'volunteer' as MorePage }

const STUCK = [
  {
    id: 'r1',
    reason: 'The server would not accept it. Check your phone’s date and time.',
  },
]

describe('the volunteer & report page', () => {
  it('offers the way into reporting', async () => {
    const user = userEvent.setup()
    render(<More {...ON_VOLUNTEER} />)

    await user.click(screen.getByRole('button', { name: /report a problem/i }))

    expect(PROPS.onStartReport).toHaveBeenCalledTimes(1)
  })

  it('renders the volunteer surface the shell hands it', () => {
    render(
      <More
        {...ON_VOLUNTEER}
        volunteerScreen={<div data-testid="volunteer-surface" />}
      />,
    )

    expect(screen.getByTestId('volunteer-surface')).toBeInTheDocument()
  })

  it('keeps the volunteer surface off the other pages', () => {
    render(<More {...PROPS} volunteerScreen={<div data-testid="volunteer-surface" />} />)

    expect(screen.queryByTestId('volunteer-surface')).toBe(null)
  })

  it('says nothing about an outbox that is empty', () => {
    render(<More {...ON_VOLUNTEER} />)

    expect(screen.queryByRole('status')).toBe(null)
  })

  it('counts a single waiting report in the singular', () => {
    render(<More {...ON_VOLUNTEER} queuedReportCount={1} />)

    expect(screen.getByRole('status')).toHaveTextContent('1 report waiting to send.')
  })

  it('counts several in the plural', () => {
    render(<More {...ON_VOLUNTEER} queuedReportCount={3} />)

    expect(screen.getByRole('status')).toHaveTextContent('3 reports waiting to send.')
  })
})

// --- A report that will never send (#243) --------------------------------
//
// "Waiting to send" is true right up until it is not, and a phone with a
// wrong clock has every report refused - so without this the app tells
// someone their report is on its way, indefinitely, while it never moves.

describe('the volunteer & report page, when a report was refused for good', () => {
  it('says so, in words, rather than leaving it in the waiting count', () => {
    render(<More {...ON_VOLUNTEER} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent('1 report could not be sent.')
  })

  it('shows the reason, because "failed" alone is not actionable', () => {
    render(<More {...ON_VOLUNTEER} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent(/date and time/i)
  })

  it('promises the writing is not lost, which is the fear this creates', () => {
    render(<More {...ON_VOLUNTEER} stuckReports={STUCK} />)

    expect(screen.getByRole('alert')).toHaveTextContent(/nothing has been lost/i)
  })

  it('keeps the two counts apart', () => {
    // One waiting for signal, one refused. Rolling them together is the bug.
    render(<More {...ON_VOLUNTEER} queuedReportCount={1} stuckReports={STUCK} />)

    expect(screen.getByRole('status')).toHaveTextContent('1 report waiting to send.')
    expect(screen.getByRole('alert')).toHaveTextContent('1 report could not be sent.')
  })

  it('pluralises', () => {
    render(
      <More {...ON_VOLUNTEER} stuckReports={[...STUCK, { id: 'r2', reason: 'Nope.' }]} />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('2 reports could not be sent.')
  })

  it('offers a retry, for the cause a hiker can actually fix', async () => {
    const user = userEvent.setup()
    const onRetryReport = vi.fn()
    render(<More {...ON_VOLUNTEER} stuckReports={STUCK} onRetryReport={onRetryReport} />)

    await user.click(screen.getByRole('button', { name: /try again/i }))

    expect(onRetryReport).toHaveBeenCalledWith('r1')
  })

  it('offers a way out, so a doomed report is not permanent furniture', async () => {
    const user = userEvent.setup()
    const onDiscardReport = vi.fn()
    render(
      <More {...ON_VOLUNTEER} stuckReports={STUCK} onDiscardReport={onDiscardReport} />,
    )

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
    render(
      <More {...ON_VOLUNTEER} stuckReports={STUCK} onDiscardReport={onDiscardReport} />,
    )

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onDiscardReport).not.toHaveBeenCalled()

    // The safe answer disarms and puts the ordinary buttons back.
    await user.click(screen.getByRole('button', { name: /keep it/i }))
    expect(onDiscardReport).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
  })

  it('says nothing when nothing is stuck', () => {
    render(<More {...ON_VOLUNTEER} queuedReportCount={2} />)

    expect(screen.queryByRole('alert')).toBe(null)
  })
})

describe('the moderation entry (#235)', () => {
  it('is absent for an ordinary hiker', () => {
    // Offered on a guess, it costs a 403 the person cannot act on and an app
    // that looks broken. `onOpenModeration` being undefined IS "not a
    // moderator" as far as this screen is concerned.
    render(<More {...ON_VOLUNTEER} />)

    expect(screen.queryByRole('button', { name: /moderation/i })).toBeNull()
  })

  it('appears, and opens the queue, when there is somewhere to go', () => {
    const onOpenModeration = vi.fn()
    render(<More {...ON_VOLUNTEER} onOpenModeration={onOpenModeration} />)

    screen.getByRole('button', { name: /moderation queue/i }).click()

    expect(onOpenModeration).toHaveBeenCalled()
  })
})

// --- Which page shows which group -------------------------------------------
//
// The groups themselves are Settings.test.tsx's job; what is pinned here is
// that every one still has a home after the tabs became destinations, with
// their copy verbatim (#1054).

describe('the five pages', () => {
  it('shows the You groups on the You page', () => {
    render(<More {...PROPS} page="you" onEditHike={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'Your hike' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'You' })).toBeInTheDocument()
  })

  it('shows the map preferences on The map page', () => {
    render(<More {...PROPS} page="map" />)

    expect(screen.getByRole('heading', { name: 'The map' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Display' })).toBeInTheDocument()
  })

  it('shows safety and privacy on its own page', () => {
    render(<More {...PROPS} page="safety" />)

    expect(screen.getByRole('heading', { name: 'Safety & privacy' })).toBeInTheDocument()
  })

  it('shows the reference material on Where this map comes from', () => {
    render(<More {...PROPS} page="sources" />)

    expect(screen.getByRole('heading', { name: 'Your data' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'About this build' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Report a bug' })).toBeInTheDocument()
  })

  it('offers the way home from a sub-page', async () => {
    const user = userEvent.setup()
    render(<More {...PROPS} page="safety" />)

    await user.click(screen.getByRole('button', { name: 'More' }))

    expect(PROPS.onNavigate).toHaveBeenCalledWith('home')
  })
})

// #378. The sources page is where somebody goes looking for it - so the wiring
// is worth a test of its own even though screens/AboutBuild.test.tsx covers
// the rows.
describe('About this build, from the sources page', () => {
  it('says which build the app is running, without being passed one', () => {
    render(<More {...PROPS} page="sources" />)

    expect(screen.getByRole('heading', { name: 'About this build' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /copy build details/i }),
    ).toBeInTheDocument()
  })
})

// --- Where the sync panel sits (#894) --------------------------------------
//
// Which page shows which group is this file's job. The panel's own copy is
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
  it('sits in the You page, under the account it depends on', () => {
    render(
      <More
        {...PROPS}
        page="you"
        account={{ email: 'hiker@example.org' }}
        {...SYNCING}
      />,
    )

    expect(
      screen.getByRole('heading', { name: /what your account has/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('Grayson Highlands')).toBeInTheDocument()
  })

  it('says nothing at all to a hiker who is signed out', () => {
    // There is no account for anything to have reached, and a panel reading
    // "never synced" over a signed-out phone would describe a failure where
    // there is only the app's ordinary premise.
    render(<More {...PROPS} page="you" {...SYNCING} />)

    expect(screen.queryByRole('heading', { name: /what your account has/i })).toBe(null)
  })

  it('says nothing when the shell could not read the sync bookkeeping', () => {
    // Null status is "we could not ask", and this screen would rather say
    // nothing than say the reassuring thing on no evidence.
    render(
      <More
        {...PROPS}
        page="you"
        account={{ email: 'hiker@example.org' }}
        {...SYNCING}
        syncStatus={undefined}
      />,
    )

    expect(screen.queryByRole('heading', { name: /what your account has/i })).toBe(null)
  })

  it('keeps the conditions bucket’s own last-synced row on the sources page', () => {
    // Two different clocks in two different places, deliberately: "Last sent"
    // is the account exchange, "Last synced" is the published-conditions
    // bucket every hiker gets.
    const signedIn = { ...PROPS, account: { email: 'hiker@example.org' }, ...SYNCING }
    const you = render(<More {...signedIn} page="you" />)
    expect(within(you.container).queryByText('Last synced')).toBe(null)
    expect(within(you.container).getByText('Last sent')).toBeInTheDocument()
    cleanup()

    const sources = render(<More {...signedIn} page="sources" />)
    expect(within(sources.container).getByText('Last synced')).toBeInTheDocument()
    expect(within(sources.container).queryByText('Last sent')).toBe(null)
  })
})

const ACCOUNT_DATA = {
  onExportAccount: vi.fn().mockResolvedValue(undefined),
  onDeleteAccount: vi.fn(),
}

describe('taking your data, or leaving (#895)', () => {
  it('sits in the You page, below the sync panel', () => {
    // Export first, delete second, both from one screen - and the
    // irreversible control furthest from the thumb that opened the page.
    render(
      <More
        {...PROPS}
        page="you"
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
    render(<More {...PROPS} page="you" {...SYNCING} {...ACCOUNT_DATA} />)

    expect(screen.queryByRole('heading', { name: /taking your data/i })).toBe(null)
  })

  it('stays on screen after the deletion signs the hiker out', () => {
    // The receipt is unmountable by construction otherwise: deleting signs
    // them out, `account` goes null, and the one screen a hiker is owed
    // disappears in the same tick it was earned.
    render(<More {...PROPS} page="you" {...SYNCING} {...ACCOUNT_DATA} accountDeleted />)

    expect(
      screen.getByRole('heading', { name: /taking your data, or leaving/i }),
    ).toBeInTheDocument()
  })

  it('says nothing on a surface that cannot actually run the deletion', () => {
    // The same rule the sync panel follows: a control with no handler behind
    // it must not be drawn, because there is no honest thing for it to do.
    render(
      <More
        {...PROPS}
        page="you"
        account={{ email: 'hiker@example.org' }}
        {...SYNCING}
      />,
    )

    expect(screen.queryByRole('heading', { name: /taking your data/i })).toBe(null)
  })
})

// --- The GPS trace recorder's door (#1180) ---------------------------------

describe('the GPS trace section on Safety & privacy', () => {
  const TRACE = {
    status: {
      recording: false,
      startedAt: null,
      marker: null,
      samples: 0,
      lastSampleAt: null,
      lastAccuracyM: null,
      lastAccuracyConfidence: null,
    },
    onStart: vi.fn(),
    onStop: vi.fn(),
    onMark: vi.fn(),
    onExport: vi.fn(),
    onDelete: vi.fn(),
  }

  const withLocation = {
    ...PROPS.preferences,
    location_permission_requested: true,
  }

  it('is absent from a build that does not wire it', () => {
    // An instrument, not a feature. A caller that passes nothing gets the
    // page every test written before now expects.
    render(<More {...PROPS} page="safety" preferences={withLocation} />)

    expect(
      screen.queryByRole('heading', { name: 'Record a GPS trace' }),
    ).not.toBeInTheDocument()
  })

  it('appears under Use my location once it is wired and location is on', () => {
    render(<More {...PROPS} page="safety" preferences={withLocation} gpsTrace={TRACE} />)

    expect(
      screen.getByRole('heading', { name: 'Record a GPS trace' }),
    ).toBeInTheDocument()
  })

  it('stays hidden while location is off, rather than offering a button that records nothing', () => {
    // With the switch off there is no watch to tap - useGeolocation returns
    // `idle` and registers nothing - so a Start button would look exactly
    // like one that worked and produce an empty file. A tester finding that
    // out afterwards has lost the walk.
    render(
      <More
        {...PROPS}
        page="safety"
        preferences={{ ...PROPS.preferences, location_permission_requested: false }}
        gpsTrace={TRACE}
      />,
    )

    expect(
      screen.queryByRole('heading', { name: 'Record a GPS trace' }),
    ).not.toBeInTheDocument()
  })

  it('comes BACK while a recording is open, so Stop is still reachable', () => {
    // #1201. The test above is right and was half a rule: hidden while
    // location is off is correct when nothing is recording, and takes the
    // app's only Stop button away when something is. Turning the switch off
    // mid-walk left a recording open that the hiker could not close without
    // turning location back on first.
    render(
      <More
        {...PROPS}
        page="safety"
        preferences={{ ...PROPS.preferences, location_permission_requested: false }}
        gpsTrace={{
          ...TRACE,
          status: { ...TRACE.status, recording: true, startedAt: 0 },
        }}
      />,
    )

    expect(screen.getByRole('button', { name: 'Stop recording' })).toBeInTheDocument()
  })

  it('keeps the finished trace reachable after Stop, with location still off', () => {
    // The half the first #1201 fix left standing, and the worse half. Adding
    // `recording` kept Stop on screen; tapping it - which is what the note
    // beside it advises - set `recording` false and took the section away
    // again, this time with the Save and Delete buttons. A finished walk of
    // 412 readings then had no way out of the phone, under a sentence saying
    // nothing recorded so far is lost.
    render(
      <More
        {...PROPS}
        page="safety"
        preferences={{ ...PROPS.preferences, location_permission_requested: false }}
        gpsTrace={{
          ...TRACE,
          status: { ...TRACE.status, recording: false, startedAt: 0, samples: 412 },
        }}
      />,
    )

    expect(
      screen.getByRole('button', { name: /save the recording/i }),
    ).toBeInTheDocument()
  })

  it('is still absent with location off and nothing recorded', () => {
    // The original rule, which is still right: with no trace and no recording
    // there is nothing to reach, and a Start button that records nothing is
    // what the gate exists to prevent.
    render(
      <More
        {...PROPS}
        page="safety"
        preferences={{ ...PROPS.preferences, location_permission_requested: false }}
        gpsTrace={{ ...TRACE, status: { ...TRACE.status, recording: false, samples: 0 } }}
      />,
    )

    expect(
      screen.queryByRole('heading', { name: 'Record a GPS trace' }),
    ).not.toBeInTheDocument()
  })

  it('does not put it on any other page', () => {
    render(<More {...PROPS} page="you" preferences={withLocation} gpsTrace={TRACE} />)

    expect(
      screen.queryByRole('heading', { name: 'Record a GPS trace' }),
    ).not.toBeInTheDocument()
  })
})
