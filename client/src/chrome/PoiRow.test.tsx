import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PoiRow } from './PoiRow'
import { POI_COLORS } from '../map/poiIcons'
import { WARNING_PIN } from '../lib/seriousWarnings'

afterEach(cleanup)

describe('PoiRow', () => {
  it('draws the map’s own pin for a waypoint type, in its own colour', () => {
    const { container } = render(
      <PoiRow kind="water" title="Stony Brook crossing" meta="0.8 mi · water" />,
    )

    const disc = container.querySelector('.map-icon__disc')
    expect(disc).not.toBeNull()
    expect(disc?.getAttribute('fill')).toBe(POI_COLORS.water)
    expect(screen.getByText('Stony Brook crossing')).toBeInTheDocument()
    expect(screen.getByText('0.8 mi · water')).toBeInTheDocument()
  })

  it('draws a serious warning as the warning pin, never as a waypoint', () => {
    const { container } = render(<PoiRow kind="warning" title="Blowdown reported" />)

    expect(container.querySelector('.map-icon__disc')?.getAttribute('fill')).toBe(
      WARNING_PIN.color,
    )
  })

  it('keeps a broken rim on an unverified place', () => {
    const { container } = render(<PoiRow kind="water" title="Spring" confidence="low" />)

    expect(container.querySelector('.map-icon__edge')).toHaveAttribute('stroke-dasharray')
  })

  it('is a button only when it opens something', async () => {
    const onOpen = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(<PoiRow kind="shelter" title="High Point Shelter" />)

    expect(screen.queryByRole('button')).toBeNull()

    rerender(<PoiRow kind="shelter" title="High Point Shelter" onOpen={onOpen} />)
    await user.click(screen.getByRole('button', { name: /High Point Shelter/ }))
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it('prints a trailing figure for lists ordered by it', () => {
    render(<PoiRow kind="finish" title="Tuxedo station · finish" trailing="4.2 mi" />)

    expect(screen.getByText('4.2 mi')).toHaveClass('poi-row__trailing')
  })
})
