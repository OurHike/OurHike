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

describe('the bail sheet with nothing to keep (#1378)', () => {
  // The sweep. `App.tsx`'s `sweepForBuilder` opens the OTHER kind of plan,
  // and only one route can be live (#997) - so the sweep IS the discard, and
  // a "Keep it for later" button would be the sheet lying about what it does.
  it('asks a narrower question and says why keeping is absent', () => {
    render(
      <BailSheet figures="2 legs · 4.1 mi so far" onDiscard={vi.fn()} onStay={vi.fn()} />,
    )

    const sheet = screen.getByRole('dialog', { name: 'Drop this half-built route?' })
    expect(sheet).toHaveTextContent('2 legs · 4.1 mi so far')
    expect(sheet).toHaveTextContent(
      'Starting the other kind of plan needs this one out of the way, so keeping it is not on offer here.',
    )
    expect(screen.queryByRole('button', { name: 'Keep it for later' })).toBeNull()
  })

  it('puts the focus on the answer that costs nothing', () => {
    // With no "Keep it for later" the primary slot is empty, and the
    // destructive answer must not inherit it.
    render(<BailSheet figures={null} onDiscard={vi.fn()} onStay={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Stay here' })).toHaveFocus()
  })

  it('still offers both answers it can honour', async () => {
    const user = userEvent.setup()
    const onDiscard = vi.fn()
    const onStay = vi.fn()
    render(<BailSheet figures={null} onDiscard={onDiscard} onStay={onStay} />)

    await user.click(screen.getByRole('button', { name: 'Discard it' }))
    expect(onDiscard).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: 'Stay here' }))
    expect(onStay).toHaveBeenCalledTimes(1)
  })

  it('takes Escape as staying, the same as the three-answer shape', () => {
    const onStay = vi.fn()
    render(<BailSheet figures={null} onDiscard={vi.fn()} onStay={onStay} />)

    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(onStay).toHaveBeenCalledTimes(1)
  })
})
