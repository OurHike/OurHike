import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Tabs } from './Tabs'

// The strip the download window and first run both choose a background sheet
// with (#298). What is asserted here is the part a stylesheet cannot carry:
// only the chosen panel exists, the keyboard can reach every tab, and the
// panel is tied to the tab that named it.

const TABS = [
  { id: 'hiking-sheet', label: 'Hiking sheet' },
  { id: 'usgs-sheet', label: 'USGS sheet' },
  { id: 'later-sheet', label: 'Something later' },
]

function renderTabs(activeId = 'hiking-sheet', onSelect = vi.fn()) {
  render(
    <Tabs
      label="Background maps"
      tabs={TABS}
      activeId={activeId}
      onSelect={onSelect}
      idPrefix="test"
    >
      <p>{`Panel for ${activeId}`}</p>
    </Tabs>,
  )
  return onSelect
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Tabs', () => {
  it('names the whole strip, so a screen reader says what is being chosen', () => {
    renderTabs()

    expect(screen.getByRole('tablist', { name: 'Background maps' })).toBeInTheDocument()
  })

  it('marks exactly one tab selected', () => {
    renderTabs('usgs-sheet')

    expect(screen.getByRole('tab', { selected: true })).toHaveTextContent('USGS sheet')
    expect(screen.getAllByRole('tab', { selected: false })).toHaveLength(2)
  })

  it('renders only the chosen panel, rather than hiding the others with CSS', () => {
    // Hidden panels leave their radios, buttons and progress bars in the tab
    // order and in the accessibility tree - including a `role="status"`
    // warning about a download nobody is looking at.
    renderTabs('usgs-sheet')

    expect(screen.getByText('Panel for usgs-sheet')).toBeInTheDocument()
    expect(screen.queryByText('Panel for hiking-sheet')).toBe(null)
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1)
  })

  it('ties the panel to the tab that names it', () => {
    renderTabs('usgs-sheet')
    const tab = screen.getByRole('tab', { name: 'USGS sheet' })

    expect(screen.getByRole('tabpanel')).toHaveAttribute(
      'aria-labelledby',
      tab.getAttribute('id'),
    )
    expect(tab).toHaveAttribute('aria-controls', screen.getByRole('tabpanel').id)
  })

  it('reports the tab that was tapped', async () => {
    const user = userEvent.setup()
    const onSelect = renderTabs()

    await user.click(screen.getByRole('tab', { name: 'USGS sheet' }))

    expect(onSelect).toHaveBeenCalledWith('usgs-sheet')
  })

  it('keeps one tab in the page’s tab order and the rest on the arrows', () => {
    // A roving tabstop: tabbing through three sheets to reach the download
    // button behind them is what this pattern exists to avoid.
    renderTabs('usgs-sheet')

    expect(screen.getByRole('tab', { name: 'USGS sheet' })).toHaveAttribute(
      'tabindex',
      '0',
    )
    expect(screen.getByRole('tab', { name: 'Hiking sheet' })).toHaveAttribute(
      'tabindex',
      '-1',
    )
  })

  it('moves between tabs with the arrow keys', async () => {
    const user = userEvent.setup()
    const onSelect = renderTabs()

    screen.getByRole('tab', { name: 'Hiking sheet' }).focus()
    await user.keyboard('{ArrowRight}')

    expect(onSelect).toHaveBeenCalledWith('usgs-sheet')
  })

  it('wraps around rather than dead-ending at the edges', async () => {
    const user = userEvent.setup()
    const onSelect = renderTabs()

    screen.getByRole('tab', { name: 'Hiking sheet' }).focus()
    await user.keyboard('{ArrowLeft}')

    expect(onSelect).toHaveBeenCalledWith('later-sheet')
  })

  it('jumps to the ends with Home and End', async () => {
    const user = userEvent.setup()
    const onSelect = renderTabs('usgs-sheet')

    screen.getByRole('tab', { name: 'USGS sheet' }).focus()
    await user.keyboard('{End}')
    expect(onSelect).toHaveBeenCalledWith('later-sheet')

    await user.keyboard('{Home}')
    expect(onSelect).toHaveBeenCalledWith('hiking-sheet')
  })

  it('leaves other keys to the page', async () => {
    const user = userEvent.setup()
    const onSelect = renderTabs()

    screen.getByRole('tab', { name: 'Hiking sheet' }).focus()
    await user.keyboard('{ArrowDown}')

    expect(onSelect).not.toHaveBeenCalled()
  })
})
