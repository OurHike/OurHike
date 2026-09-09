import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Header } from './Header'

// The floating identity plate (#1054), still a READ-ONLY zone: trail + state
// eyebrow, current mile + direction in mono, the status strip in its one
// typed slot, and exactly two 38px icon buttons - legend then search.
// WIREFRAMES.md's words were "Nothing else lives here," and the constraint
// survives the shape change - the plate is prime screen space and the
// obvious place for scope to creep.

const PROPS = {
  trailName: 'Appalachian Trail',
  state: 'Virginia',
  // Already decided by the shell since #312 - what the line SAYS, and which
  // of eight situations it is saying it about, is lib/positionLine.ts's job
  // and is tested there. What is left here is that the header renders it.
  position: 'mi 1,407.2 · NOBO',
  // The slot is typed to the status strip; a marker is enough to assert the
  // plate renders what it is handed, and StatusStrip.test.tsx owns the rest.
  strip: <span data-testid="strip-stand-in" />,
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

  it('renders the position line it is handed, in the mono slot', () => {
    render(<Header {...PROPS} />)

    // "mi 1,407.2 · NOBO" - thousands separator, one decimal place.
    expect(screen.getByText('mi 1,407.2 · NOBO')).toBeInTheDocument()
  })

  it('renders a settled state in the same slot, without dressing it up', () => {
    // The half of #312 this component owns. It used to render "Looking for
    // GPS…" for every mile-less state, including three that never resolve, so
    // the words could not be told apart from here. Now the slot says whatever
    // the shell decided - and this test is what keeps it from growing its own
    // opinion about which of those states deserves the mono slot.
    render(<Header {...PROPS} position="Location is off" />)

    expect(screen.getByText('Location is off')).toBeInTheDocument()
    expect(screen.queryByText(/Looking for GPS/)).not.toBeInTheDocument()
  })

  it('renders the strip into its one typed slot', () => {
    render(<Header {...PROPS} />)

    expect(screen.getByTestId('strip-stand-in')).toBeInTheDocument()
  })

  it('has no trail logo when none is given', () => {
    const { container } = render(<Header {...PROPS} />)

    expect(container.querySelector('.map-plate__trail-logo')).toBeNull()
  })

  it("renders the trail's own mark to the left of its name when one is given", () => {
    const { container } = render(<Header {...PROPS} trailLogo="/at-logo.svg" />)

    const logo = container.querySelector('.map-plate__trail-logo')
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
