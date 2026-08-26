import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TabBar } from './TabBar'
import { TABS } from './tabs'

// Today / Map / Plan / More (#1054). Today is the redesign's home; Downloads
// went on 2026-08-05 (a window now, not a place) and Volunteer went with
// #1054 - not demoted, re-homed: the mode switch and the Today column say the
// word daily, which is the outcome VOLUNTEERING.md's argument wanted.
// chrome/tabs.ts carries the standard a tab has to meet and both departures.

const PROPS = { active: 'today' as const, onSelect: vi.fn() }

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('TabBar', () => {
  it('has exactly the four tabs, in order', () => {
    render(<TabBar {...PROPS} />)

    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'Today',
      'Map',
      'Plan',
      'More',
    ])
  })

  it('no longer offers Volunteer, whose word now lives on the Today screen', () => {
    // An absence test like the Downloads one below, and for the same reason:
    // the tab was argued IN once (VOLUNTEERING.md), so nothing stops a later
    // change arguing it back by accident. chrome/tabs.ts records why it left
    // and who approved it (#1054).
    render(<TabBar {...PROPS} />)

    expect(screen.queryByRole('tab', { name: /volunteer/i })).toBeNull()
  })

  it('no longer offers Downloads, which is a window now rather than a place', () => {
    // An absence test, because the tab is coming back in v2 (chrome/tabs.ts)
    // and "it was easy to re-add" is exactly how it gets re-added by accident.
    render(<TabBar {...PROPS} />)

    expect(screen.queryByRole('tab', { name: /download/i })).toBeNull()
  })

  it('derives its tabs from the shared list rather than hardcoding them in markup', () => {
    render(<TabBar {...PROPS} />)

    expect(screen.getAllByRole('tab')).toHaveLength(TABS.length)
  })

  it('marks the active tab as selected, and only that one', () => {
    render(<TabBar {...PROPS} active="more" />)
    const selected = screen.getAllByRole('tab', { selected: true })

    expect(selected).toHaveLength(1)
    expect(selected[0]).toHaveTextContent('More')
  })

  it('reports which tab was chosen', async () => {
    const user = userEvent.setup()
    render(<TabBar {...PROPS} />)

    await user.click(screen.getByRole('tab', { name: 'More' }))

    expect(PROPS.onSelect).toHaveBeenCalledWith('more')
  })

  it('still reports a tap on the tab that is already active, so it can scroll-to-top', async () => {
    const user = userEvent.setup()
    render(<TabBar {...PROPS} active="today" />)

    await user.click(screen.getByRole('tab', { name: 'Today' }))

    expect(PROPS.onSelect).toHaveBeenCalledWith('today')
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
    // wordmark; a phone shows the icon alone beside the tabs, because the icon
    // on its own still says whose app this is and type there would come
    // straight out of a thumb target's width.
    const { container } = render(<TabBar {...PROPS} />)

    expect(container.querySelector('.tab-bar__brand-icon')).not.toBeNull()
    expect(container.querySelector('.tab-bar__brand')).toHaveTextContent('OurHike')
  })

  it('keeps the mark out of the tablist, so it is not read as one more tab', () => {
    // `role="tablist"` is required to own tabs and nothing else. With the mark
    // inside it, a screen reader announces the brand as one more member of the
    // set - which is why the tabs have their own box.
    render(<TabBar {...PROPS} />)

    expect(screen.getByRole('tablist').querySelector('.tab-bar__brand')).toBeNull()
    expect(screen.getAllByRole('tab')).toHaveLength(TABS.length)
  })
})

// The sidebar's mode block (#1054). A slot, so the bar stays ignorant of
// hiker modes - what is asserted here is that the slot renders where it is
// given and costs the phone nothing when it is not.
describe('the mode slot', () => {
  it('renders nothing extra when no switch is handed over, which is the phone', () => {
    const { container } = render(<TabBar {...PROPS} />)

    expect(container.querySelector('.tab-bar__mode')).toBeNull()
  })

  it('carries the switch it is handed, outside the tablist', () => {
    render(<TabBar {...PROPS} modeSwitch={<div data-testid="mode-switch" />} />)

    expect(screen.getByTestId('mode-switch')).toBeInTheDocument()
    // Not inside the tablist: role="tablist" may own tabs and nothing else.
    expect(
      screen.getByRole('tablist').querySelector('[data-testid="mode-switch"]'),
    ).toBeNull()
  })
})
