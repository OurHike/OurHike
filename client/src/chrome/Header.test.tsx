import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Header } from './Header'

// WIREFRAMES.md, map screen §2 - the header is a READ-ONLY zone. Trail + state
// eyebrow, current mile + direction in mono, and on the right exactly two 38px
// icon buttons: legend then search. The doc's words are "Nothing else lives
// here," which is a real constraint worth a regression test - the header is
// prime screen space and the obvious place for scope to creep.

const PROPS = {
  trailName: 'Appalachian Trail',
  state: 'Virginia',
  mile: 1407.2,
  direction: 'NOBO' as const,
  onOpenLegend: vi.fn(),
  onOpenSearch: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Header', () => {
  it('names the trail and the state in the eyebrow', () => {
    render(<Header {...PROPS} />)

    expect(screen.getByText(/Appalachian Trail/)).toBeInTheDocument()
    expect(screen.getByText(/Virginia/)).toBeInTheDocument()
  })

  it('renders mile and direction exactly as WIREFRAMES.md spells them', () => {
    render(<Header {...PROPS} />)

    // "mi 1,407.2 · NOBO" - thousands separator, one decimal place.
    expect(screen.getByText('mi 1,407.2 · NOBO')).toBeInTheDocument()
  })

  it('keeps one decimal place even on a whole mile, so the number never jitters in width', () => {
    render(<Header {...PROPS} mile={1400} />)

    expect(screen.getByText('mi 1,400.0 · NOBO')).toBeInTheDocument()
  })

  it('renders a southbound hike as SOBO', () => {
    render(<Header {...PROPS} direction="SOBO" />)

    expect(screen.getByText('mi 1,407.2 · SOBO')).toBeInTheDocument()
  })

  it('has no trail logo when none is given', () => {
    const { container } = render(<Header {...PROPS} />)

    expect(container.querySelector('.map-header__trail-logo')).toBeNull()
  })

  it("renders the trail's own mark to the left of its name when one is given", () => {
    const { container } = render(<Header {...PROPS} trailLogo="/at-logo.svg" />)

    const logo = container.querySelector('.map-header__trail-logo')
    expect(logo).toHaveAttribute('src', '/at-logo.svg')
    // Decorative - the eyebrow text already names the trail in words.
    expect(logo).toHaveAttribute('alt', '')
  })

  it('offers exactly two buttons - legend, then search - and nothing else', () => {
    render(<Header {...PROPS} />)
    const buttons = screen.getAllByRole('button')

    expect(buttons).toHaveLength(2)
    expect(buttons[0]).toHaveAccessibleName(/legend/i)
    expect(buttons[1]).toHaveAccessibleName(/search/i)
  })

  it('opens the legend when the legend button is pressed', async () => {
    const user = userEvent.setup()
    render(<Header {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /legend/i }))

    expect(PROPS.onOpenLegend).toHaveBeenCalledTimes(1)
    expect(PROPS.onOpenSearch).not.toHaveBeenCalled()
  })

  it('opens search when the search button is pressed', async () => {
    const user = userEvent.setup()
    render(<Header {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /search/i }))

    expect(PROPS.onOpenSearch).toHaveBeenCalledTimes(1)
    expect(PROPS.onOpenLegend).not.toHaveBeenCalled()
  })

  it('is a banner landmark, so the read-only zone is skippable by screen reader', () => {
    render(<Header {...PROPS} />)

    expect(screen.getByRole('banner')).toBeInTheDocument()
  })
})
