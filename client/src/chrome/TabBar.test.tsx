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

  // The bar is also the sidebar on a desktop, and the mark sits at the foot of
  // it - the bottom-left corner of the page. Whether it is VISIBLE is a CSS
  // contract, asserted in test/desktopLayout.test.ts; what is asserted here is
  // that the bar carries it at all, and carries it without disturbing the tabs.
  it('carries the OurHike mark for the foot of the sidebar', () => {
    const { container } = render(<TabBar {...PROPS} />)

    expect(container.querySelector('.tab-bar__brand')).not.toBeNull()
  })

  it('carries both pieces of the mark, leaving the layout to pick', () => {
    // Both are always in the markup; which one is drawn is a CSS question, and
    // is asserted in test/desktopLayout.test.ts. The sidebar shows icon over
    // wordmark; a phone shows the icon alone beside its three tabs, because the
    // icon on its own still says whose app this is and type there would come
    // straight out of a thumb target's width.
    const { container } = render(<TabBar {...PROPS} />)

    expect(container.querySelector('.tab-bar__brand-icon')).not.toBeNull()
    expect(container.querySelector('.tab-bar__brand')).toHaveTextContent('OurHike')
  })

  it('keeps the mark out of the tablist, so it is not read as a fourth tab', () => {
    // `role="tablist"` is required to own tabs and nothing else. With the mark
    // inside it, a screen reader announces the brand as one more member of a
    // set of three - which is why the tabs have their own box.
    render(<TabBar {...PROPS} />)

    expect(screen.getByRole('tablist').querySelector('.tab-bar__brand')).toBeNull()
    expect(screen.getAllByRole('tab')).toHaveLength(TABS.length)
  })
})
