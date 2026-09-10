// In view (#1373, frame 12a): the viewport's waypoints as a list, in trail
// order, with distances only where both miles are known.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { InViewSheet, type InViewSheetProps } from './InViewSheet'

const POINTS = [
  {
    id: 'spring',
    type: 'water',
    lat: 41.2,
    lon: -74.5,
    confidence: 'low' as const,
    name: 'Murray spring',
  },
  {
    id: 'shelter',
    type: 'shelter',
    lat: 41.3,
    lon: -74.5,
    confidence: 'high' as const,
    name: 'Brink Road shelter',
  },
  { id: 'view', type: 'viewpoint', lat: 41.4, lon: -74.5, confidence: 'high' as const },
]

const MILES: Record<string, number> = { spring: 1336.4, shelter: 1318.4 }

const PROPS: InViewSheetProps = {
  open: true,
  points: POINTS,
  total: 23,
  currentMile: 1336.3,
  mileOf: (id) => MILES[id],
  units: 'imperial',
  onSelectPoi: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('what is in view', () => {
  it('counts against the phone, lists in mile order, and prints a distance only where both miles are known', () => {
    render(<InViewSheet {...PROPS} />)

    expect(screen.getByRole('dialog', { name: 'In view' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'In view · 3 of 23' })).toBeInTheDocument()

    const rows = within(screen.getByRole('list')).getAllByRole('button')
    // The shelter at mi 1,318.4 before the spring at 1,336.4; the point the
    // download cannot place comes last, by name.
    expect(rows[0]).toHaveTextContent('Brink Road shelter')
    expect(rows[0]).toHaveTextContent('shelter · mi 1,318.4 · 17.9 mi away')
    expect(rows[1]).toHaveTextContent('Murray spring')
    expect(rows[1]).toHaveTextContent('water · mi 1,336.4 · 0.1 mi away')
    expect(rows[2]).toHaveTextContent('Viewpoint')
    expect(rows[2]).not.toHaveTextContent(/away|mi \d/)
  })

  it('opens the waypoint a row names, the same card a pin opens', async () => {
    const user = userEvent.setup()
    const onSelectPoi = vi.fn()
    render(<InViewSheet {...PROPS} onSelectPoi={onSelectPoi} />)

    await user.click(screen.getByRole('button', { name: /Murray spring/ }))
    expect(onSelectPoi).toHaveBeenCalledWith('spring')
  })

  it('prints no distance without the hiker’s own mile, and rides staleness words where given', () => {
    render(
      <InViewSheet
        {...PROPS}
        currentMile={null}
        stalenessFor={(id) =>
          id === 'spring'
            ? {
                treatment: { ring: 'amber', faded: false } as never,
                words: 'flowing 3 days ago',
              }
            : null
        }
      />,
    )
    const spring = screen.getByRole('button', { name: /Murray spring/ })
    expect(spring).toHaveTextContent('water · mi 1,336.4 · flowing 3 days ago')
    expect(spring).not.toHaveTextContent(/away/)
  })

  it('counts only what is in view when the shell gives no total, and says what to do with nothing', () => {
    render(<InViewSheet {...PROPS} total={undefined} />)
    expect(screen.getByRole('heading', { name: 'In view · 3' })).toBeInTheDocument()

    cleanup()
    render(<InViewSheet {...PROPS} points={[]} />)
    expect(screen.getByText(/Nothing the map draws is in view/)).toBeInTheDocument()
    expect(screen.queryByText(/signal|online/i)).toBeNull()
  })

  it('renders nothing while closed', () => {
    const { container } = render(<InViewSheet {...PROPS} open={false} />)
    expect(container).toBeEmptyDOMElement()
  })
})
