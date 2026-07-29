import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
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
