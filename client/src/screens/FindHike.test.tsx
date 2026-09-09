import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FindHike, type FindHikeProps } from './FindHike'
import { STANDARD_PACE } from '../lib/pace'
import type { HikePlaceOption, SuggestedHike } from '../lib/suggestedHikes'

// The Find-a-hike screen's honesty contract (#1284), asserted where it
// renders: a facet nothing can answer is not a chip, the number a sheet's
// button promises is the number the list then shows, a removed chip re-runs
// the query, and an unmeasured climb prints no time.

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const NJ = { lon: -74.6, lat: 41.2 }
const VA = { lon: -80.7, lat: 37.3 }

function hike(
  overrides: Partial<SuggestedHike> & Pick<SuggestedHike, 'id'>,
): SuggestedHike {
  return {
    name: overrides.id,
    miles: 5,
    climb: { gainFt: 500, lossFt: 500 },
    difficulty: 'moderate',
    author: { kind: 'club', name: 'A club' },
    segments: [
      [
        { coord: [NJ.lon, NJ.lat], poiId: null },
        { coord: [NJ.lon + 0.01, NJ.lat], poiId: null },
      ],
    ],
    ...overrides,
  }
}

const SUNRISE = hike({
  id: 'sunrise',
  name: 'Sunrise Mtn loop',
  miles: 6.2,
  climb: { gainFt: 980, lossFt: 980 },
  author: { kind: 'club', name: 'NY-NJ Trail Conference' },
  transit: { line: 'NJT 197', toStop: 'Culvers Gap', walkMiles: 0.3, source: 'NJT' },
})
const ANGELS = hike({
  id: 'angels',
  name: 'Angels Rest',
  miles: 5.6,
  climb: { gainFt: 1540, lossFt: 1540 },
  difficulty: 'strenuous',
  author: { kind: 'guidebook', name: 'L. Adkins' },
  segments: [
    [
      { coord: [VA.lon, VA.lat], poiId: null },
      { coord: [VA.lon + 0.02, VA.lat], poiId: null },
    ],
  ],
})
const POCHUCK = hike({
  id: 'pochuck',
  name: 'Pochuck boardwalk',
  miles: 3.6,
  climb: { gainFt: 120, lossFt: 120 },
  difficulty: 'easy',
  author: { kind: 'hiker', name: '@slackpack' },
  transit: { line: 'NJT 890', toStop: 'Vernon', walkMiles: 0.6, source: 'NJ Transit' },
})
const WAPITI = hike({
  id: 'wapiti',
  name: 'Wapiti to Docs Knob',
  miles: 7.9,
  climb: null,
  author: { kind: 'ourhike', name: 'Vernon Trails' },
  segments: [
    [
      { coord: [VA.lon + 0.05, VA.lat + 0.05], poiId: null },
      { coord: [VA.lon + 0.07, VA.lat + 0.05], poiId: null },
    ],
  ],
})
const HIKES = [SUNRISE, ANGELS, POCHUCK, WAPITI]

const PLACES: HikePlaceOption[] = [
  { id: 'pearisburg', name: 'Pearisburg', kind: 'town', at: VA },
  { id: 'culvers', name: 'Culvers Gap trailhead', kind: 'trailhead', at: NJ },
]

function props(overrides: Partial<FindHikeProps> = {}): FindHikeProps {
  return {
    hikes: HIKES,
    places: PLACES,
    fixAt: null,
    units: 'imperial',
    pace: STANDARD_PACE,
    onBack: vi.fn(),
    ...overrides,
  }
}

/** The names on the list, in the order they are drawn. */
function listed(): string[] {
  return [...document.querySelectorAll('.suggested-hike__name')].map(
    (name) => name.textContent ?? '',
  )
}

