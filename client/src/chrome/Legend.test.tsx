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

// --- As a persistent desktop panel ----------------------------------------
//
// A panel that is always on screen is not a dialog, and saying it is tells a
// screen-reader user the rest of the app is inert when it is not. That is the
// part of this a stylesheet could not have done, so it is the part tested.

describe('legend as a persistent panel', () => {
  it('renders even when nothing opened it', () => {
    render(<Legend {...PROPS} open={false} persistent />)

    expect(screen.getByRole('region', { name: 'Legend' })).toBeInTheDocument()
  })

  it('is a region rather than a modal dialog', () => {
    render(<Legend {...PROPS} open persistent />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Legend' })).not.toHaveAttribute(
      'aria-modal',
    )
  })

  it('has no close button, because nothing would reopen it', () => {
    // The control that opens the legend is hidden at this width precisely
    // because the legend is always there. A close button would be a trap.
    render(<Legend {...PROPS} open persistent />)

    expect(
      screen.queryByRole('button', { name: /close legend/i }),
    ).not.toBeInTheDocument()
  })

  it('still hides nothing safety-relevant', () => {
    // The rule that holds across the whole app: a safety layer has no off
    // switch, and a different layout is not a reason to grow one.
    render(
      <Legend
        {...PROPS}
        open
        persistent
        points={[
          {
            id: 'c9',
            type: 'closure',
            lat: 39.5,
            lon: -77.5,
            confidence: 'high' as const,
          },
        ]}
      />,
    )

    expect(screen.queryByRole('button', { name: /hide/i })).not.toBeInTheDocument()
  })

  it('is still a dismissable dialog on a phone', () => {
    render(<Legend {...PROPS} open />)

    expect(screen.getByRole('dialog', { name: 'Legend' })).toHaveAttribute(
      'aria-modal',
      'true',
    )
    expect(screen.getByRole('button', { name: /close legend/i })).toBeInTheDocument()
  })

  it('puts the way to the download last, under everything the panel is for', () => {
    // It is the only route to the download window, which makes it worth
    // carrying and does not make it worth the top of a panel someone opens all
    // day to ask what is around them. Asserted as a position rather than as
    // presence, because presence is not the part that was got wrong.
    const { container } = render(
      <Legend {...PROPS} onOpenDownloads={vi.fn()} backgroundChoice={undefined} />,
    )

    const link = screen.getByRole('button', { name: /choose what to download/i })
    expect(container.querySelector('.legend')?.lastElementChild).toBe(link)
  })

  it('draws no such link where there is no window to open', () => {
    render(<Legend {...PROPS} />)

    expect(screen.queryByRole('button', { name: /download/i })).toBeNull()
  })

  it('admits a download still running with its window shut', () => {
    // The panel a hiker is one tap from while they walk, and since the
    // download window closes over a transfer that keeps going, the only place
    // on the map that says so. Asserted here rather than left to
    // DownloadsLink's own tests because what is at stake is the wiring: an
    // unpassed prop draws a link that is silent about a download in flight,
    // which is exactly the app this was built to stop shipping.
    render(
      <Legend
        {...PROPS}
        onOpenDownloads={vi.fn()}
        downloadActivity={{ kind: 'downloading', doneBytes: 1, totalBytes: 4 }}
      />,
    )

    expect(screen.getByText('Downloading 25%')).toBeVisible()
  })
})

// Saying what is not drawn (#528). Before this the panel counted the viewport
// rectangle and called it "what am I looking at", which at hiking zooms is a row
// reading `Privy · 6` over a map with no privy pin on it.
describe('reporting waypoints that did not fit', () => {
  const bbox = { west: -1, south: -1, east: 1, north: 1 }
  const point = (id: string, type: string) => ({
    id,
    type,
    lat: 0,
    lon: 0,
    confidence: 'high' as const,
  })
  const points = [
    point('w1', 'water'),
    point('w2', 'water'),
    point('p1', 'privy'),
    point('p2', 'privy'),
  ]

  function renderLegend(drawnCounts?: ReadonlyMap<string, number>, belowPoiZoom = false) {
    return render(
      <Legend
        open
        bbox={bbox}
        points={points}
        blazeCounts={[]}
        hiddenTypes={new Set()}
        onToggleType={() => {}}
        onClose={() => {}}
        drawnCounts={drawnCounts}
        belowPoiZoom={belowPoiZoom}
      />,
    )
  }

  it('shows the drawn count beside the present one where they differ', () => {
    renderLegend(
      new Map([
        ['water::high', 1],
        ['privy::high', 0],
      ]),
    )

    expect(screen.getByText('1 shown')).toBeInTheDocument()
    expect(screen.getByText('0 shown')).toBeInTheDocument()
  })

  it('says nothing extra on a row that is fully drawn', () => {
    // The panel stays quiet at the zooms where nothing is being dropped.
    renderLegend(
      new Map([
        ['water::high', 2],
        ['privy::high', 2],
      ]),
    )

    expect(screen.queryByText(/shown/)).not.toBeInTheDocument()
    expect(screen.queryByText(/fit at this zoom/)).not.toBeInTheDocument()
  })

  it('puts the drawn figure in the row’s accessible name', () => {
    // A screen-reader user gets "Privy, 2, 0 shown" rather than a bare count
    // that is wrong about what is on the map.
    renderLegend(new Map([['privy::high', 0]]))

    expect(
      screen.getByRole('listitem', { name: /privy · 2 · 0 shown/i }),
    ).toBeInTheDocument()
  })

  it('summarises the drop at the head of the panel', () => {
    renderLegend(
      new Map([
        ['water::high', 1],
        ['privy::high', 0],
      ]),
    )

    expect(screen.getByText(/1 of 4 waypoints fit at this zoom/i)).toBeInTheDocument()
  })

  it('reads exactly as it did before when nothing was measured', () => {
    renderLegend(undefined)

    expect(screen.queryByText(/shown/)).not.toBeInTheDocument()
    expect(screen.queryByText(/fit at this zoom/)).not.toBeInTheDocument()
  })

  it('keeps the hide control on a row that did not fit', () => {
    // A category being culled is exactly when a hiker might want to hide
    // something else, so the affordance has to survive the new figure.
    renderLegend(new Map([['privy::high', 0]]))

    expect(screen.getByRole('button', { name: /hide privy/i })).toBeInTheDocument()
  })
})

describe('below the zoom waypoints are drawn at', () => {
  const bbox = { west: -1, south: -1, east: 1, north: 1 }

  it('says so, instead of claiming there is nothing here', () => {
    // The old sentence was false in both halves at the opening view: there is
    // plenty here, and zooming OUT is the wrong direction (#528).
    render(
      <Legend
        open
        bbox={bbox}
        points={[]}
        blazeCounts={[]}
        hiddenTypes={new Set()}
        onToggleType={() => {}}
        onClose={() => {}}
        belowPoiZoom
      />,
    )

    expect(screen.getByText(/drawn from a closer zoom/i)).toBeInTheDocument()
    expect(screen.queryByText(/pan or zoom out/i)).not.toBeInTheDocument()
  })

  it('still says "nothing here" when that is the true one', () => {
    render(
      <Legend
        open
        bbox={bbox}
        points={[]}
        blazeCounts={[]}
        hiddenTypes={new Set()}
        onToggleType={() => {}}
        onClose={() => {}}
      />,
    )

    expect(screen.getByText(/pan or zoom out/i)).toBeInTheDocument()
  })
})
