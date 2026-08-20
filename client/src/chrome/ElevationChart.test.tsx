import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ElevationChart } from './ElevationChart'
import type { ElevationProfile } from '../lib/elevationProfile'

// The chart's claims are numbers a hiker plans a day around, so the tests
// pin the numbers: a known ramp profile whose gain, loss and Naismith time
// are computable by hand, dragged over with a stubbed geometry so a clientX
// IS a mile times ten.

/** Miles 0..100 at 0.1 mi spacing: a steady climb from 1,000 ft to 2,000 ft
 *  over the first fifty miles, then a steady descent to 800 ft. Northbound
 *  20 -> 70 therefore gains exactly 600 ft and loses exactly 480 ft. */
function rampProfile(): ElevationProfile {
  const count = 1001
  const distanceMi = new Float32Array(count)
  const elevationFt = new Float32Array(count)
  for (let i = 0; i < count; i += 1) {
    distanceMi[i] = i / 10
    elevationFt[i] = i <= 500 ? 1000 + i * 2 : 2000 - (i - 500) * 2.4
  }
  return { distanceMi, elevationFt }
}

/** The plot div measured as exactly 1,000px wide at x=0, so clientX 200 is
 *  20% of the width - mile 20 of this 100-mile profile. */
let rectSpy: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  rectSpy = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: 1000,
    bottom: 150,
    width: 1000,
    height: 150,
    toJSON: () => ({}),
  } as DOMRect)
})

afterEach(() => {
  rectSpy.mockRestore()
  cleanup()
})

function plot(): HTMLElement {
  return screen.getByRole('application')
}

function dragStretch(fromX: number, toX: number): void {
  fireEvent.pointerDown(plot(), { clientX: fromX, pointerId: 1 })
  fireEvent.pointerMove(plot(), { clientX: toX, pointerId: 1 })
  fireEvent.pointerUp(plot(), { clientX: toX, pointerId: 1 })
}

