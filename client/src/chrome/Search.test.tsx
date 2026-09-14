import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Search } from './Search'

// WIREFRAMES.md Interactions + `7c`. Search takes over the header, works only
// against what is already downloaded, and - the part that matters most - says
// so when it finds nothing. "No results" and "that may exist, just outside
// what you downloaded" are different answers, and only the second one tells
// someone what to do next.

const POIS = [
  { id: '1', name: 'Rocky Run Shelter', type: 'shelter', mile: 1043.2 },
  { id: '2', name: 'Annapolis Rock', type: 'campsite', mile: 1049.1 },
]

const PROPS = {
  open: true,
  pois: POIS,
  onSelect: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Search', () => {
  it('renders nothing while closed', () => {
    render(<Search {...PROPS} open={false} />)

    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
  })

  it('takes over with a focused search box, so typing can start immediately', () => {
    render(<Search {...PROPS} />)

    expect(screen.getByRole('searchbox')).toHaveFocus()
  })

  it('shows no results before anything has been typed', () => {
    render(<Search {...PROPS} />)

    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })

  it('lists matches as the query is typed', async () => {
    const user = userEvent.setup()
    render(<Search {...PROPS} />)

    await user.type(screen.getByRole('searchbox'), 'rocky')

    expect(screen.getByRole('listitem')).toHaveTextContent('Rocky Run Shelter')
  })

  it('shows where along the trail each match is', async () => {
    const user = userEvent.setup()
    render(<Search {...PROPS} />)

    await user.type(screen.getByRole('searchbox'), 'rocky')

    expect(screen.getByRole('listitem')).toHaveTextContent('1,043.2')
  })

  it('explains on an empty result that the place may lie outside what was downloaded', async () => {
    const user = userEvent.setup()
    render(<Search {...PROPS} />)

    await user.type(screen.getByRole('searchbox'), 'katahdin')

    expect(screen.getByText(/outside/i)).toHaveTextContent(/download/i)
  })

  it('never suggests going online to find more - there is no network path', async () => {
    const user = userEvent.setup()
    render(<Search {...PROPS} />)

    await user.type(screen.getByRole('searchbox'), 'katahdin')

    expect(screen.queryByText(/try again online|check your connection|go online/i)).toBe(
      null,
    )
  })

  it('makes no network request while searching', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const user = userEvent.setup()
    render(<Search {...PROPS} />)

    await user.type(screen.getByRole('searchbox'), 'rocky')

    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('reports the chosen place', async () => {
    const user = userEvent.setup()
    render(<Search {...PROPS} />)

    await user.type(screen.getByRole('searchbox'), 'rocky')
    await user.click(screen.getByRole('button', { name: /Rocky Run Shelter/i }))

    expect(PROPS.onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: '1' }))
  })

  it('closes when dismissed, handing the header back', async () => {
    const user = userEvent.setup()
    render(<Search {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /close|cancel/i }))

    expect(PROPS.onClose).toHaveBeenCalledTimes(1)
  })
})

describe('getting out of it (#315)', () => {
  it('closes on Escape from the search box', () => {
    // The panel covers the map opaquely and Cancel was the only way out. With
    // nothing downloaded it is a blank page over the map, which is the state
    // where "how do I get back" is a real question.
    const onClose = vi.fn()
    render(<Search open pois={[]} onSelect={vi.fn()} onClose={onClose} />)

    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Escape' })

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on Escape from the results, not just the box', () => {
    // Somebody scrolling results has moved focus off the input. Binding this
    // to the input alone would leave Escape dead in exactly that state.
    const onClose = vi.fn()
    render(
      <Search
        open
        pois={[{ id: 'a', name: 'Annapolis Rock', type: 'viewpoint' }]}
        onSelect={vi.fn()}
        onClose={onClose}
      />,
    )
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'annapolis' } })

    fireEvent.keyDown(screen.getByRole('button', { name: /annapolis rock/i }), {
      key: 'Escape',
    })

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('leaves other keys alone', () => {
    const onClose = vi.fn()
    render(<Search open pois={[]} onSelect={vi.fn()} onClose={onClose} />)

    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'Enter' })
    fireEvent.keyDown(screen.getByRole('searchbox'), { key: 'a' })

    expect(onClose).not.toHaveBeenCalled()
  })
})

