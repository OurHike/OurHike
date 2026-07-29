import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Settings } from './Settings'
import { DEFAULT_PREFERENCES } from '../lib/userPreferences'

// WIREFRAMES.md §10. Five groups, one canonical UserPreferences model.
//
// The account row is deliberately absent here - it needs the backend, and is
// Phase E5 of the build plan.
//
// The schema-level guarantee that no closures/warnings toggle can exist lives
// in lib/userPreferences.test.ts, where TESTING.md item 16 says to put it.
// What is tested here is the visible half: the locked red callout that tells
// someone why they cannot find the switch they went looking for.

const PROPS = {
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

  it('has no account row yet - that needs the backend', () => {
    render(<Settings {...PROPS} />)

    expect(screen.queryByRole('button', { name: /sign in|account/i })).toBe(null)
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
})
