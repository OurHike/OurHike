import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StepRail } from './StepRail'

afterEach(cleanup)

describe('StepRail', () => {
  it('names the three stops, the first by the kind of hike the mode answered', () => {
    render(<StepRail step={1} kind="Day hike" />)

    const items = screen.getAllByRole('listitem').map((item) => item.textContent)
    expect(items[0]).toContain('Day hike')
    expect(items[1]).toContain('Route')
    expect(items[2]).toContain('Details')
  })

  it('marks the current step, and ticks the ones behind it', () => {
    render(<StepRail step={2} kind="Long hike" />)

    const [hike, route, details] = screen.getAllByRole('listitem')
    expect(route).toHaveAttribute('aria-current', 'step')
    expect(hike).toHaveClass('step-rail__step--done')
    expect(hike.textContent).toContain('✓')
    expect(details).not.toHaveAttribute('aria-current')
    expect(details.textContent).toContain('3')
  })

  it('lets a hiker go back to a finished step, and forward to one already reached', async () => {
    const onStep = vi.fn()
    const user = userEvent.setup()
    render(<StepRail step={2} kind="Day hike" reached={3} onStep={onStep} />)

    await user.click(screen.getByRole('button', { name: 'Step 1, Day hike' }))
    await user.click(screen.getByRole('button', { name: 'Step 3, Details' }))

    expect(onStep.mock.calls).toEqual([[1], [3]])
  })

  it('offers no door to a step nobody has reached, and none to the step you are on', () => {
    render(<StepRail step={2} kind="Day hike" onStep={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Step 1, Day hike' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Step 2, Route' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Step 3, Details' })).toBeNull()
  })

  it('reads only when nothing is wired to it', () => {
    render(<StepRail step={3} kind="Day hike" />)

    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.getByRole('navigation', { name: 'Planning steps' })).toBeInTheDocument()
  })
})
