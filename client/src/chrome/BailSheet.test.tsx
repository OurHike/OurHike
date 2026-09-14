import { describe, it, expect, vi, afterEach } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BailSheet } from './BailSheet'

afterEach(() => cleanup())

describe('the bail sheet (#1373, D8)', () => {
  it('asks the one question, says what the route has cost, and offers all three answers', async () => {
    const user = userEvent.setup()
    const onKeep = vi.fn()
    const onDiscard = vi.fn()
    const onStay = vi.fn()
    render(
      <BailSheet
        figures="2 legs · 4.1 mi so far"
        onKeep={onKeep}
        onDiscard={onDiscard}
        onStay={onStay}
      />,
    )

    const sheet = screen.getByRole('dialog', { name: 'Keep this half-built route?' })
    expect(sheet).toHaveTextContent('2 legs · 4.1 mi so far')
    expect(sheet).toHaveTextContent(
      'Kept, it waits on Today and on the Plan tab until you finish or delete it.',
    )

    await user.click(screen.getByRole('button', { name: 'Keep it for later' }))
    expect(onKeep).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Discard it' }))
    expect(onDiscard).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button', { name: 'Stay here' }))
    expect(onStay).toHaveBeenCalledTimes(1)
  })

  it('prices nothing when nothing has been routed, and Escape stays', () => {
    const onStay = vi.fn()
    render(
      <BailSheet figures={null} onKeep={vi.fn()} onDiscard={vi.fn()} onStay={onStay} />,
    )

    expect(screen.queryByText(/so far/)).toBeNull()
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(onStay).toHaveBeenCalledTimes(1)
  })
})
