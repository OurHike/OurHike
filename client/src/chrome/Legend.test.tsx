import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Legend } from './Legend'

// WIREFRAMES.md §2 (Legend) plus TESTING.md item 7. Two rules carry real
// weight beyond layout:
//
//  - The legend lists ONLY what is in the current viewport, with counts, and
//    recomputes as the map moves. It is not the settings list of every
//    possible category - WIREFRAMES.md is explicit that the full 10-category
//    list lives in Settings, not here.
//  - Closure and serious-warning rows carry "Always shown" and have NO hide
//    control. Not merely defaulted-on: there is no affordance to turn a safety
//    layer off, here or anywhere else in the app.

const BBOX = { west: -78, south: 39, east: -77, north: 40 }

const POINTS = [
  { id: 'w1', type: 'water', lat: 39.5, lon: -77.5, confidence: 'high' as const },
  { id: 'w2', type: 'water', lat: 39.6, lon: -77.4, confidence: 'high' as const },
  { id: 'w3', type: 'water', lat: 39.7, lon: -77.3, confidence: 'low' as const },
  { id: 's1', type: 'shelter', lat: 39.4, lon: -77.6, confidence: 'high' as const },
  { id: 'c1', type: 'closure', lat: 39.3, lon: -77.7, confidence: 'high' as const },
  {
    id: 'x1',
    type: 'serious-warning',
    lat: 39.2,
    lon: -77.8,
    confidence: 'high' as const,
  },
  // Well outside the bbox - must never appear.
  { id: 'far', type: 'campsite', lat: 20, lon: -100, confidence: 'high' as const },
]

const PROPS = {
  open: true,
  bbox: BBOX,
  points: POINTS,
  blazeCounts: [
    { blaze: 'White', count: 12 },
    { blaze: 'Blue', count: 3 },
  ],
  hiddenTypes: new Set<string>(),
  onToggleType: vi.fn(),
  onClose: vi.fn(),
}

// Exact accessible names throughout: "Water" and "Water · Unverified" are two
// separate rows, and a loose regex would match both.
function rowFor(name: string) {
  return screen.getByRole('listitem', { name })
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Legend', () => {
  it('renders nothing while closed', () => {
    render(<Legend {...PROPS} open={false} />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('is a labelled dialog when open, so focus and escape behave like a sheet', () => {
    render(<Legend {...PROPS} />)

    expect(screen.getByRole('dialog', { name: /legend/i })).toBeInTheDocument()
  })

  it('counts what is in the viewport', () => {
    render(<Legend {...PROPS} />)

    expect(rowFor('Water')).toHaveTextContent('2')
  })

  it('leaves out what is outside the viewport entirely', () => {
    render(<Legend {...PROPS} />)

    expect(screen.queryByRole('listitem', { name: 'Campsite' })).not.toBeInTheDocument()
  })

  it('recomputes when the map moves, rather than holding the first viewport', () => {
    const { rerender } = render(<Legend {...PROPS} />)
    expect(screen.getByRole('listitem', { name: 'Shelter' })).toBeInTheDocument()

    // Pan north-east, leaving the shelter behind.
    rerender(
      <Legend {...PROPS} bbox={{ west: -77.5, south: 39.55, east: -77, north: 40 }} />,
    )

    expect(screen.queryByRole('listitem', { name: 'Shelter' })).not.toBeInTheDocument()
  })

  it('splits low-confidence points into their own "Unverified" row', () => {
    render(<Legend {...PROPS} />)

    expect(rowFor('Water · Unverified')).toHaveTextContent('1')
  })

  it('lists the blaze colours in view, with counts', () => {
    render(<Legend {...PROPS} />)

    expect(rowFor('White blaze')).toHaveTextContent('12')
    expect(rowFor('Blue blaze')).toHaveTextContent('3')
  })

  it('offers a hide control on an ordinary row', async () => {
    const user = userEvent.setup()
    render(<Legend {...PROPS} />)

    await user.click(within(rowFor('Water')).getByRole('button'))

    expect(PROPS.onToggleType).toHaveBeenCalledWith('water')
  })

  it.each(['Closure', 'Serious warning'])(
    'gives the %s row no hide control at all - a safety layer has no off switch',
    (label) => {
      render(<Legend {...PROPS} />)
      const row = rowFor(label)

      expect(within(row).queryByRole('button')).not.toBeInTheDocument()
    },
  )

  it.each(['Closure', 'Serious warning'])('tags the %s row "Always shown"', (label) => {
    render(<Legend {...PROPS} />)

    expect(rowFor(label)).toHaveTextContent(/always shown/i)
  })

  it('shows an ordinary row as hidden once it has been toggled off', () => {
    render(<Legend {...PROPS} hiddenTypes={new Set(['water'])} />)

    expect(within(rowFor('Water')).getByRole('button')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('closes when asked', async () => {
    const user = userEvent.setup()
    render(<Legend {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /close/i }))

    expect(PROPS.onClose).toHaveBeenCalledTimes(1)
  })

  it('says so plainly when the viewport holds nothing, instead of showing an empty sheet', () => {
    render(<Legend {...PROPS} points={[]} blazeCounts={[]} />)

    expect(screen.getByText(/nothing on this part of the map/i)).toBeInTheDocument()
  })
})
