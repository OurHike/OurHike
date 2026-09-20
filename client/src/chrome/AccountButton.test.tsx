import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AccountButton } from './AccountButton'

// The one-tap way in (#1596). What these pin is the half a glyph cannot say:
// which state it is in, and as whom, for somebody who cannot see it.

afterEach(cleanup)

describe('signed out', () => {
  it('is named "Sign in", so the door says what it does rather than what it is', () => {
    render(<AccountButton account={null} onOpen={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('draws the glyph unfilled, which is what tells a sighted hiker the seat is empty', () => {
    render(<AccountButton account={null} onOpen={vi.fn()} />)
    const shapes = screen.getByRole('button').querySelectorAll('svg *')

    expect(Array.from(shapes).map((shape) => shape.getAttribute('fill'))).toEqual([
      'none',
      'none',
    ])
  })

  it('opens the ask when tapped', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<AccountButton account={null} onOpen={onOpen} />)

    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(onOpen).toHaveBeenCalledTimes(1)
  })
})

describe('signed in', () => {
  const account = { email: 'hiker@example.com' }

  it('names the account in the label, since the filled glyph cannot say as whom', () => {
    render(<AccountButton account={account} onOpen={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'Account, signed in as hiker@example.com' }),
    ).toBeInTheDocument()
  })

  it('fills the same glyph rather than swapping in a second one', () => {
    // One shape a hiker learns, in two weights. A different icon per state is
    // two things to learn for one fact.
    render(<AccountButton account={account} onOpen={vi.fn()} />)
    const shapes = screen.getByRole('button').querySelectorAll('svg *')

    expect(Array.from(shapes).map((shape) => shape.getAttribute('fill'))).toEqual([
      'currentColor',
      'currentColor',
    ])
  })

  it('still opens the same window, which is where signing out lives', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<AccountButton account={account} onOpen={onOpen} />)

    await user.click(screen.getByRole('button', { name: /^Account/ }))

    expect(onOpen).toHaveBeenCalledTimes(1)
  })
})

describe('wherever it is mounted', () => {
  it('takes the caller class, so the header copy matches Legend and Search exactly', () => {
    render(
      <AccountButton account={null} onOpen={vi.fn()} className="map-header__button" />,
    )

    expect(screen.getByRole('button')).toHaveClass('map-header__button')
  })

  it('hides the glyph from assistive tech, because the label already carries it', () => {
    render(<AccountButton account={null} onOpen={vi.fn()} />)

    expect(screen.getByRole('button').querySelector('svg')).toHaveAttribute(
      'aria-hidden',
      'true',
    )
  })
})
