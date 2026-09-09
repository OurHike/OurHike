// A finished hike as it lives in Plan afterwards (#1317).

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { FinishedHike } from './FinishedHike'

const PROPS = {
  hikeName: 'Springer → Katahdin',
  header: '14 Mar 2024 – 12 Aug 2026 · 2,198.4 mi · 0.0 mi to go',
  photo: null,
  sections: [
    {
      id: 't1',
      name: 'Damascus → Pearisburg',
      figures: '156.2 mi',
      provenance: 'walked · 2024 · northbound',
    },
  ],
  totalSections: 9,
  someUnpriced: false,
  units: 'imperial' as const,
  onOpenSection: vi.fn(),
  onAllSections: vi.fn(),
  onShare: vi.fn(),
  onExport: vi.fn(),
  onStartAnother: vi.fn(),
  onBack: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the record afterwards', () => {
  it('says the hike is finished, with its dates and its two figures', () => {
    render(<FinishedHike {...PROPS} />)

    expect(screen.getByText('finished hike')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Springer → Katahdin' }),
    ).toBeInTheDocument()
    // Zero rather than "unknown": a finished hike has nothing left.
    expect(screen.getByText(/0\.0 mi to go/)).toBeInTheDocument()
  })

  it('lists its sections with their own figures and provenance', async () => {
    const user = userEvent.setup()
    const onOpenSection = vi.fn()
    render(<FinishedHike {...PROPS} onOpenSection={onOpenSection} />)

    const row = screen.getByRole('button', { name: /Damascus → Pearisburg/ })
    expect(row).toHaveTextContent('156.2 mi')
    expect(row).toHaveTextContent('walked · 2024 · northbound')
    await user.click(row)
    expect(onOpenSection).toHaveBeenCalledWith('t1')
  })

  it('offers the way to the rest when it is showing fewer than there are', async () => {
    const user = userEvent.setup()
    const onAllSections = vi.fn()
    render(<FinishedHike {...PROPS} onAllSections={onAllSections} />)

    await user.click(screen.getByRole('button', { name: 'All 9 ›' }))
    expect(onAllSections).toHaveBeenCalled()
  })

  it('says why some sections show distance alone, once rather than per row', () => {
    // Repeating it per section would make a download's limitation look like
    // a property of each walk.
    render(<FinishedHike {...PROPS} someUnpriced />)

    expect(screen.getAllByText(/this download has no elevation profile/)).toHaveLength(1)
  })

  it('commits to export, in the words FEATURES.md already used', () => {
    render(<FinishedHike {...PROPS} />)
    expect(
      screen.getByText(/the trail belongs to the trails, not to this app/),
    ).toBeInTheDocument()
  })

  it('promises the hike stays exactly as it is when another one starts', async () => {
    const user = userEvent.setup()
    const onStartAnother = vi.fn()
    render(<FinishedHike {...PROPS} onStartAnother={onStartAnother} />)

    await user.click(screen.getByRole('button', { name: /Start another long hike/ }))
    expect(onStartAnother).toHaveBeenCalled()
    expect(screen.getByText('This one stays exactly as it is.')).toBeInTheDocument()
  })

  it('says a finished hike is still a hike', () => {
    // "Finished" in most apps means archived, greyed, or gone from where it
    // used to be. Here it means the walking is done and the record is not.
    render(<FinishedHike {...PROPS} />)
    expect(
      screen.getByText(/it never leaves the list unless you forget it/),
    ).toBeInTheDocument()
  })

  it('prints no percentage, nothing behind and nothing on track', () => {
    const { container } = render(<FinishedHike {...PROPS} />)
    expect(container.textContent).not.toMatch(/%|behind|ahead of|on track|streak/i)
  })
})
