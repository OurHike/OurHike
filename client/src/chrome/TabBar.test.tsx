import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TabBar } from './TabBar'
import { TABS } from './tabs'

// WIREFRAMES.md, map screen §6: Trail / Downloads / More. Three tabs, no more -
// v1's whole surface fits in them, and the tab bar sits in the thumb zone where
// every extra target costs accuracy mid-walk.

const PROPS = { active: 'trail' as const, onSelect: vi.fn() }

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('TabBar', () => {
  it('has exactly the three MVP tabs, in order', () => {
    render(<TabBar {...PROPS} />)

    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'Trail',
      'Downloads',
      'More',
    ])
  })

  it('derives its tabs from the shared list rather than hardcoding them in markup', () => {
    render(<TabBar {...PROPS} />)

    expect(screen.getAllByRole('tab')).toHaveLength(TABS.length)
  })

  it('marks the active tab as selected, and only that one', () => {
    render(<TabBar {...PROPS} active="downloads" />)
    const selected = screen.getAllByRole('tab', { selected: true })

    expect(selected).toHaveLength(1)
    expect(selected[0]).toHaveTextContent('Downloads')
  })

  it('reports which tab was chosen', async () => {
    const user = userEvent.setup()
    render(<TabBar {...PROPS} />)

    await user.click(screen.getByRole('tab', { name: 'More' }))

    expect(PROPS.onSelect).toHaveBeenCalledWith('more')
  })

  it('still reports a tap on the tab that is already active, so it can scroll-to-top', async () => {
    const user = userEvent.setup()
    render(<TabBar {...PROPS} active="trail" />)

    await user.click(screen.getByRole('tab', { name: 'Trail' }))

    expect(PROPS.onSelect).toHaveBeenCalledWith('trail')
  })

  it('is a tablist, so assistive tech announces position within the set', () => {
    render(<TabBar {...PROPS} />)

    expect(screen.getByRole('tablist')).toBeInTheDocument()
  })
})
