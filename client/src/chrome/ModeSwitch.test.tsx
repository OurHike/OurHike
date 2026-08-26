import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ModeSwitch } from './ModeSwitch'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ModeSwitch', () => {
  it('renders all three segments, always - the product decision, pinned', () => {
    // Volunteer left the tab bar on the promise that the word is on screen
    // every day (chrome/tabs.ts). A build where this control collapses to a
    // dropdown or hides the unselected two has broken that deal.
    render(<ModeSwitch mode="day" onChange={vi.fn()} />)

    expect(screen.getAllByRole('radio').map((r) => r.textContent)).toEqual([
      'Day hike',
      'Thru-hike',
      'Volunteer',
    ])
  })

  it('marks exactly the current mode as checked', () => {
    render(<ModeSwitch mode="thru" onChange={vi.fn()} />)

    expect(screen.getByRole('radio', { name: 'Thru-hike' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    expect(screen.getAllByRole('radio', { checked: true })).toHaveLength(1)
  })

  it('reports which mode was chosen', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<ModeSwitch mode="day" onChange={onChange} />)

    await user.click(screen.getByRole('radio', { name: 'Volunteer' }))

    expect(onChange).toHaveBeenCalledWith('volunteer')
  })

  it('announces what the group is choosing', () => {
    render(<ModeSwitch mode="day" onChange={vi.fn()} />)

    expect(screen.getByRole('radiogroup', { name: "Today I'm" })).toBeInTheDocument()
  })
})
