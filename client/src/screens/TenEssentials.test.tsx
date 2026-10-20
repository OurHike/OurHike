// The Ten Essentials page (#1689): the banner is the only disclosure before
// a tap leaves for REI, so what it says is held here in both builds.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { TenEssentials } from './TenEssentials'
import type { EssentialId } from '../lib/tenEssentials'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const none: ReadonlySet<EssentialId> = new Set()

describe('the Ten Essentials page', () => {
  it('lists ten checkboxes, each with a Shop … at REI link that opens outside the app', () => {
    render(
      <TenEssentials room="sections" packed={none} onChange={vi.fn()} onBack={vi.fn()} />,
    )

    expect(screen.getAllByRole('checkbox')).toHaveLength(10)
    const links = screen.getAllByRole('link', { name: /^Shop .+ at REI$/ })
    expect(links).toHaveLength(10)
    for (const link of links) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noreferrer')
      expect(link.getAttribute('href')).toMatch(/^https:\/\/www\.rei\.com\/[cs]\//)
    }
  })

  it('claims no commission while the build ships no affiliate code', () => {
    render(
      <TenEssentials room="sections" packed={none} onChange={vi.fn()} onBack={vi.fn()} />,
    )

    const banner = screen.getByRole('note')
    expect(banner).toHaveTextContent('Links on this page go to REI.')
    expect(banner).not.toHaveTextContent(/commission/i)
  })

  it('says OurHike earns a commission, and sends links through the template, once there is a code', () => {
    render(
      <TenEssentials
        room="sections"
        packed={none}
        onChange={vi.fn()}
        onBack={vi.fn()}
        affiliateTemplate="https://track.example/click?url={url}"
      />,
    )

    expect(screen.getByRole('note')).toHaveTextContent(
      /OurHike earns a commission.*nothing is tracked until you tap one/,
    )
    expect(screen.getByRole('link', { name: 'Shop headlamps at REI' })).toHaveAttribute(
      'href',
      'https://track.example/click?url=https%3A%2F%2Fwww.rei.com%2Fc%2Fheadlamps',
    )
  })

  it('ticks an essential by its name, and hands the new set up', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <TenEssentials
        room="day"
        packed={new Set<EssentialId>(['navigation'])}
        onChange={onChange}
        onBack={vi.fn()}
      />,
    )

    expect(screen.getByRole('checkbox', { name: /Navigation/ })).toBeChecked()
    await user.click(screen.getByText('Headlamp'))
    expect([...onChange.mock.calls[0][0]].sort()).toEqual(['headlamp', 'navigation'])
  })

  it('offers "Clear all ticks" only when something is ticked, and it clears every tick', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { rerender } = render(
      <TenEssentials room="day" packed={none} onChange={onChange} onBack={vi.fn()} />,
    )
    expect(
      screen.queryByRole('button', { name: 'Clear all ticks' }),
    ).not.toBeInTheDocument()

    rerender(
      <TenEssentials
        room="day"
        packed={new Set<EssentialId>(['fire', 'water'])}
        onChange={onChange}
        onBack={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Clear all ticks' }))
    expect(onChange.mock.calls[0][0].size).toBe(0)
  })

  it('goes back to Plan from the crumb', async () => {
    const user = userEvent.setup()
    const onBack = vi.fn()
    render(
      <TenEssentials room="sections" packed={none} onChange={vi.fn()} onBack={onBack} />,
    )

    await user.click(screen.getByRole('button', { name: /Plan/ }))
    expect(onBack).toHaveBeenCalledOnce()
  })
})