describe('the header', () => {
  it('goes back to Today from the crumb', async () => {
    const onBack = vi.fn()
    const user = userEvent.setup()
    render(<FindHike {...props({ onBack })} />)

    await user.click(screen.getByRole('button', { name: '‹ Today' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('offers "Near me" only while there is a fix', () => {
    const { rerender } = render(<FindHike {...props({ fixAt: null })} />)
    expect(screen.queryByRole('button', { name: /near me/i })).toBeNull()
    expect(screen.getByText('Routes on this phone')).toBeInTheDocument()

    rerender(<FindHike {...props({ fixAt: NJ })} />)
    expect(screen.getByRole('button', { name: /near me/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByText('Near you')).toBeInTheDocument()
  })

  it('renders no chip for a facet no route on the phone can answer', () => {
    // No transit published anywhere, and nothing that can be priced.
    render(
      <FindHike
        {...props({
          hikes: [{ ...ANGELS, climb: null }, { ...WAPITI }],
        })}
      />,
    )

    expect(screen.queryByRole('button', { name: 'Transit ▾' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Time ▾' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Difficulty ▾' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Author ▾' })).toBeInTheDocument()
  })

  it('says where the boundary is over an empty phone, and offers no chips', () => {
    render(<FindHike {...props({ hikes: [] })} />)

    expect(
      screen.getByText(/only routes inside what you have downloaded/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /▾/ })).toBeNull()
    expect(document.body.textContent).not.toMatch(/no hikes here/i)
  })

  it('resolves the field against the phone’s own towns and trailheads', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props({ fixAt: NJ })} />)

    await user.type(screen.getByRole('searchbox', { name: 'Where' }), 'pear')
    await user.click(screen.getByRole('button', { name: /Pearisburg/ }))

    expect(screen.getByText('Near Pearisburg')).toBeInTheDocument()
    // Anchored on the place now, ordered outward from it - and nothing cut.
    expect(listed()[0]).toBe('Angels Rest')
    expect(listed()).toHaveLength(HIKES.length)
    expect(screen.getByRole('button', { name: /near me/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })
})

describe('the list', () => {
  it('prints a duration from the cached climb and says plainly when there is none', () => {
    render(<FindHike {...props()} />)

    expect(screen.getByText('6.2 mi · ≈2h 30m · +980 ft')).toBeInTheDocument()
    expect(screen.getByText('7.9 mi · no time — climb unmeasured')).toBeInTheDocument()
  })

  it('names every publisher and marks transit only where it was published', () => {
    render(<FindHike {...props()} />)

    expect(screen.getByText('Guidebook route · L. Adkins')).toBeInTheDocument()
    expect(screen.getByText('OurHike pick · route by Vernon Trails')).toBeInTheDocument()
    expect(
      screen.getAllByRole('img', { name: 'Reachable by public transport' }),
    ).toHaveLength(2)
  })

  it('renders the rows as things to read until there is a detail to open', () => {
    render(<FindHike {...props()} />)

    expect(screen.queryByRole('button', { name: /sunrise mtn loop/i })).toBeNull()
    expect(screen.getByRole('article', { name: 'Sunrise Mtn loop' })).toBeInTheDocument()
  })
})

describe('one facet sheet at a time', () => {
  it('counts each option, and the primary button promises the number the list then shows', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)

    await user.click(screen.getByRole('button', { name: 'Time ▾' }))
    const sheet = screen.getByRole('dialog', { name: 'Time to complete' })
    expect(within(sheet).getByText('at your pace')).toBeInTheDocument()
    expect(within(sheet).getByTestId('facet-count-under2')).toHaveTextContent('1')
    expect(within(sheet).getByTestId('facet-count-2to4')).toHaveTextContent('2')
    expect(
      within(sheet).getByRole('button', { name: /show 4 hikes/i }),
    ).toBeInTheDocument()

    await user.click(within(sheet).getByRole('button', { name: /2 – 4 hours/ }))
    const show = within(sheet).getByRole('button', { name: /show 2 hikes/i })
    await user.click(show)

    // The results view, with the same two, and the count as its title.
    expect(screen.getByRole('heading', { name: '2 hikes' })).toBeInTheDocument()
    expect(listed().sort()).toEqual(['Angels Rest', 'Sunrise Mtn loop'])
    expect(screen.queryByRole('dialog')).toBeNull()
    // The applied filter as a removable chip.
    expect(screen.getByRole('button', { name: /2–4 h/ })).toBeInTheDocument()
  })

  it('keeps the caveat that a time is a duration at the hiker’s pace, never an arrival', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)

    await user.click(screen.getByRole('button', { name: 'Time ▾' }))
    expect(screen.getByText(/never an arrival time/i)).toBeInTheDocument()
    expect(screen.getByText(/listed without one/i)).toBeInTheDocument()
  })

  it('says a rating is quoted from the publisher, never the app’s', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)

    await user.click(screen.getByRole('button', { name: 'Difficulty ▾' }))
    expect(screen.getByText(/never rated by the app/i)).toBeInTheDocument()
    expect(screen.getByTestId('facet-count-easy')).toHaveTextContent('1')
  })

  it('lists the named publishers under each kind', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)

    await user.click(screen.getByRole('button', { name: 'Author ▾' }))
    const sheet = screen.getByRole('dialog', { name: 'Who wrote it' })
    expect(within(sheet).getByText('NY-NJ Trail Conference')).toBeInTheDocument()
    expect(within(sheet).getByText('L. Adkins')).toBeInTheDocument()
  })

  it('Clear unsets that facet only and dismisses', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)

    await user.click(screen.getByRole('button', { name: 'Transit ▾' }))
    await user.click(
      screen.getByRole('button', { name: /reachable by public transport/i }),
    )
    await user.click(screen.getByRole('button', { name: /show 2 hikes/i }))
    await user.click(screen.getByRole('button', { name: '+ filter' }))
    await user.click(screen.getByRole('button', { name: 'Difficulty ▾' }))
    // ANCHORED, and the shape is not arbitrary: an option's accessible name
    // is its label run together with its count ("Easy1"), because the label
    // and the count are adjacent inline spans with no whitespace between
    // them. Since #1290 took the scale to five levels, a bare /Easy/ also
    // matches "Easy to Moderate" and the query becomes ambiguous.
    await user.click(screen.getByRole('button', { name: /^Easy\s*\d*$/ }))
    await user.click(screen.getByRole('button', { name: /show 1 hike$/i }))
    expect(listed()).toEqual(['Pochuck boardwalk'])

    await user.click(screen.getByRole('button', { name: '+ filter' }))
    await user.click(screen.getByRole('button', { name: 'Difficulty ▾' }))
    await user.click(screen.getByRole('button', { name: 'Clear' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    // Transit still applied, difficulty gone.
    expect(listed().sort()).toEqual(['Pochuck boardwalk', 'Sunrise Mtn loop'])
    expect(screen.getByRole('button', { name: 'Transit ▾' })).toHaveClass(
      'find-hike__chip--set',
    )
    expect(screen.getByRole('button', { name: 'Difficulty ▾' })).not.toHaveClass(
      'find-hike__chip--set',
    )
  })

  it('closing the sheet discards what was picked but not shown', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)

    await user.click(screen.getByRole('button', { name: 'Difficulty ▾' }))
    await user.click(screen.getByRole('button', { name: /^Easy\s*\d*$/ }))
    await user.click(screen.getByTestId('facet-scrim'))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(listed()).toHaveLength(HIKES.length)
  })
})

