import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Legend } from './Legend'
import { HIDEABLE_TYPES } from '../lib/waypointVisibility'
import { typeLabel } from './legendLabels'
import { glyphPath, poiGlyphPath } from '../map/poiIcons'
import { WARNING_GLYPH } from '../map/warningPin'
import { CLOSURE_COLOR } from '../lib/closureStyle'

// WIREFRAMES.md §2 (Legend) plus TESTING.md item 7. Two rules carry real
// weight beyond layout:
//
//  - The legend's COUNTS are only what is in the current viewport, and
//    recompute as the map moves. The ROWS those counts sit on are every
//    hideable category, in view or not, because a row is also the hide toggle
//    and a switch that vanishes with its category is a switch nobody can find
//    (#723, WIREFRAMES.md §2 as amended). What must not follow is the panel's
//    prose speaking for categories that are not there - so the empty-state
//    sentences and the drop summary are still decided by the viewport alone,
//    and are asserted here to be.
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

// Exact accessible names throughout. A loose regex would match "Water" against
// a row for any category whose label contains it, and the whole point of these
// assertions is which row is which.
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
    // Three: two verified springs and the unverified one, which is counted
    // here rather than split off into a row of its own.
    render(<Legend {...PROPS} />)

    expect(rowFor('Water')).toHaveTextContent('3')
  })

  it('counts what is outside the viewport as none of it, rather than as some', () => {
    // The campsite in POINTS is at 20N/100W, thousands of miles from this
    // rectangle. Its row exists because the row is a switch (#723); the number
    // on it is what keeps the row from claiming there is a campsite here.
    render(<Legend {...PROPS} />)

    expect(rowFor('Campsite')).toHaveTextContent('0')
  })

  it('recomputes when the map moves, rather than holding the first viewport', () => {
    const { rerender } = render(<Legend {...PROPS} />)
    expect(rowFor('Shelter')).toHaveTextContent('1')

    // Pan north-east, leaving the shelter behind.
    rerender(
      <Legend {...PROPS} bbox={{ west: -77.5, south: 39.55, east: -77, north: 40 }} />,
    )

    expect(rowFor('Shelter')).toHaveTextContent('0')
  })

  it('folds unverified points into their category row instead of adding a second one', () => {
    // The legend used to carry "Water · Unverified 1" beside "Water 2". Two
    // rows per category doubled a panel whose columns are about 116px wide,
    // wrapping half the labels onto a second line, and spent that room on a
    // distinction a viewport count cannot act on. The map still draws the
    // broken rim per pin and the waypoint card still says it in words.
    render(<Legend {...PROPS} />)

    expect(
      screen.queryByRole('listitem', { name: /unverified/i }),
    ).not.toBeInTheDocument()
    expect(screen.getAllByRole('listitem', { name: 'Water' })).toHaveLength(1)
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

  it.each(['Closure', 'Serious warning'])(
    'gives the %s row the whole grid width to say it in',
    (label) => {
      // Caught by rendering the panel rather than by a test: a safety row
      // carries the "Always shown" tag on top of everything an ordinary row
      // carries, and once the icon took its 24px the tag was clipped mid-word
      // in a ~116px column - on the two rows that must never look like a
      // rendering accident.
      render(<Legend {...PROPS} />)

      expect(rowFor(label)).toHaveClass('legend__row--always')
      expect(rowFor('Water')).not.toHaveClass('legend__row--always')
    },
  )

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

// --- Every category is reachable from the panel (#723) ---------------------
//
// The reported symptom was two toggles on an Android phone, and it was the
// specification working: the rows came from the viewport, and
// features/POI_VISIBILITY.md's own density table puts 2-4 waypoints in a
// 390 x 700 phone map at z14. Sending a hiker to Settings to turn privies back
// on is the same mistake MAP_OPTIONS.md §4 already reversed for the background
// picker - the moment you want this control is the moment you are looking at
// the map.
//
// The half of this that could go wrong quietly is the other direction: rows for
// categories that are not here must not make the PANEL claim they are. Every
// sentence on it is asserted below to still be the viewport's.
describe('every hideable category has a row, in view or not', () => {
  it('offers a switch for all of them', () => {
    render(<Legend {...PROPS} />)

    for (const type of HIDEABLE_TYPES) {
      expect(
        within(rowFor(typeLabel(type))).getByRole('button'),
        `${type} has no toggle`,
      ).toBeInTheDocument()
    }
  })

  it('turns off a category with nothing of it in view', async () => {
    // The whole point. `privy` appears nowhere in POINTS, so before this it had
    // no row and this tap had nothing to land on.
    const user = userEvent.setup()
    render(<Legend {...PROPS} />)

    await user.click(within(rowFor('Privy')).getByRole('button'))

    expect(PROPS.onToggleType).toHaveBeenCalledWith('privy')
  })

  it('turns one back on from the panel that turned it off', async () => {
    // The trap this issue is most able to build: hide the only water in view,
    // the row disappears with its own count, and the switch back is gone.
    const user = userEvent.setup()
    render(<Legend {...PROPS} hiddenTypes={new Set(['privy'])} />)

    const row = rowFor('Privy')
    expect(row).toHaveClass('legend__row--hidden')
    await user.click(within(row).getByRole('button'))

    expect(PROPS.onToggleType).toHaveBeenCalledWith('privy')
  })

  it('keeps them in one order however the map is panned', () => {
    // The counts come out of a Map keyed by whatever order the points were
    // encountered in, so the grid used to re-shuffle as a hiker walked. A key
    // whose rows move is a key you have to read rather than glance at.
    const labels = () =>
      screen
        .getAllByRole('listitem')
        .map((row) => row.getAttribute('aria-label'))
        .filter((name) => name !== null && !name.endsWith('blaze'))

    const { rerender } = render(<Legend {...PROPS} />)
    const first = labels()

    rerender(
      <Legend {...PROPS} bbox={{ west: -77.5, south: 39.55, east: -77, north: 40 }} />,
    )

    expect(labels().slice(0, HIDEABLE_TYPES.length)).toEqual(
      first.slice(0, HIDEABLE_TYPES.length),
    )
    expect(first.slice(0, HIDEABLE_TYPES.length)).toEqual(HIDEABLE_TYPES.map(typeLabel))
  })

  it('never invents a safety row for a stretch with no closure on it', () => {
    // Closures and serious warnings are not in HIDEABLE_TYPES, have no switch to
    // reach, and a standing "Closure 0" would be this panel making a claim about
    // closures that nothing asked it to make.
    render(<Legend {...PROPS} points={[]} blazeCounts={[]} />)

    expect(screen.queryByRole('listitem', { name: 'Closure' })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('listitem', { name: 'Serious warning' }),
    ).not.toBeInTheDocument()
  })

  it('still says the map is empty here, with eight rows of zero on screen', () => {
    // `isEmpty` is decided by the viewport, not by the grid. Decided by the grid
    // it would never be true again, and the sentence would be dead code that
    // still reads as live.
    render(<Legend {...PROPS} points={[]} blazeCounts={[]} />)

    expect(screen.getByText(/nothing on this part of the map/i)).toBeInTheDocument()
    expect(rowFor('Water')).toHaveTextContent('0')
  })

  it('reports no drop for a category that has nothing to drop', () => {
    // A padded row carries no `drawnCount` at all - "none of them fitted" and
    // "there were none" are different sentences, and only one of them is true
    // of a category with nothing in the rectangle. Measured against the drop
    // summary, which is where a zero would have shown up as a claim.
    render(
      <Legend
        {...PROPS}
        points={[POINTS[0], POINTS[1], POINTS[2]]}
        drawnCounts={new Map([['water', 3]])}
      />,
    )

    expect(screen.queryByText(/fit at this zoom/i)).not.toBeInTheDocument()
    expect(rowFor('Privy')).toHaveTextContent('0')
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

  it('draws the solid-rimmed pin even where the row counts an unverified point', () => {
    // A key says what a category's symbol IS. Now that a row counts both
    // confidences, a rim that broke whenever the points in view happened to be
    // unconfirmed would change the symbol as the hiker panned - and this
    // fixture's water row holds an unverified spring, so the assertion has
    // something to catch. The broken rim still means what it means on the map,
    // one pin at a time, where it is a fact about a place.
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

    await user.click(within(rowFor('Water')).getByText('3'))

    expect(PROPS.onToggleType).toHaveBeenCalledWith('water')
  })

  it('holds the icon, the name and the count in one button', () => {
    render(<Legend {...PROPS} />)
    const button = within(rowFor('Water')).getByRole('button')

    expect(button.querySelector('.legend__icon')).not.toBeNull()
    expect(button).toHaveTextContent('Water')
    expect(button).toHaveTextContent('3')
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

// --- The "Verified?" filter -----------------------------------------------
//
// What became of the "Unverified" rows. They doubled the grid to carry a
// distinction a viewport count cannot act on; this carries the same fact as
// one decision, under the rows rather than inside them.

describe('the "Verified?" toggle', () => {
  const FILTERED = { ...PROPS, onToggleVerifiedOnly: vi.fn() }

  it('is not drawn at all where the shell offers no handler for it', () => {
    // Same rule the downloads link follows: a control that does nothing is
    // worse than one that is not there.
    render(<Legend {...PROPS} />)

    expect(screen.queryByRole('checkbox', { name: /verified/i })).not.toBeInTheDocument()
  })

  it('offers it under the rows, unchecked, when the shell can act on it', () => {
    render(<Legend {...FILTERED} />)

    expect(screen.getByRole('checkbox', { name: 'Verified?' })).not.toBeChecked()
  })

  it('asks the shell to flip it when tapped', async () => {
    const user = userEvent.setup()
    render(<Legend {...FILTERED} />)

    await user.click(screen.getByRole('checkbox', { name: 'Verified?' }))

    expect(FILTERED.onToggleVerifiedOnly).toHaveBeenCalledTimes(1)
  })

  it('takes unverified points out of the counts while it is on', () => {
    // Three springs in this fixture, one of them unconfirmed. The count has to
    // move with the filter or the panel is claiming a spring the map is not
    // drawing.
    render(<Legend {...FILTERED} verifiedOnly />)

    expect(rowFor('Water')).toHaveTextContent('2')
  })

  it('still counts a safety row it cannot filter', () => {
    render(<Legend {...FILTERED} verifiedOnly />)

    expect(rowFor('Closure')).toBeInTheDocument()
  })

  it('says the filter emptied the panel, rather than that the map is empty', async () => {
    // "Nothing here yet, pan or zoom out" is a false claim about a stretch
    // with six unconfirmed springs on it, and it sends a hiker walking away
    // from water.
    render(
      <Legend
        {...FILTERED}
        verifiedOnly
        blazeCounts={[]}
        points={[{ id: 'u', type: 'water', lat: 39.5, lon: -77.5, confidence: 'low' }]}
      />,
    )

    expect(screen.getByText(/nothing here has been confirmed/i)).toBeInTheDocument()
    expect(screen.queryByText(/pan or zoom out/i)).not.toBeInTheDocument()
  })

  it('stays on screen when it has emptied the panel, so it can be turned back off', async () => {
    // A filter that hides itself along with everything else is a trap - the
    // same trap a close button on a panel nothing reopens would be.
    const user = userEvent.setup()
    render(
      <Legend
        {...FILTERED}
        verifiedOnly
        blazeCounts={[]}
        points={[{ id: 'u', type: 'water', lat: 39.5, lon: -77.5, confidence: 'low' }]}
      />,
    )

    await user.click(screen.getByRole('checkbox', { name: 'Verified?' }))

    expect(FILTERED.onToggleVerifiedOnly).toHaveBeenCalled()
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
    const foot = container.querySelector('.legend')?.lastElementChild
    expect(foot).toHaveClass('legend__downloads')
    expect(foot?.lastElementChild).toBe(link)
  })

  it('keeps the background choice with the download, not at the top of the panel', () => {
    // The two ends of one question: "Downloaded" draws the corridor archive,
    // and that link is where a corridor archive comes from. The picker used to
    // open the panel, so a hiker who chose a background this phone had no map
    // for read the note saying so and then had to scroll past every legend row
    // to do anything about it. Asserted as adjacency inside one block, because
    // "both are somewhere in the panel" is what was already true.
    const { container } = render(
      <Legend
        {...PROPS}
        onOpenDownloads={vi.fn()}
        backgroundChoice="usgs_topo_offline"
        onChangeBackground={vi.fn()}
      />,
    )

    const foot = container.querySelector('.legend__downloads')
    expect(
      within(foot as HTMLElement).getByRole('radio', { name: /downloaded/i }),
    ).toBeVisible()
    expect(
      within(foot as HTMLElement).getByRole('button', {
        name: /choose what to download/i,
      }),
    ).toBeVisible()
  })

  it('starts the panel with what is in view, not with a control', () => {
    // The daily question gets the top. A hiker opens this all day to ask what
    // is around them and a handful of times ever to change what is on the
    // phone. Asserted against the pin grid rather than the head, since the
    // heading is not what moved.
    const { container } = render(
      <Legend
        {...PROPS}
        onOpenDownloads={vi.fn()}
        backgroundChoice="hiking_topo_live"
        onChangeBackground={vi.fn()}
      />,
    )

    const pins = container.querySelector('.legend__pins')
    const picker = container.querySelector('.bg-picker')
    expect(pins!.compareDocumentPosition(picker!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
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

describe('the way to every ATC notice (#687)', () => {
  // Moved here from a permanent button across the top of the map screen -
  // chrome/MapScreen.test.tsx now only covers that the hand-off happens;
  // this is the row itself.

  it('is not there when the app holds no ATC notices', () => {
    render(<Legend {...PROPS} onOpenAtcNotices={vi.fn()} />)

    expect(screen.queryByRole('button', { name: /ATC trail update/ })).toBeNull()
  })

  it('draws no such row where the shell offers no handler', () => {
    render(<Legend {...PROPS} atcNoticeCount={6} />)

    expect(screen.queryByRole('button', { name: /ATC trail update/ })).toBeNull()
  })

  it('names every notice it holds', () => {
    render(<Legend {...PROPS} atcNoticeCount={6} onOpenAtcNotices={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'Read all 6 ATC trail updates' }),
    ).toBeInTheDocument()
  })

  it('counts one notice without pluralising it', () => {
    render(<Legend {...PROPS} atcNoticeCount={1} onOpenAtcNotices={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'Read the 1 ATC trail update' }),
    ).toBeInTheDocument()
  })

  it('reports the tap up to the shell', async () => {
    const onOpenAtcNotices = vi.fn()
    render(<Legend {...PROPS} atcNoticeCount={6} onOpenAtcNotices={onOpenAtcNotices} />)

    await userEvent.click(screen.getByRole('button', { name: /ATC trail updates/ }))

    expect(onOpenAtcNotices).toHaveBeenCalledTimes(1)
  })

  it('sits above the downloaded-map block, not inside it', () => {
    // Trail-content-adjacent, not a download errand - #687 is explicit that
    // conflating the two is what this replaced.
    const { container } = render(
      <Legend
        {...PROPS}
        atcNoticeCount={6}
        onOpenAtcNotices={vi.fn()}
        onOpenDownloads={vi.fn()}
      />,
    )

    const atcLink = screen.getByRole('button', { name: /ATC trail updates/ })
    const foot = container.querySelector('.legend__downloads')
    expect(foot).not.toBeNull()
    expect(atcLink.compareDocumentPosition(foot as HTMLElement)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })
})

// Showing one category alone, and the stored preference behind it (#530). The
// control is what makes `waypoint_types_shown` worth wiring rather than tidy:
// hiding a category hands its collision budget to the ones left, so at a crowded
// zoom this is four water pins drawn against forty.
describe('showing one category alone', () => {
  const bbox = { west: -1, south: -1, east: 1, north: 1 }
  const points = [
    { id: 'w1', type: 'water', lat: 0, lon: 0, confidence: 'high' as const },
    { id: 'p1', type: 'privy', lat: 0, lon: 0.1, confidence: 'high' as const },
    { id: 'c1', type: 'closure', lat: 0, lon: 0.2, confidence: 'high' as const },
  ]

  function renderLegend(props: {
    onOnlyType?: (type: string) => void
    onShowAllTypes?: () => void
    typesShown?: readonly string[]
  }) {
    return render(
      <Legend
        open
        bbox={bbox}
        points={points}
        blazeCounts={[]}
        hiddenTypes={new Set()}
        onToggleType={() => {}}
        onClose={() => {}}
        {...props}
      />,
    )
  }

  const wired = (extra: Parameters<typeof renderLegend>[0] = {}) => ({
    onOnlyType: vi.fn(),
    onShowAllTypes: vi.fn(),
    ...extra,
  })

  /** The one control, by the name a screen reader gives it. */
  const picker = () => screen.getByRole('combobox', { name: /showing waypoint types/i })

  it('offers one chooser rather than a button per row', async () => {
    // The whole point of the shape: the action is global, so it costs ONE line
    // here where it cost one control per row inline.
    const props = wired()
    renderLegend(props)

    await userEvent.selectOptions(picker(), 'water')

    expect(props.onOnlyType).toHaveBeenCalledWith('water')
  })

  it('never offers a safety layer in the chooser', () => {
    // The rule is kept by not building the affordance, which is how
    // HIKER_SAFETY.md and MAP_OPTIONS.md §4 say to keep it - not by building it
    // and disabling it.
    renderLegend(wired())

    expect(
      within(picker()).queryByRole('option', { name: /closure/i }),
    ).not.toBeInTheDocument()
  })

  it('lists categories that have no row in this viewport', () => {
    // The second consequence #530 lists: the legend's rows are per-viewport, so a
    // category with nothing in view has no row and could not otherwise be reached
    // from this panel at all.
    renderLegend(wired())

    expect(within(picker()).getByRole('option', { name: /shelter/i })).toBeInTheDocument()
  })

  it('offers nothing where there is nowhere to write the preference', () => {
    renderLegend({})

    expect(screen.queryByRole('combobox', { name: /showing/i })).not.toBeInTheDocument()
  })

  it('offers nothing when it could enter a filter but not leave one', () => {
    // Both handlers are halves of ONE picker now: "All types" is the exit. Half
    // a picker is the trap this issue is most able to build - a map filtered
    // down to privies with nothing on the panel that undoes it.
    renderLegend({ onOnlyType: vi.fn() })

    expect(screen.queryByRole('combobox', { name: /showing/i })).not.toBeInTheDocument()
  })

  it('displays the filter rather than describing it beside a placeholder', () => {
    // THE BUG THIS REPLACES. The control read "Show one only…" whatever the map
    // was drawing, with a sentence next to it carrying the actual state - so the
    // panel said the same thing twice, in two places, and the control's own value
    // disowned it. A selected value cannot disagree with itself.
    renderLegend(wired({ typesShown: ['water'] }))

    expect(picker()).toHaveValue('water')
    expect(
      within(picker()).getByRole('option', { name: 'Water', selected: true }),
    ).toBeInTheDocument()
  })

  it('offers the way back as the picker itself', async () => {
    const props = wired({ typesShown: ['water'] })
    renderLegend(props)

    await userEvent.selectOptions(picker(), 'All types')

    expect(props.onShowAllTypes).toHaveBeenCalledTimes(1)
    expect(props.onOnlyType).not.toHaveBeenCalled()
  })

  it('says the map is unfiltered rather than saying nothing', () => {
    // The control is the one place the mode lives, so it states the mode either
    // way. "All types" is both the readout and the exit, which is why there is no
    // second control to appear and disappear.
    renderLegend(wired({ typesShown: [] }))

    expect(
      within(picker()).getByRole('option', { name: 'All types', selected: true }),
    ).toBeInTheDocument()
  })

  it('reads several categories as a count rather than as one of them', async () => {
    // Reachable only by toggling rows, so it is a readout and not a choice: there
    // is no single tap that means "these three". Naming them would not fit the
    // 272px panel either.
    const props = wired({ typesShown: ['water', 'privy'] })
    renderLegend(props)

    const shown = within(picker()).getByRole('option', { selected: true })
    expect(shown).toHaveTextContent(`2 of ${HIDEABLE_TYPES.length} types`)

    // And it is not a category, so it must never reach the preference.
    await userEvent.selectOptions(picker(), 'privy')
    expect(props.onOnlyType).toHaveBeenCalledWith('privy')
    expect(props.onOnlyType).not.toHaveBeenCalledWith(expect.stringContaining('of'))
  })

  it('drops the count readout once the map is back to one category', () => {
    renderLegend(wired({ typesShown: ['water'] }))

    expect(within(picker()).queryByText(/of \d+ types/)).not.toBeInTheDocument()
  })

  it('keeps the way out on screen even when the filter empties the panel', () => {
    // THE TRAP THIS AVOIDS. "Only privies" in a stretch with no privies leaves no
    // rows at all, and an exit gated on rows existing would disappear with them -
    // the same reasoning the verified-only control already carries.
    render(
      <Legend
        open
        bbox={bbox}
        points={[]}
        blazeCounts={[]}
        hiddenTypes={new Set()}
        onToggleType={() => {}}
        onClose={() => {}}
        typesShown={['privy']}
        {...wired()}
      />,
    )

    expect(picker()).toHaveValue('privy')
    expect(
      within(picker()).getByRole('option', { name: 'All types' }),
    ).toBeInTheDocument()
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

  it('folds the drawn count into the count slot as a fraction where they differ', () => {
    renderLegend(
      new Map([
        ['water', 1],
        ['privy', 0],
      ]),
    )

    expect(screen.getByText('1/2')).toBeInTheDocument()
    expect(screen.getByText('0/2')).toBeInTheDocument()
  })

  it('renders one count element per row, so nothing has to wrap', () => {
    // The defect this design replaced: a second `1 shown` badge beside the
    // count does not fit a two-column row at 390 px, so it wrapped and left
    // rows of unequal height and a ragged column edge. Asserting the element
    // COUNT rather than the width, because jsdom lays nothing out - what can be
    // proved here is that there is only one thing in the slot, which is what
    // makes the wrap impossible. The width itself is a real-browser question
    // and is why the rendering was screenshotted before this landed.
    const { container } = renderLegend(
      new Map([
        ['water', 1],
        ['privy', 0],
      ]),
    )

    // Counted against the ROWS rather than against a literal: the grid is
    // every hideable category now (#723), so a hard number here would be
    // asserting how many types the app ships rather than the invariant, which
    // is one slot per row and no second badge beside it.
    const rows = container.querySelectorAll('.legend__pins .legend__row')
    expect(rows.length).toBeGreaterThan(0)
    expect(container.querySelectorAll('.legend__count')).toHaveLength(rows.length)
    expect(container.querySelector('.legend__drawn')).toBe(null)
  })

  it('says nothing extra on a row that is fully drawn', () => {
    // The panel stays quiet at the zooms where nothing is being dropped. Asserted
    // as the plain count being PRESENT rather than only as the fraction being
    // absent: `queryByText(/shown/)` alone would now pass on a row rendering
    // `2/2`, since the word left with the badge.
    renderLegend(
      new Map([
        ['water', 2],
        ['privy', 2],
      ]),
    )

    expect(screen.getAllByText('2')).toHaveLength(2)
    expect(screen.queryByText('2/2')).not.toBeInTheDocument()
    expect(screen.queryByText(/fit at this zoom/)).not.toBeInTheDocument()
  })

  it('spells the figure out in the row’s accessible name rather than reusing the fraction', () => {
    // A screen-reader user gets "Privy, none of 2 shown" rather than a bare
    // count that is wrong about what is on the map - and rather than `0/2`,
    // whose slash a reader is free to skip, leaving "0 2".
    renderLegend(new Map([['privy', 0]]))

    expect(
      screen.getByRole('listitem', { name: /privy · none of 2 shown/i }),
    ).toBeInTheDocument()
  })

  it('says the number out loud when some did fit', () => {
    renderLegend(new Map([['water', 1]]))

    expect(
      screen.getByRole('listitem', { name: /water · 1 of 2 shown/i }),
    ).toBeInTheDocument()
  })

  it('summarises the drop at the head of the panel', () => {
    renderLegend(
      new Map([
        ['water', 1],
        ['privy', 0],
      ]),
    )

    expect(screen.getByText(/1 of 4 waypoints fit at this zoom/i)).toBeInTheDocument()
  })

  it('reads exactly as it did before when nothing was measured', () => {
    // No measurement is a real state on a cold start, and it must read as "not
    // measured" rather than as "none are drawn" - which a fraction of `0/2`
    // would say, wrongly and alarmingly.
    renderLegend(undefined)

    expect(screen.getAllByText('2')).toHaveLength(2)
    expect(screen.queryByText('0/2')).not.toBeInTheDocument()
    expect(screen.queryByText(/fit at this zoom/)).not.toBeInTheDocument()
  })

  it('keeps the row tappable as the hide control on a row that did not fit', () => {
    // A category being culled is exactly when a hiker might want to hide
    // something else, so the affordance has to survive the new figure. Since #580
    // the ROW is that control - there is no separate "Hide privy" button - so what
    // this checks is that the row is still a pressed-state button carrying the
    // figure rather than a plain span.
    renderLegend(new Map([['privy', 0]]))

    // The figure is on the row's own accessible name; the button is inside it.
    const row = screen.getByRole('listitem', { name: /privy · none of 2 shown/i })
    expect(within(row).getByRole('button')).toHaveAttribute('aria-pressed', 'true')
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

    // Reworded by #603. The dot rank draws below the seam now, so the panel
    // must not say waypoints are absent here - it says what a hiker is looking
    // at (dots) and what zooming in buys (knowing which is which).
    expect(screen.getByText(/show as dots at this zoom/i)).toBeInTheDocument()
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

describe('the drought row', () => {
  const bbox = { west: -80, south: 35, east: -78, north: 37 } as const

  function renderDrought(
    droughtSummary: { miles: number; weekStart: Date | null } | undefined,
    units: 'imperial' | 'metric' = 'imperial',
  ) {
    render(
      <Legend
        open
        bbox={bbox}
        points={[]}
        blazeCounts={[]}
        hiddenTypes={new Set()}
        onToggleType={() => {}}
        onClose={() => {}}
        onToggleDrought={() => {}}
        droughtSummary={droughtSummary}
        units={units}
      />,
    )
  }

  it('does not say "none on the trail" when nothing arrived', () => {
    // The whole point of the row, and the bug it shipped with first: an
    // unreachable artifact and a genuinely drought-free week both draw an
    // empty map, and only one of them is good news (#286's distinction). The
    // week is what says somebody looked, so no week means no reassurance.
    renderDrought({ miles: 0, weekStart: null })

    expect(screen.getByText(/not available/i)).toBeInTheDocument()
    expect(screen.queryByText(/none on the trail/i)).not.toBeInTheDocument()
  })

  it('says none on the trail for a week somebody did look at', () => {
    renderDrought({ miles: 0, weekStart: new Date('2026-08-11') })

    expect(screen.getByText(/none on the trail/i)).toBeInTheDocument()
    expect(screen.getByText(/week of Aug 11/i)).toBeInTheDocument()
  })

  it('reports the affected distance in the hiker’s own units', () => {
    // CONTRIBUTING.md's units standard. This row printed "mi" directly once,
    // which unitDisplay.test.ts caught - the guard proves nothing writes a
    // unit, and this proves the right one comes out.
    renderDrought({ miles: 1388.5, weekStart: new Date('2026-08-11') }, 'metric')

    expect(screen.getByText(/2,235 km affected/)).toBeInTheDocument()
  })

  it('is absent entirely when the shell cannot store the preference', () => {
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

    expect(screen.queryByRole('checkbox', { name: /drought/i })).not.toBeInTheDocument()
  })
})