describe('ElevationChart', () => {
  it('rests on the whole profile with no fix and invites a selection', () => {
    render(<ElevationChart profile={rampProfile()} />)

    expect(screen.getByText('mi 0.0 – 100.0')).toBeInTheDocument()
    expect(screen.getByText('100.0 mi')).toBeInTheDocument()
    expect(screen.getByText('Drag to measure a stretch')).toBeInTheDocument()
    // No fix, no you-are-here rule - and no pretence of one.
    expect(screen.queryByTestId('chart-you-are-here')).not.toBeInTheDocument()
  })

  it('draws the you-are-here rule when a profile-axis mile is known', () => {
    render(<ElevationChart profile={rampProfile()} currentMile={30} />)
    expect(screen.getByTestId('chart-you-are-here')).toBeInTheDocument()
  })

  it('reports the hovered mile and shows its readout', () => {
    const onHoverMile = vi.fn()
    render(<ElevationChart profile={rampProfile()} onHoverMile={onHoverMile} />)

    fireEvent.pointerMove(plot(), { clientX: 300, pointerId: 1 })

    // Hover is continuous, so the reported mile is float arithmetic, not a
    // snapped sample - near 30, not necessarily exactly 30.
    const lastHover = onHoverMile.mock.calls.at(-1)?.[0] as number
    expect(lastHover).toBeCloseTo(30, 6)
    // Mile 30 on the ramp is 1,600 ft.
    expect(screen.getByTestId('chart-readout')).toHaveTextContent('mi 30.0 · 1,600 ft')

    fireEvent.pointerLeave(plot())
    expect(onHoverMile).toHaveBeenLastCalledWith(null)
    expect(screen.queryByTestId('chart-readout')).not.toBeInTheDocument()
  })

  it('measures a dragged stretch: distance, gain, loss and a ≈time that is never a clock', () => {
    const onSelectStretch = vi.fn()
    render(<ElevationChart profile={rampProfile()} onSelectStretch={onSelectStretch} />)

    dragStretch(200, 700)

    expect(onSelectStretch).toHaveBeenLastCalledWith({ startMile: 20, endMile: 70 })
    expect(screen.getByText('mi 20.0 – 70.0')).toBeInTheDocument()
    expect(screen.getByText('50.0 mi')).toBeInTheDocument()
    expect(screen.getByText('↑ 600 ft')).toBeInTheDocument()
    expect(screen.getByText('↓ 480 ft')).toBeInTheDocument()
    // 50 mi at 5 km/h plus an hour per 600 m of the 600 ft climbed, rounded
    // to five minutes: ≈16h 25m. Moving time, said so, and no clock digits.
    const time = screen.getByText('≈16h 25m walking')
    expect(time).toBeInTheDocument()
    expect(time.textContent).not.toMatch(/:\d\d|am|pm/i)
  })

  it('re-walks the stretch southbound rather than assuming a direction is harmless', async () => {
    render(<ElevationChart profile={rampProfile()} />)
    dragStretch(200, 700)

    await userEvent.click(screen.getByRole('button', { name: /northbound/i }))

    // Southbound the same ground climbs 480 and descends 600, and the walk
    // is 20 minutes shorter - the direction is load-bearing, not a label.
    expect(screen.getByText('↑ 480 ft')).toBeInTheDocument()
    expect(screen.getByText('↓ 600 ft')).toBeInTheDocument()
    expect(screen.getByText('≈16h 20m walking')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /southbound/i })).toBeInTheDocument()
  })

  it('clears the selection on a click that never travelled', () => {
    const onSelectStretch = vi.fn()
    render(<ElevationChart profile={rampProfile()} onSelectStretch={onSelectStretch} />)

    dragStretch(200, 700)
    expect(screen.getByTestId('chart-selection')).toBeInTheDocument()

    fireEvent.pointerDown(plot(), { clientX: 400, pointerId: 1 })
    fireEvent.pointerUp(plot(), { clientX: 400, pointerId: 1 })

    expect(onSelectStretch).toHaveBeenLastCalledWith(null)
    expect(screen.queryByTestId('chart-selection')).not.toBeInTheDocument()
  })

  it('zooms to the stretch and comes back to the whole trail', async () => {
    render(<ElevationChart profile={rampProfile()} />)
    dragStretch(200, 700)

    await userEvent.click(screen.getByRole('button', { name: 'Zoom to stretch' }))

    // 20-70 padded by 8% of its span each side: 16-74.
    expect(screen.queryByText('mi 0.0 – 100.0')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Whole trail' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Whole trail' }))
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }))
    expect(screen.getByText('mi 0.0 – 100.0')).toBeInTheDocument()
  })

  it('moves the cursor and clears with the keyboard', () => {
    const onHoverMile = vi.fn()
    const onSelectStretch = vi.fn()
    render(
      <ElevationChart
        profile={rampProfile()}
        onHoverMile={onHoverMile}
        onSelectStretch={onSelectStretch}
      />,
    )

    // From the centre of the domain, one step right is 1% of 100 miles.
    fireEvent.keyDown(plot(), { key: 'ArrowRight' })
    expect(onHoverMile).toHaveBeenLastCalledWith(51)

    fireEvent.keyDown(plot(), { key: 'ArrowRight', shiftKey: true })
    expect(onSelectStretch).toHaveBeenLastCalledWith({ startMile: 51, endMile: 52 })

    fireEvent.keyDown(plot(), { key: 'Escape' })
    expect(onSelectStretch).toHaveBeenLastCalledWith(null)
  })

  it('renders nothing rather than an empty frame when the profile has no samples', () => {
    const empty: ElevationProfile = {
      distanceMi: new Float32Array(0),
      elevationFt: new Float32Array(0),
    }
    const { container } = render(<ElevationChart profile={empty} />)
    expect(container).toBeEmptyDOMElement()
  })

  // --- The controlled selection (PR #885 review) ---------------------------
  //
  // While the route builder is open the shell owns the selection and the
  // direction, so a stop typed into the builder selects here and a drag here
  // re-stretches the route. The chart's job narrows to rendering what it is
  // handed and reporting what the hiker did.

  it('renders a controlled selection, unsnapped, with its figures', () => {
    render(
      <ElevationChart
        profile={rampProfile()}
        selection={{ startMile: 20, endMile: 70 }}
        southbound={false}
      />,
    )

    expect(screen.getByTestId('chart-selection')).toBeInTheDocument()
    expect(screen.getByText('mi 20.0 – 70.0')).toBeInTheDocument()
    expect(screen.getByText('↑ 600 ft')).toBeInTheDocument()
    expect(screen.getByText('≈16h 25m walking')).toBeInTheDocument()
  })

  it('reads a controlled direction and asks the shell to turn the route around', async () => {
    const onToggleSouthbound = vi.fn()
    render(
      <ElevationChart
        profile={rampProfile()}
        selection={{ startMile: 20, endMile: 70 }}
        southbound={true}
        onToggleSouthbound={onToggleSouthbound}
      />,
    )

    // Southbound figures for the same ground - the direction arrived, not
    // a local default.
    expect(screen.getByText('↑ 480 ft')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /southbound/i }))
    expect(onToggleSouthbound).toHaveBeenCalledTimes(1)
    // And nothing flipped locally - the shell decides what turning means.
    expect(screen.getByText('↑ 480 ft')).toBeInTheDocument()
  })

  it('will not let a click or Escape unmake a route', () => {
    const onSelectStretch = vi.fn()
    render(
      <ElevationChart
        profile={rampProfile()}
        selection={{ startMile: 20, endMile: 70 }}
        southbound={false}
        selectionFromPlan
        onSelectStretch={onSelectStretch}
      />,
    )

    fireEvent.pointerDown(plot(), { clientX: 400, pointerId: 1 })
    fireEvent.pointerUp(plot(), { clientX: 400, pointerId: 1 })
    fireEvent.keyDown(plot(), { key: 'Escape' })

    expect(onSelectStretch).not.toHaveBeenCalled()
    expect(screen.getByTestId('chart-selection')).toBeInTheDocument()
    // Clearing is the builder's close, so the Clear control steps aside -
    // and the row says whose selection this is.
    expect(screen.queryByRole('button', { name: 'Clear' })).not.toBeInTheDocument()
    expect(screen.getByText('route')).toBeInTheDocument()
  })

  it('still reports a drag over a route - the override the review asked for', () => {
    const onSelectStretch = vi.fn()
    render(
      <ElevationChart
        profile={rampProfile()}
        selection={{ startMile: 20, endMile: 70 }}
        southbound={false}
        selectionFromPlan
        onSelectStretch={onSelectStretch}
      />,
    )

    dragStretch(100, 300)
    expect(onSelectStretch).toHaveBeenLastCalledWith({ startMile: 10, endMile: 30 })
  })

  it('offers to plan a measured stretch, and not the route it came from', async () => {
    const onPlanStretch = vi.fn()
    const { rerender } = render(
      <ElevationChart profile={rampProfile()} onPlanStretch={onPlanStretch} />,
    )
    dragStretch(200, 700)

    await userEvent.click(screen.getByRole('button', { name: 'Plan this stretch' }))
    expect(onPlanStretch).toHaveBeenCalledTimes(1)

    rerender(
      <ElevationChart
        profile={rampProfile()}
        selection={{ startMile: 20, endMile: 70 }}
        southbound={false}
        selectionFromPlan
        onPlanStretch={onPlanStretch}
      />,
    )
    expect(
      screen.queryByRole('button', { name: 'Plan this stretch' }),
    ).not.toBeInTheDocument()
  })

  it("prices the stretch at the hiker's own pace, and says what it moved from", () => {
    // 50 mi at 2.5 mph is 1,200 min; 600 ft of climb at the standard 600 m/h
    // adds 18.3 - ≈20h 20m once rounded to the 5-minute step. The baseline
    // rides beside it, welded on by paceEstimate (#886): an adjusted time
    // must never render without saying what it was adjusted from.
    const { rerender } = render(
      <ElevationChart
        profile={rampProfile()}
        selection={{ startMile: 20, endMile: 70 }}
        southbound={false}
        pace={{ flatPaceMph: 2.5, ascentMetersPerHour: 600 }}
      />,
    )

    expect(screen.getByText('≈20h 20m walking')).toBeInTheDocument()
    expect(screen.getByText('was ≈16h 25m · 1.2× standard')).toBeInTheDocument()

    // At the standard pace the line vanishes rather than reading "1.0×" - a
    // caveat on every line reads exactly like a caveat on none.
    rerender(
      <ElevationChart
        profile={rampProfile()}
        selection={{ startMile: 20, endMile: 70 }}
        southbound={false}
      />,
    )
    expect(screen.getByText('≈16h 25m walking')).toBeInTheDocument()
    expect(screen.queryByText(/standard/)).not.toBeInTheDocument()
  })

  it('reports zoom acts so the screen can move the map with the chart', async () => {
    const onZoomDomain = vi.fn()
    render(
      <ElevationChart
        profile={rampProfile()}
        selection={{ startMile: 20, endMile: 70 }}
        southbound={false}
        onZoomDomain={onZoomDomain}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Zoom to stretch' }))
    // The same padded window the chart itself zooms to - 20-70 plus 8% of
    // the span each side - so the map's frame and the profile's agree.
    expect(onZoomDomain).toHaveBeenLastCalledWith({ startMile: 16, endMile: 74 })

    await userEvent.click(screen.getByRole('button', { name: 'Whole trail' }))
    expect(onZoomDomain).toHaveBeenLastCalledWith(null)
  })
})