describe('the results', () => {
  async function toResults(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('button', { name: 'Transit ▾' }))
    await user.click(
      screen.getByRole('button', { name: /reachable by public transport/i }),
    )
    await user.click(screen.getByRole('button', { name: /show 2 hikes/i }))
  }

  it('promotes the first result to the hero and lists the rest as rows', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)
    await toResults(user)

    expect(document.querySelectorAll('.find-hike__hero')).toHaveLength(1)
    expect(document.querySelectorAll('.find-hike__row')).toHaveLength(1)
    expect(screen.getByText('Transit as the publisher listed it')).toBeInTheDocument()
  })

  it('re-runs the query when a chip’s ✕ drops its filter', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)
    await toResults(user)
    expect(screen.getByRole('heading', { name: '2 hikes' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /By transit/ }))

    expect(screen.getByRole('heading', { name: '4 hikes' })).toBeInTheDocument()
    expect(listed()).toHaveLength(4)
    expect(screen.queryByRole('button', { name: /By transit/ })).toBeNull()
  })

  it('offers a sort control only where there is a choice, and applies the pick', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props()} />)
    await toResults(user)

    // No fix: shortest and easiest are honest, nearest is not.
    await user.click(screen.getByRole('button', { name: 'shortest first ▾' }))
    const sheet = screen.getByRole('dialog', { name: 'Order these by' })
    expect(within(sheet).queryByRole('button', { name: /nearest/ })).toBeNull()
    await user.click(within(sheet).getByRole('button', { name: /easiest first/ }))

    expect(screen.getByRole('button', { name: 'easiest first ▾' })).toBeInTheDocument()
    expect(listed()).toEqual(['Pochuck boardwalk', 'Sunrise Mtn loop'])
  })

  it('prints the sort as a word when only one is honest', async () => {
    const user = userEvent.setup()
    render(
      <FindHike
        {...props({
          hikes: [
            { ...SUNRISE, difficulty: null },
            { ...POCHUCK, difficulty: null },
          ],
        })}
      />,
    )
    await toResults(user)

    expect(screen.queryByRole('button', { name: /first ▾/ })).toBeNull()
    expect(screen.getByText('shortest first')).toBeInTheDocument()
  })

  it('says so when nothing matches, rather than "no hikes here"', async () => {
    const user = userEvent.setup()
    render(<FindHike {...props({ hikes: [ANGELS, WAPITI] })} />)

    await user.click(screen.getByRole('button', { name: 'Difficulty ▾' }))
    await user.click(screen.getByRole('button', { name: /^Easy\s*\d*$/ }))
    await user.click(screen.getByRole('button', { name: /show 0 hikes/i }))

    expect(screen.getByText(/nothing on this phone matches/i)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/no hikes here/i)
  })
})
