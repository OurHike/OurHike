// Tests for the route entrance (#755, the "route by destination" flow's
// front door): the honesty seams - the days conversion said out loud, days
// withheld without a profile, the snap shown with its own name and mile,
// the pre-#753 refusal - and the plumbing of every door and toggle.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RouteEntranceSheet } from './RouteEntranceSheet'

const PROPS = {
  start: { mile: 470.8, name: 'Damascus' },
  ask: 'far' as const,
  miles: 45,
  days: 3,
  south: false,
  end: { mile: 516.1, name: 'Old Orchard Shelter', kind: 'shelter' as const },
  reachMi: null,
  hoursTarget: 7,
  daysUsable: true,
  gpsUsable: true,
  refused: false,
  units: 'imperial' as const,
  onAsk: vi.fn(),
  onMiles: vi.fn(),
  onDays: vi.fn(),
  onSouth: vi.fn(),
  onPickStart: vi.fn(),
  onUse: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the entrance', () => {
  it('shows the start, the question and the snapped end', () => {
    render(<RouteEntranceSheet {...PROPS} />)

    expect(screen.getByText('Where from?')).toBeInTheDocument()
    expect(screen.getByText('Damascus')).toBeInTheDocument()
    expect(screen.getByText('mi 470.8')).toBeInTheDocument()
    expect(screen.getByText('45 mi')).toBeInTheDocument()
    expect(screen.getByText('of trail')).toBeInTheDocument()
    expect(screen.getByText('Ends near')).toBeInTheDocument()
    expect(screen.getByText('Old Orchard Shelter')).toBeInTheDocument()
    expect(screen.getByText('Shelter · mi 516.1')).toBeInTheDocument()
  })

  it('offers all three doors to a start, GPS only when it can be honest', () => {
    const { rerender } = render(<RouteEntranceSheet {...PROPS} />)

    for (const door of ['where I am', 'search', 'map'] as const) {
      expect(screen.getByRole('button', { name: door })).toBeEnabled()
    }
    rerender(<RouteEntranceSheet {...PROPS} gpsUsable={false} />)
    expect(screen.getByRole('button', { name: 'where I am' })).toBeDisabled()
  })

  it('routes each door to the shell', async () => {
    const user = userEvent.setup()
    render(<RouteEntranceSheet {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'where I am' }))
    expect(PROPS.onPickStart).toHaveBeenLastCalledWith('gps')
    await user.click(screen.getByRole('button', { name: 'map' }))
    expect(PROPS.onPickStart).toHaveBeenLastCalledWith('map')
    // The field itself is the search door too - tapping what you want to
    // change is the anatomy every phone teaches.
    await user.click(screen.getByRole('button', { name: /Damascus/ }))
    expect(PROPS.onPickStart).toHaveBeenLastCalledWith('search')
  })

  it('says the days conversion out loud, with the target named', () => {
    render(<RouteEntranceSheet {...PROPS} ask="long" reachMi={45.3} />)

    expect(screen.getByText('3 days')).toBeInTheDocument()
    expect(screen.getByText('on trail')).toBeInTheDocument()
    expect(
      screen.getByText(/3 days at your 7h-walking target reaches/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/yours to change when the days are laid out/),
    ).toBeInTheDocument()
    expect(screen.getByText(/≈ 45 mi/)).toBeInTheDocument()
  })

  it('withholds days without a profile and says why - miles it is', () => {
    render(<RouteEntranceSheet {...PROPS} ask="long" daysUsable={false} />)

    expect(screen.getByRole('button', { name: 'How long' })).toBeDisabled()
    // The ask falls back to miles rather than pricing climbs at zero.
    expect(screen.getByText('of trail')).toBeInTheDocument()
    expect(
      screen.getByText(/Sizing by days needs the elevation profile/),
    ).toBeInTheDocument()
  })

  it('moves the sliders and the direction through the shell', () => {
    const { rerender } = render(<RouteEntranceSheet {...PROPS} />)

    fireEvent.change(screen.getByLabelText('Miles of trail'), { target: { value: '25' } })
    expect(PROPS.onMiles).toHaveBeenCalledWith(25)

    rerender(<RouteEntranceSheet {...PROPS} ask="long" />)
    fireEvent.change(screen.getByLabelText('Days on trail'), { target: { value: '5' } })
    expect(PROPS.onDays).toHaveBeenCalledWith(5)

    fireEvent.click(screen.getByRole('button', { name: 'South' }))
    expect(PROPS.onSouth).toHaveBeenCalledWith(true)
  })

  it('cannot use a stretch that has no start or no end', () => {
    const { rerender } = render(<RouteEntranceSheet {...PROPS} start={null} end={null} />)

    expect(screen.getByText('Pick a start')).toBeInTheDocument()
    expect(screen.getByText('pick a start first')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use this stretch' })).toBeDisabled()

    rerender(<RouteEntranceSheet {...PROPS} end={null} />)
    expect(screen.getByText('nothing that way in this download')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use this stretch' })).toBeDisabled()
  })

  it('shows a bare-mile end as exactly that, never dressed as a stop', () => {
    render(<RouteEntranceSheet {...PROPS} end={{ mile: 490.2 }} />)

    expect(screen.getByText('mi 490.2')).toBeInTheDocument()
    expect(screen.getByText(/no shelter or campsite nearby/)).toBeInTheDocument()
  })

  it('refuses a pre-#753 download whole, controls withheld', () => {
    render(<RouteEntranceSheet {...PROPS} refused={true} />)

    expect(screen.getByText(/predates trail miles/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Use this stretch' })).toBeNull()
    expect(screen.queryByLabelText('Miles of trail')).toBeNull()
  })

  it('never prints an arrival clock', () => {
    const { container } = render(
      <RouteEntranceSheet {...PROPS} ask="long" reachMi={45.3} />,
    )
    expect(container.textContent).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)/i)
  })
})
