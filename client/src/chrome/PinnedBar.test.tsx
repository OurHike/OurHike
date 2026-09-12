import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PinnedBar } from './PinnedBar'

afterEach(cleanup)

describe('PinnedBar', () => {
  it('always carries both doors', async () => {
    const onFind = vi.fn()
    const onPlan = vi.fn()
    const user = userEvent.setup()
    render(<PinnedBar onFind={onFind} onPlan={onPlan} />)

    await user.click(screen.getByRole('button', { name: 'Find a hike' }))
    await user.click(screen.getByRole('button', { name: 'Plan a hike' }))

    expect(onFind).toHaveBeenCalledTimes(1)
    expect(onPlan).toHaveBeenCalledTimes(1)
  })

  it('raises the one that is the next step on this state, and neither by default', () => {
    const { rerender } = render(
      <PinnedBar onFind={vi.fn()} onPlan={vi.fn()} emphasis="plan" />,
    )
    expect(screen.getByRole('button', { name: 'Plan a hike' })).toHaveClass(
      'pinned-bar__button--primary',
    )
    expect(screen.getByRole('button', { name: 'Find a hike' })).not.toHaveClass(
      'pinned-bar__button--primary',
    )

    rerender(<PinnedBar onFind={vi.fn()} onPlan={vi.fn()} />)
    expect(document.querySelector('.pinned-bar__button--primary')).toBeNull()
  })
})
