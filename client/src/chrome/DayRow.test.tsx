import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DayRow } from './DayRow'
import { MIN_ROW_PX, dayRowHeight } from '../lib/planDisplay'
import { priceLeg, type LegFigures } from '../lib/route'
import { STANDARD_PACE, type PaceProfile } from '../lib/pace'

afterEach(cleanup)

const MEASURED: LegFigures = {
  distanceMi: 15.8,
  ascentFt: 2100,
  descentFt: 1800,
  minutes: 470,
  unmeasuredMi: 0,
}

const QUICKER: PaceProfile = {
  ...STANDARD_PACE,
  flatPaceMph: STANDARD_PACE.flatPaceMph * 1.2,
}

describe('DayRow', () => {
  it('carries distance, time at the hiker’s pace and gain - never distance alone', () => {
    render(
      <DayRow
        label="D1"
        title="→ Mohican Outdoor Center"
        distanceMi={15.8}
        figures={priceLeg(MEASURED, STANDARD_PACE)}
        units="imperial"
      />,
    )

    const figures = screen.getByText(/15\.8 mi/)
    expect(figures.textContent).toMatch(/≈\d+h/)
    expect(figures.textContent).toContain('2,100 ft up')
  })

  it('prints the baseline beside a pace-adjusted time, and nothing at the standard pace', () => {
    const { rerender } = render(
      <DayRow
        label="D1"
        title="x"
        distanceMi={15.8}
        figures={priceLeg(MEASURED, QUICKER)}
        units="imperial"
      />,
    )
    expect(document.querySelector('.day-row__figures--baseline')?.textContent).toMatch(
      /× standard/,
    )

    rerender(
      <DayRow
        label="D1"
        title="x"
        distanceMi={15.8}
        figures={priceLeg(MEASURED, STANDARD_PACE)}
        units="imperial"
      />,
    )
    expect(document.querySelector('.day-row__figures--baseline')).toBeNull()
  })

  it('withholds the climb and the time over a hole in the DEM, and says so', () => {
    render(
      <DayRow
        label="D2"
        title="x"
        distanceMi={17.1}
        figures={priceLeg(
          { ...MEASURED, distanceMi: 17.1, unmeasuredMi: 1.4 },
          STANDARD_PACE,
        )}
        units="imperial"
      />,
    )

    expect(screen.getByText('17.1 mi')).toBeInTheDocument()
    expect(screen.queryByText(/≈/)).toBeNull()
    expect(
      screen.getByText(/no climb measured for 1\.4 mi of this day/),
    ).toBeInTheDocument()
  })

  it('says when there is no profile at all rather than printing the distance as if complete', () => {
    render(<DayRow label="D3" title="x" distanceMi={12} units="imperial" />)

    expect(screen.getByText('12.0 mi')).toBeInTheDocument()
    expect(screen.getByText('no profile for this day')).toBeInTheDocument()
  })

  it('is as tall as its walking hours, floored at the touch target', () => {
    const { container, rerender } = render(
      <DayRow
        label="D1"
        title="x"
        distanceMi={15.8}
        figures={priceLeg(MEASURED, STANDARD_PACE)}
        units="imperial"
      />,
    )
    const priced = priceLeg(MEASURED, STANDARD_PACE)
    expect((container.firstElementChild as HTMLElement).style.minHeight).toBe(
      `${dayRowHeight(priced.minutes)}px`,
    )

    rerender(<DayRow label="D1" title="x" distanceMi={1} units="imperial" />)
    expect((container.firstElementChild as HTMLElement).style.minHeight).toBe(
      `${MIN_ROW_PX}px`,
    )
  })

  it('reads a zero as no walking, and the states as words on the foot', () => {
    const { rerender } = render(
      <DayRow
        label="D3"
        title="Zero in Unionville"
        distanceMi={0}
        units="imperial"
        state="zero"
        resupply
      />,
    )
    expect(screen.getByText('no walking')).toBeInTheDocument()
    expect(screen.getByText('zero')).toHaveClass('day-row__state')
    expect(screen.getByRole('img', { name: 'resupply' })).toBeInTheDocument()

    rerender(
      <DayRow
        label="D4"
        title="→ Rutherford Shelter"
        distanceMi={16.4}
        units="imperial"
        state="moved"
        note="was Wed · now Thu"
      />,
    )
    expect(screen.getByText('moved')).toHaveClass('day-row__state')
    expect(screen.getByText('was Wed · now Thu')).toHaveClass('day-row__note')
  })

  it('carries its own Edit only when one is wired, and opens only when one is', async () => {
    const onEdit = vi.fn()
    const onOpen = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <DayRow label="D1" title="→ Somewhere" distanceMi={3} units="imperial" />,
    )
    expect(screen.queryByRole('button')).toBeNull()

    rerender(
      <DayRow
        label="D1"
        title="→ Somewhere"
        distanceMi={3}
        units="imperial"
        onEdit={onEdit}
        onOpen={onOpen}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Edit this day ›' }))
    await user.click(screen.getByRole('button', { name: /→ Somewhere/ }))
    expect(onEdit).toHaveBeenCalledTimes(1)
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it('draws the terrain and the high point where the caller supplies them', () => {
    render(
      <DayRow
        label="D1"
        title="x"
        distanceMi={3}
        units="imperial"
        terrain={<svg data-testid="terrain" />}
        high="1,480 ft"
      />,
    )

    expect(screen.getByTestId('terrain')).toBeInTheDocument()
    expect(screen.getByText('1,480 ft')).toHaveClass('day-row__high')
  })

  it('prints in the hiker’s units', () => {
    render(
      <DayRow
        label="D1"
        title="x"
        distanceMi={15.8}
        figures={priceLeg(MEASURED, STANDARD_PACE)}
        units="metric"
      />,
    )

    expect(screen.getByText(/km/).textContent).toContain('m up')
  })
})
