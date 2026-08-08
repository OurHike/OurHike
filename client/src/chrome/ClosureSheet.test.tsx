import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { ClosureSheet } from './ClosureSheet'

// WIREFRAMES.md §7 and TESTING.md item 10.
//
// Two things this sheet must do that are easy to skip:
//
// 1. Say OurHike does not compute detours. Saying nothing invites someone to
//    assume the app is routing them around a closure, which is the one wrong
//    belief that could put them somewhere worse than the closed trail.
//
// 2. Carry its own sync age. A downloaded map is at its most dangerous when
//    it is stale specifically about closures - the trail may have reopened,
//    or far worse, closed since. The age belongs on the closure itself, not
//    buried in a global status strip.

const CLOSURE = {
  id: 'c1',
  reason_type: 'storm_damage' as const,
  note: 'Bridge washed out at the creek crossing.',
  status: 'closed' as const,
  start_mile_marker: 1408.6,
  end_mile_marker: 1411.0,
  closed_since: new Date('2026-07-10T00:00:00Z'),
  expected_reopen: new Date('2026-09-01T00:00:00Z'),
  reroute_url: 'https://example.org/reroute',
}

const PROPS = {
  closure: CLOSURE,
  lastSyncedAt: new Date('2026-07-26T12:00:00Z'),
  now: new Date('2026-07-29T12:00:00Z'),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ClosureSheet', () => {
  it('gives the reason in plain language', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.getByText(/Storm damage/)).toBeInTheDocument()
  })

  it('includes the marker note when there is one', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.getByText(/Bridge washed out/)).toBeInTheDocument()
  })

  it('shows the mile range', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.getByText(/1,408\.6 – 1,411\.0/)).toBeInTheDocument()
  })

  it('shows the status', () => {
    // Exact: "Closed since July 10" is a different line and would otherwise
    // satisfy a loose /closed/i match without the status ever being rendered.
    render(<ClosureSheet {...PROPS} />)

    expect(screen.getByText('Closed')).toBeInTheDocument()
  })

  it('shows closed-since and expected reopen', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.getByText(/July 10/)).toBeInTheDocument()
    expect(screen.getByText(/September 1/)).toBeInTheDocument()
  })

  // `marked_by` used to be asserted here, and it was the only one of the four
  // extras that named a person (#245). Its sources were profile ids whose
  // display names sit behind an anonymity position the app has stored and not
  // applied, so the field was deleted rather than wired. This replaces the
  // assertion instead of dropping it: the point now is that the sheet says
  // nothing at all about who marked the closure.
  it('attributes the closure to nobody', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.queryByText(/Marked by/)).not.toBeInTheDocument()
  })

  it('links to the club’s reroute notice when there is one', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.getByRole('link', { name: /reroute/i })).toHaveAttribute(
      'href',
      CLOSURE.reroute_url,
    )
  })

  it('states plainly that OurHike does not compute detours', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.getByText(/does not.*detour|no detour/i)).toBeInTheDocument()
  })

  it('offers no detour or reroute-me control of its own', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.queryByRole('button', { name: /route|detour|navigate/i })).toBe(null)
  })

  it('carries its own sync age, not just a global one', () => {
    render(<ClosureSheet {...PROPS} />)

    expect(screen.getByText(/3d ago|3 days/i)).toBeInTheDocument()
  })

  it('says the copy has never synced rather than implying it is current', () => {
    render(<ClosureSheet {...PROPS} lastSyncedAt={null} />)

    expect(screen.getByText(/never synced/i)).toBeInTheDocument()
  })

  it('offers no way to hide the closure', () => {
    // show_closures is not a setting anywhere - see lib/userPreferences.
    render(<ClosureSheet {...PROPS} />)

    expect(screen.queryByRole('button', { name: /hide|dismiss.*closure/i })).toBe(null)
  })

  it('still warns when a reroute is available - that is not an all-clear', () => {
    render(
      <ClosureSheet {...PROPS} closure={{ ...CLOSURE, status: 'reroute_available' }} />,
    )

    expect(screen.getByText(/reroute available/i)).toBeInTheDocument()
    expect(screen.getByText(/does not.*detour|no detour/i)).toBeInTheDocument()
  })

  it('omits the reopen line rather than guessing when none is known', () => {
    render(<ClosureSheet {...PROPS} closure={{ ...CLOSURE, expected_reopen: null }} />)

    expect(screen.queryByText(/expected/i)).toBe(null)
  })
})
