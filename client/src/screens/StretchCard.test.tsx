import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StretchCard, STRETCH_TITLE, type StretchOffer } from './StretchCard'

// Just the stretch a hiker is walking (#558). What is under test is the
// shape the per-section list was retired for NOT having (WIREFRAMES.md §4):
// no rows to pick, a price that is the price of what is missing, the whole
// trail left as the decision above it, and a sentence for every state so the
// card never reads as a feature that is not there.

function offer(overrides: Partial<StretchOffer> = {}): StretchOffer {
  return {
    hike: 'Northbound · mi 8.5 – 79.2',
    available: true,
    pieces: 3,
    missing: 3,
    bytes: 21_841_273,
    marginKm: 3,
    units: 'imperial',
    status: { state: 'not-downloaded' },
    wholeSheetHere: false,
    onTake: vi.fn(),
    onResume: vi.fn(),
    onRemove: vi.fn(),
    ...overrides,
  }
}

afterEach(() => {
  cleanup()
})

describe('StretchCard', () => {
  it('offers the stretch under the hike, priced, with one button and no rows', async () => {
    const user = userEvent.setup()
    const stretch = offer()
    render(<StretchCard stretch={stretch} />)

    const card = screen.getByRole('region', { name: STRETCH_TITLE })
    expect(card).toHaveTextContent(/Northbound · mi 8\.5 – 79\.2 · 3 pieces/)
    expect(card).toHaveTextContent(/About 21\.8 MB/)
    // Derived, never enumerated: nothing here is a list of stretches to
    // choose from.
    expect(screen.queryAllByRole('radio')).toHaveLength(0)
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: /take this stretch/i }))
    expect(stretch.onTake).toHaveBeenCalledTimes(1)
  })

  it('prices only what is missing when some pieces are already here', () => {
    render(<StretchCard stretch={offer({ missing: 1, bytes: 7_000_000 })} />)

    expect(
      screen.getByText(/About 7 MB for the 1 piece not here yet/),
    ).toBeInTheDocument()
  })

  it('withholds the price rather than guessing when the manifest has not priced it', () => {
    render(<StretchCard stretch={offer({ bytes: null })} />)

    expect(screen.getByText(/size not known yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/about [\d.]+ [MG]B/i)).toBeNull()
    // Still offered: an unpriced stretch is a stretch, and the manifest is
    // the thing that is late, not the download.
    expect(screen.getByRole('button', { name: /take this stretch/i })).toBeInTheDocument()
  })

  it('says how far past its edge a piece reaches, in the hiker’s own units', () => {
    // The index states the margin in kilometres; the card states it the way
    // the hiker reads every other distance (lib/units.ts). 2.5 km is 1.55
    // miles, rounded to the tenth the formatter keeps.
    render(<StretchCard stretch={offer({ marginKm: 2.5 })} />)

    expect(screen.getByText(/about 1\.6 mi past its own edge/i)).toBeInTheDocument()
  })

  it('states the margin in kilometres for a metric hiker', () => {
    render(<StretchCard stretch={offer({ units: 'metric' })} />)

    expect(screen.getByText(/about 3(\.0)? km past its own edge/i)).toBeInTheDocument()
  })

  it('points at the hike setting when there is no hike, and offers nothing', () => {
    render(<StretchCard stretch={offer({ hike: null })} />)

    expect(screen.getByText(/set the hike you’re on/i)).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('says the pieces list has not arrived, and that the whole trail is still one tap', () => {
    render(<StretchCard stretch={offer({ available: false })} />)

    expect(screen.getByText(/hasn’t reached this phone yet/i)).toBeInTheDocument()
    expect(screen.getByText(/whole trail above is still one tap/i)).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('stands down when the whole trail is on the phone', () => {
    // The A.T. is the union of its cells (OFFLINE_COVERAGE.md §5): a phone
    // holding the sheet holds every stretch, and offering one would be
    // asking for bytes it already has.
    render(<StretchCard stretch={offer({ wholeSheetHere: true })} />)

    expect(screen.getByText(/whole trail is on this phone/i)).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('says a hike off the cut has no pieces, rather than offering zero of them', () => {
    render(<StretchCard stretch={offer({ pieces: 0, missing: 0, bytes: 0 })} />)

    expect(
      screen.getByText(/crosses no ground the pieces cover yet/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('shows the transfer while pieces arrive', () => {
    render(
      <StretchCard
        stretch={offer({
          status: {
            state: 'downloading',
            receivedBytes: 5_000_000,
            totalBytes: 21_841_273,
          },
        })}
      />,
    )

    expect(
      screen.getByRole('progressbar', { name: /stretch download/i }),
    ).toHaveAttribute('aria-valuenow', '23')
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('offers to resume a stretch that stopped, keeping what arrived', async () => {
    const user = userEvent.setup()
    const stretch = offer({
      missing: 2,
      status: { state: 'failed', receivedBytes: 9_131_273, totalBytes: 21_841_273 },
    })
    render(<StretchCard stretch={stretch} />)

    expect(screen.getByText(/1 piece of 3 here/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /resume the stretch/i }))
    expect(stretch.onResume).toHaveBeenCalledTimes(1)
  })

  it('asks twice before removing a stretch, and removes on the second', async () => {
    const user = userEvent.setup()
    const stretch = offer({
      missing: 0,
      status: { state: 'downloaded', totalBytes: 21_841_273, completedAt: new Date() },
    })
    render(<StretchCard stretch={stretch} />)

    expect(screen.getByText(/3 pieces on this phone/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /remove the stretch/i }))
    expect(stretch.onRemove).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /keep them/i }))
    expect(stretch.onRemove).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: /remove the stretch/i }))
    await user.click(screen.getByRole('button', { name: /yes, remove them/i }))
    expect(stretch.onRemove).toHaveBeenCalledTimes(1)
  })

  it('offers a fresh copy after an eviction, saying what happened', () => {
    render(
      <StretchCard
        stretch={offer({ status: { state: 'evicted', completedAt: null } })}
      />,
    )

    expect(screen.getByText(/phone removed them/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /take it again/i })).toBeInTheDocument()
  })

  it('never describes the edge of coverage as damage', () => {
    // The card's own sentences about where the map stops are held to the
    // same rule the status strip is (#352, #557).
    render(<StretchCard stretch={offer()} />)

    expect(screen.getByRole('region', { name: STRETCH_TITLE }).textContent).not.toMatch(
      /damaged|corrupt|incomplete/i,
    )
  })
})
