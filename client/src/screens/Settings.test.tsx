import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Settings } from './Settings'
import { DEFAULT_PREFERENCES } from '../lib/userPreferences'

// WIREFRAMES.md §10. Five groups, one canonical UserPreferences model.
//
// The account row landed in Phase E5. Signing out must never destroy what is
// on the phone: the map, the outbox and the preferences are all local first
// and an account only syncs them (IDENTITY_AND_PRIVACY.md). An app that wiped
// a queued report because someone signed out would be losing work they had
// no reason to think was at risk.
//
// The schema-level guarantee that no closures/warnings toggle can exist lives
// in lib/userPreferences.test.ts, where TESTING.md item 16 says to put it.
// What is tested here is the visible half: the locked red callout that tells
// someone why they cannot find the switch they went looking for.

const PROPS = {
  account: null as { email: string } | null,
  reporterType: 'thru' as const,
  onSignIn: vi.fn(),
  onSignOut: vi.fn(),
  preferences: DEFAULT_PREFERENCES,
  onChange: vi.fn(),
  lastSyncedAt: new Date('2026-07-29T09:00:00Z'),
  onSync: vi.fn(),
  onExport: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Settings', () => {
  it('lays out the groups WIREFRAMES.md names', () => {
    render(<Settings {...PROPS} />)

    for (const group of ['You', 'The map', 'Display', 'Safety & privacy', 'Your data']) {
      expect(screen.getByRole('heading', { name: group })).toBeInTheDocument()
    }
  })

  it('states that closures and serious warnings are always shown', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/always shown/i)).toHaveTextContent(
      /closures and serious warnings/i,
    )
  })

  it('says the absence of a switch is deliberate, not an oversight', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/no switch, here or anywhere/i)).toBeInTheDocument()
  })

  it('renders no control at all for closures or warnings', () => {
    render(<Settings {...PROPS} />)
    const toggles = screen
      .getAllByRole('checkbox')
      .map((el) => el.getAttribute('name') ?? '')

    expect(toggles.filter((name) => /closure|warning/i.test(name))).toEqual([])
  })

  it('offers the wrong-way alert toggle, which IS a real preference', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByRole('checkbox', { name: /wrong-way alert/i })).toBeInTheDocument()
  })

  it('reports a wrong-way toggle change against the canonical field name', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('checkbox', { name: /wrong-way alert/i }))

    expect(PROPS.onChange).toHaveBeenCalledWith({ wrong_way_alert_enabled: false })
  })

  it('shows the offline topo basemap as the current background source', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/USGS topo/i)).toBeInTheDocument()
  })

  it('marks the offline basemap as the only one that works without signal', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/only.*offline|works with no signal/i)).toBeInTheDocument()
  })

  it('tags not-yet-built rows "Later" rather than hiding them', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getAllByText('Later').length).toBeGreaterThan(0)
  })

  it('disables the Later rows so they cannot be operated', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByRole('checkbox', { name: /roads & walkability/i })).toBeDisabled()
  })

  it('offers sign-in when signed out', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(PROPS.onSignIn).toHaveBeenCalled()
  })

  it('shows the account and offers sign-out when signed in', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} account={{ email: 'pat@example.org' }} />)

    expect(screen.getByText('pat@example.org')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /sign out/i }))

    expect(PROPS.onSignOut).toHaveBeenCalled()
  })

  it('says the trail name lives only on this device while signed out', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/on this device/i)).toBeInTheDocument()
  })

  it('says the trail name is linked once an account exists', () => {
    render(
      <Settings
        {...PROPS}
        account={{ email: 'pat@example.org' }}
        preferences={{ ...DEFAULT_PREFERENCES, trail_name: 'Switchback' }}
      />,
    )

    expect(screen.getByText(/linked/i)).toBeInTheDocument()
  })

  it('promises signing out keeps the map, the outbox and the settings', () => {
    // The assurance that matters most on this screen. Someone who believes
    // signing out might discard a queued report simply will not sign out.
    render(<Settings {...PROPS} account={{ email: 'pat@example.org' }} />)

    expect(
      screen.getByText(/stays on this phone|nothing is deleted/i),
    ).toBeInTheDocument()
  })

  it('shows the reporter type reports are signed with', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/thru-hiker/i)).toBeInTheDocument()
  })

  it('says a maintainer claim is still unverified', () => {
    render(<Settings {...PROPS} reporterType="maintainer" />)

    expect(screen.getByText(/unverified/i)).toBeInTheDocument()
  })

  it('still says reading the map needs no account, even on the account row', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/never needs an account/i)).toBeInTheDocument()
  })

  it('shows when data last synced, and offers to sync now', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /^sync$/i }))

    expect(PROPS.onSync).toHaveBeenCalledTimes(1)
  })

  it('says the data has never synced rather than leaving it blank', () => {
    render(<Settings {...PROPS} lastSyncedAt={null} />)

    expect(screen.getByText(/never synced/i)).toBeInTheDocument()
  })

  it('offers export in both formats the wireframe names', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /GPX/i }))

    expect(PROPS.onExport).toHaveBeenCalledWith('gpx')
    expect(screen.getByRole('button', { name: /GeoJSON/i })).toBeInTheDocument()
  })

  it('credits the data sources, which the licences require', () => {
    render(<Settings {...PROPS} />)

    expect(screen.getByText(/OpenStreetMap/i)).toBeInTheDocument()
  })

  it('exports GeoJSON as well as GPX', async () => {
    const user = userEvent.setup()
    render(<Settings {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /GeoJSON/i }))

    expect(PROPS.onExport).toHaveBeenCalledWith('geojson')
  })

  it('shows a reporter type it has no label for rather than a blank', () => {
    // The set of reporter types can grow server-side ahead of this build.
    render(<Settings {...PROPS} reporterType={'ridgerunner' as 'thru'} />)

    expect(screen.getByText('ridgerunner')).toBeInTheDocument()
  })
})
