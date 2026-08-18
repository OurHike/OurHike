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
  refusedTap: false,
  fixedEnd: null as { mile: number; name?: string } | null,
  trailMiles: 2197.4,
  units: 'imperial' as const,
  onAsk: vi.fn(),
  onMiles: vi.fn(),
  onDays: vi.fn(),
  onSouth: vi.fn(),
  onPickStart: vi.fn(),
  onPickEnd: vi.fn(),
  onClearEnd: vi.fn(),
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
    expect(screen.getByLabelText('Miles of trail')).toHaveValue(45)
    expect(screen.getByText(/of trail — type it, or drag/)).toBeInTheDocument()
    expect(screen.getByText('Ends near')).toBeInTheDocument()
    expect(screen.getByText('Old Orchard Shelter')).toBeInTheDocument()
    expect(screen.getByText('Shelter · mi 516.1')).toBeInTheDocument()
  })

  it('offers the doors as things you can see, GPS only when it can be honest', () => {
    // #801: the three 11-px words this replaced were the same size and
    // weight as their own caption, and were missed outright.
    const { rerender } = render(<RouteEntranceSheet {...PROPS} />)

    for (const door of ['Where I am', 'Pick on the map'] as const) {
      expect(screen.getByRole('button', { name: door })).toBeEnabled()
    }
    rerender(<RouteEntranceSheet {...PROPS} gpsUsable={false} />)
    expect(screen.getByRole('button', { name: 'Where I am' })).toBeDisabled()
  })

  it('says the map takes a tap with no button pressed first', () => {
    render(<RouteEntranceSheet {...PROPS} />)
    expect(screen.getByText(/just tap the trail on the map/)).toBeInTheDocument()
  })

  it('says a refused tap out loud rather than doing nothing', () => {
    render(<RouteEntranceSheet {...PROPS} refusedTap />)
    expect(screen.getByText(/more than 3 mi off the trail/)).toBeInTheDocument()
  })

  it('routes each door to the shell', async () => {
    const user = userEvent.setup()
    render(<RouteEntranceSheet {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'Where I am' }))
    expect(PROPS.onPickStart).toHaveBeenLastCalledWith('gps')
    await user.click(screen.getByRole('button', { name: 'Pick on the map' }))
    expect(PROPS.onPickStart).toHaveBeenLastCalledWith('map')
    // The field itself is the search door too - tapping what you want to
    // change is the anatomy every phone teaches.
    await user.click(screen.getByRole('button', { name: /Damascus/ }))
    expect(PROPS.onPickStart).toHaveBeenLastCalledWith('search')
  })

  it('says the days conversion out loud, with the target named', () => {
    render(<RouteEntranceSheet {...PROPS} ask="long" reachMi={45.3} />)

    expect(screen.getByLabelText('Days on trail')).toHaveValue(3)
    expect(screen.getByText(/on trail — type it, or drag/)).toBeInTheDocument()
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
    expect(screen.getByText(/of trail — type it, or drag/)).toBeInTheDocument()
    expect(
      screen.getByText(/Sizing by days needs the elevation profile/),
    ).toBeInTheDocument()
  })

  it('moves the sliders and the direction through the shell', () => {
    const { rerender } = render(<RouteEntranceSheet {...PROPS} />)

    fireEvent.change(screen.getByLabelText('Miles of trail, slider'), {
      target: { value: '25' },
    })
    expect(PROPS.onMiles).toHaveBeenCalledWith(25)

    rerender(<RouteEntranceSheet {...PROPS} ask="long" />)
    fireEvent.change(screen.getByLabelText('Days on trail, slider'), {
      target: { value: '5' },
    })
    expect(PROPS.onDays).toHaveBeenCalledWith(5)

    fireEvent.click(screen.getByRole('button', { name: 'South' }))
    expect(PROPS.onSouth).toHaveBeenCalledWith(true)
  })

  it('cannot use a stretch that has no start or no end', () => {
    const { rerender } = render(<RouteEntranceSheet {...PROPS} start={null} end={null} />)

    expect(screen.getByText(/Shelter, town, or/)).toBeInTheDocument()
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

describe('no ceiling on the answer (#804)', () => {
  it('runs the slider to the trail’s own length, from the download', () => {
    render(<RouteEntranceSheet {...PROPS} />)
    expect(screen.getByLabelText('Miles of trail, slider')).toHaveAttribute(
      'max',
      '2197.4',
    )
  })

  it('runs the days slider to a leap year', () => {
    render(<RouteEntranceSheet {...PROPS} ask="long" />)
    expect(screen.getByLabelText('Days on trail, slider')).toHaveAttribute('max', '366')
  })

  it('keeps a typed answer past the slider, and says what will happen to it', () => {
    render(<RouteEntranceSheet {...PROPS} miles={2500} />)

    // The number the hiker typed is still on screen, unreduced.
    expect(screen.getByLabelText('Miles of trail')).toHaveValue(2500)
    expect(screen.getByText(/Past the end of the trail/)).toBeInTheDocument()
    expect(screen.getByText(/haven’t shortened your answer/)).toBeInTheDocument()
    // ...and the slider simply pegs.
    expect(screen.getByLabelText('Miles of trail, slider')).toHaveValue('2197.4')
  })

  it('takes any number from the field', () => {
    render(<RouteEntranceSheet {...PROPS} />)
    fireEvent.change(screen.getByLabelText('Miles of trail'), {
      target: { value: '2189' },
    })
    expect(PROPS.onMiles).toHaveBeenCalledWith(2189)
  })
})

describe('naming an end (#804)', () => {
  const END = { mile: 1025.0, name: 'Harpers Ferry' }

  it('offers an end, and it is optional', async () => {
    const user = userEvent.setup()
    render(<RouteEntranceSheet {...PROPS} />)

    expect(screen.getByText(/Somewhere particular\?/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Somewhere particular/ }))
    expect(PROPS.onPickEnd).toHaveBeenCalled()
  })

  it('states the distance instead of asking for it, once both ends are named', () => {
    render(<RouteEntranceSheet {...PROPS} fixedEnd={END} />)

    // 1025.0 - 470.8. Asking "how far" here would be asking a question the
    // sheet can already answer.
    expect(screen.getByText('554.2 mi')).toBeInTheDocument()
    expect(screen.getByText(/Damascus → Harpers Ferry · north/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'How far' })).toBeNull()
    expect(screen.queryByLabelText('Miles of trail')).toBeNull()
  })

  it('says the day count is an aid, not a claim about this hiker', () => {
    render(<RouteEntranceSheet {...PROPS} fixedEnd={END} />)
    expect(screen.getByText(/at a 15-mile day/)).toBeInTheDocument()
    expect(
      screen.getByText(/days you actually have are the next screen/),
    ).toBeInTheDocument()
  })

  it('lets a named end be cleared, going back to how far', async () => {
    const user = userEvent.setup()
    render(<RouteEntranceSheet {...PROPS} fixedEnd={END} />)

    await user.click(screen.getByRole('button', { name: /Harpers Ferry/ }))
    expect(PROPS.onClearEnd).toHaveBeenCalled()
  })
})
