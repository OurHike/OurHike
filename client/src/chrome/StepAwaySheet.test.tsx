// Stepping away from a long hike (#1317).
//
// The load-bearing tests are the last two: every door names its consequence,
// and the one destructive door is behind a confirm that says the sections
// survive - because a hiker cannot see that from the outside.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { StepAwaySheet } from './StepAwaySheet'

const PROPS = {
  hikeName: 'Springer → Katahdin',
  status: 'walking' as const,
  confirmingForget: false,
  onZero: vi.fn(),
  onTownNight: vi.fn(),
  onPause: vi.fn(),
  onTurnAround: vi.fn(),
  onFinish: vi.fn(),
  onForget: vi.fn(),
  onCancelForget: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('stepping away', () => {
  it('offers every way off, each named by what it does', () => {
    // Verbs alone - "Zero", "Pause", "Finish" - would make the destructive
    // door look like the reversible ones.
    render(<StepAwaySheet {...PROPS} />)

    expect(
      screen.getByText(/The day stays; the ones after it shift by one/),
    ).toBeInTheDocument()
    expect(screen.getByText(/Resupply logged at the stop/)).toBeInTheDocument()
    expect(screen.getByText(/Keeps the mile you stopped at/)).toBeInTheDocument()
    expect(screen.getByText(/The miles already walked stay walked/)).toBeInTheDocument()
    expect(
      screen.getByText(/Closes the hike and keeps every section in it/),
    ).toBeInTheDocument()
  })

  it('does not offer to pause a hike that is already paused', () => {
    render(<StepAwaySheet {...PROPS} status="paused" />)
    expect(screen.queryByText(/Keeps the mile you stopped at/)).not.toBeInTheDocument()
  })

  it('arms the forget rather than doing it, and never behind a swipe', async () => {
    const user = userEvent.setup()
    const onForget = vi.fn()
    render(<StepAwaySheet {...PROPS} onForget={onForget} />)

    // The first press is the shell's to interpret as arming - this sheet
    // reports the tap, and the shell decides. What matters here is that the
    // control is a BUTTON: a swipe would put the most alarming-sounding
    // action behind the gesture most easily performed by accident.
    const door = screen.getByRole('button', { name: /Forget this hike/ })
    await user.click(door)
    expect(onForget).toHaveBeenCalled()
  })

  it('says the sections survive, in the confirm as well as on the door', async () => {
    const user = userEvent.setup()
    const onForget = vi.fn()
    const onCancelForget = vi.fn()
    render(
      <StepAwaySheet
        {...PROPS}
        confirmingForget
        onForget={onForget}
        onCancelForget={onCancelForget}
      />,
    )

    expect(
      screen.getByText(/Every section stays in Plan, with its days/),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Keep it' }))
    expect(onCancelForget).toHaveBeenCalled()
    expect(onForget).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Forget it' }))
    expect(onForget).toHaveBeenCalled()
  })

  it('prints no percentage, nothing behind and nothing on track', () => {
    const { container } = render(<StepAwaySheet {...PROPS} />)
    expect(container.textContent).not.toMatch(/%|behind|ahead of|on track|streak/i)
  })
})
