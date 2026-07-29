import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WrongWayCue } from './WrongWayCue'

// WIREFRAMES.md §9, beat 1: the in-app cue. "You may be off the trail — about
// 90 ft from the white blazes for the last 12 minutes," with Show me the way
// back / I'm fine.
//
// The wording is hedged on purpose. GPS under tree canopy is unreliable
// enough that certainty would be dishonest, and "You ARE off the trail" to
// someone standing on it is exactly the false positive that spends this
// feature's whole trust budget. "May be" is the claim the data supports.

const PROPS = {
  open: true,
  distanceFt: 90,
  minutes: 12,
  onShowWayBack: vi.fn(),
  onDismiss: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('WrongWayCue', () => {
  it('stays out of the way when there is nothing to say', () => {
    render(<WrongWayCue {...PROPS} open={false} />)

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('hedges rather than asserting - GPS under canopy does not support certainty', () => {
    render(<WrongWayCue {...PROPS} />)

    expect(screen.getByRole('alert')).toHaveTextContent(/may be/i)
  })

  it('gives the distance and the duration behind the claim', () => {
    render(<WrongWayCue {...PROPS} />)
    const cue = screen.getByRole('alert')

    expect(cue).toHaveTextContent(/90 ft/)
    expect(cue).toHaveTextContent(/12 minutes/)
  })

  it('offers to show the way back', async () => {
    const user = userEvent.setup()
    render(<WrongWayCue {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /way back/i }))

    expect(PROPS.onShowWayBack).toHaveBeenCalled()
  })

  it('lets the hiker say they are fine, and believes them', async () => {
    const user = userEvent.setup()
    render(<WrongWayCue {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /fine/i }))

    expect(PROPS.onDismiss).toHaveBeenCalled()
  })

  it('is announced to assistive tech without waiting to be found', () => {
    render(<WrongWayCue {...PROPS} />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('never promises to navigate anywhere - it points, it does not route', () => {
    // Consistent with the closure sheet's "OurHike does not work out detours".
    render(<WrongWayCue {...PROPS} />)

    expect(screen.queryByText(/directions|navigate|route you/i)).toBe(null)
  })
})
