import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Legend } from './Legend'
import { glyphPath, poiGlyphPath } from '../map/poiIcons'
import { WARNING_GLYPH } from '../map/warningPin'
import { CLOSURE_COLOR } from '../lib/closureStyle'

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
    // Pressed means SHOWN. The control used to be a separate "hide" dot, where
    // pressed sensibly meant the hide action was engaged; the row is now the
    // category itself and greys out when it is off, so the old polarity would
    // have a row that plainly reads as off announcing itself as pressed.
    render(<Legend {...PROPS} hiddenTypes={new Set(['water'])} />)

    expect(within(rowFor('Water')).getByRole('button')).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(within(rowFor('Shelter')).getByRole('button')).toHaveAttribute(
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

// --- The map's own icons (#572) -------------------------------------------
//
// The legend named categories the map draws as pins and drew none of them.
// What is asserted here is not "an icon is present" but that it is THE icon -
// the same glyph data, the same broken rim, the same barred band - because a
// legend drawing its own approximation of a pin is worse than one drawing
// none: it teaches a symbol the map does not use.

function iconIn(row: HTMLElement): Element | null {
  return row.querySelector('.legend__icon')
}

describe('legend icons are the map’s icons', () => {
  it('gives a row the silhouette the map draws for that type', () => {
    render(<Legend {...PROPS} />)

    expect(iconIn(rowFor('Water'))?.querySelector('.map-icon__glyph')).toHaveAttribute(
      'd',
      poiGlyphPath('water'),
    )
  })

  it('breaks the rim on an unverified row, which is how the map says it', () => {
    // The row already says "Unverified" in words. The map says the same thing
    // with a dashed rim and nothing on screen connected the two, which left
    // this panel teaching half of its own vocabulary.
    render(<Legend {...PROPS} />)

    expect(
      iconIn(rowFor('Water · Unverified'))?.querySelector('.map-icon__edge'),
    ).toHaveAttribute('stroke-dasharray')
  })

  it('leaves a verified rim unbroken', () => {
    render(<Legend {...PROPS} />)

    expect(iconIn(rowFor('Water'))?.querySelector('.map-icon__edge')).not.toHaveAttribute(
      'stroke-dasharray',
    )
  })

  it('draws a closure as the barred band it is, not as a pin it never was', () => {
    render(<Legend {...PROPS} />)
    const icon = iconIn(rowFor('Closure'))

    expect(icon?.querySelector('.map-icon__closure-band')).toHaveAttribute(
      'stroke',
      CLOSURE_COLOR,
    )
    expect(icon?.querySelector('.map-icon__disc')).toBeNull()
  })

  it('draws a serious warning as the hazard triangle', () => {
    render(<Legend {...PROPS} />)

    expect(
      iconIn(rowFor('Serious warning'))?.querySelector('.map-icon__glyph'),
    ).toHaveAttribute('d', glyphPath(WARNING_GLYPH))
  })

  it('gives a safety row its icon too, without giving it a control', () => {
    render(<Legend {...PROPS} />)
    const row = rowFor('Closure')

    expect(iconIn(row)).not.toBeNull()
    expect(within(row).queryByRole('button')).not.toBeInTheDocument()
  })
})

// --- The row is the control (#572) ----------------------------------------
//
// WIREFRAMES.md §2 has said "rows are tappable to hide" since before this
// panel was built. What shipped was a 20px dot at the end of a 44px row, so a
// tap on the word "Water" did nothing and said nothing about having done
// nothing. Each of these taps used to miss.

describe('the whole legend row is the hide control', () => {
  it('turns a category off from a tap on its name', async () => {
    const user = userEvent.setup()
    render(<Legend {...PROPS} />)

    await user.click(within(rowFor('Water')).getByText('Water'))

    expect(PROPS.onToggleType).toHaveBeenCalledWith('water')
  })

  it('turns a category off from a tap on its icon', async () => {
    const user = userEvent.setup()
    render(<Legend {...PROPS} />)

    await user.click(iconIn(rowFor('Water')) as Element)

    expect(PROPS.onToggleType).toHaveBeenCalledWith('water')
  })

  it('turns a category off from a tap on its count', async () => {
    const user = userEvent.setup()
    render(<Legend {...PROPS} />)

    await user.click(within(rowFor('Water')).getByText('2'))

    expect(PROPS.onToggleType).toHaveBeenCalledWith('water')
  })

  it('holds the icon, the name and the count in one button', () => {
    render(<Legend {...PROPS} />)
    const button = within(rowFor('Water')).getByRole('button')

    expect(button.querySelector('.legend__icon')).not.toBeNull()
    expect(button).toHaveTextContent('Water')
    expect(button).toHaveTextContent('2')
  })

  it('greys the row out while its category is off', () => {
    // The channel a sighted hiker reads, and the reason aria-pressed had to
    // flip with it - see the polarity note above.
    render(<Legend {...PROPS} hiddenTypes={new Set(['water'])} />)

    expect(rowFor('Water')).toHaveClass('legend__row--hidden')
    expect(rowFor('Shelter')).not.toHaveClass('legend__row--hidden')
  })

  it('never greys a safety row, whatever the hidden set says', () => {
    // hiddenTypes is the shell's state and nothing in this panel can put a
    // closure in it - but if something ever did, the row must not read as off
    // while the map goes on drawing it. What is on the map and what this panel
    // says about it cannot be allowed to disagree about a closure.
    render(<Legend {...PROPS} hiddenTypes={new Set(['closure'])} />)

    expect(rowFor('Closure')).not.toHaveClass('legend__row--hidden')
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
    //
    // Asserted against a water row in the same render rather than against the
    // absence of a button named /hide/i, which is what this used to do: once
    // the row itself became the control no button is named "hide" at all, so
    // that assertion had stopped being able to fail.
    render(<Legend {...PROPS} open persistent />)

    expect(within(rowFor('Closure')).queryByRole('button')).not.toBeInTheDocument()
    expect(within(rowFor('Water')).getByRole('button')).toBeInTheDocument()
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