// --- The places index under the waypoints (#1373, frame 14d) ---------------

const PLACES = [
  {
    id: 'p1',
    name: 'Harriman State Park',
    kind: 'park' as const,
    category: 'State Park',
    state: 'NY',
    lon: -74.1,
    lat: 41.25,
    bbox: [-74.2, 41.2, -74.0, 41.3] as const,
  },
  {
    id: 't1',
    name: 'Reeves Meadow',
    kind: 'trailhead' as const,
    within: 'Harriman State Park',
    lon: -74.16,
    lat: 41.2,
    poiId: 'atc:reeves',
  },
]

describe('Search, over the places index', () => {
  it('lists places under the waypoints, named for what they are', async () => {
    const user = userEvent.setup()
    const onSelectPlace = vi.fn()
    render(<Search {...PROPS} places={PLACES} onSelectPlace={onSelectPlace} />)

    await user.type(screen.getByRole('searchbox'), 'harr')

    // Its own list, under its own heading - a waypoint opens a card and a
    // place moves the map, so the seam has to be readable.
    const places = screen.getByRole('list', { name: 'Places' })
    expect(screen.getByRole('heading', { name: 'Places' })).toBeInTheDocument()
    expect(
      within(places).getByRole('button', { name: /Harriman State Park, NY/ }),
    ).toHaveTextContent('State Park')
    expect(screen.queryByRole('list', { name: 'Waypoints' })).toBeNull()
  })

  it('names the park a trailhead sits in', async () => {
    const user = userEvent.setup()
    render(<Search {...PROPS} places={PLACES} onSelectPlace={vi.fn()} />)

    await user.type(screen.getByRole('searchbox'), 'reeves')

    expect(screen.getByRole('button', { name: /Reeves Meadow/ })).toHaveTextContent(
      'trailhead · Harriman State Park',
    )
  })

  it('reports the chosen place, with everything the map needs to go there', async () => {
    const user = userEvent.setup()
    const onSelectPlace = vi.fn()
    render(<Search {...PROPS} places={PLACES} onSelectPlace={onSelectPlace} />)

    await user.type(screen.getByRole('searchbox'), 'harr')
    await user.click(screen.getByRole('button', { name: /Harriman State Park/ }))

    expect(onSelectPlace).toHaveBeenCalledWith(PLACES[0])
    expect(PROPS.onSelect).not.toHaveBeenCalled()
  })

  it('keeps the empty sentence for when both lists are empty', async () => {
    const user = userEvent.setup()
    render(<Search {...PROPS} places={PLACES} onSelectPlace={vi.fn()} />)

    await user.type(screen.getByRole('searchbox'), 'harr')
    expect(screen.queryByText(/Nothing here by that name/)).toBeNull()

    await user.clear(screen.getByRole('searchbox'))
    await user.type(screen.getByRole('searchbox'), 'zzz')
    expect(screen.getByText(/Nothing here by that name/)).toBeInTheDocument()
  })

  it('offers nothing extra on a phone with no index, and says so in the placeholder', async () => {
    // D10: a placeholder naming parks on a phone that cannot find one is a
    // refusal dressed as a door.
    const user = userEvent.setup()
    render(<Search {...PROPS} />)

    expect(screen.getByRole('searchbox')).toHaveAttribute(
      'placeholder',
      'Search shelters, water, towns',
    )
    await user.type(screen.getByRole('searchbox'), 'harr')
    expect(screen.queryByRole('heading', { name: 'Places' })).toBeNull()
    expect(screen.getByText(/Nothing here by that name/)).toBeInTheDocument()
  })

  it('names parks in the placeholder once there is an index to search', () => {
    render(<Search {...PROPS} places={PLACES} onSelectPlace={vi.fn()} />)
    expect(screen.getByRole('searchbox')).toHaveAttribute(
      'placeholder',
      'Search shelters, water, parks, towns',
    )
  })
})
