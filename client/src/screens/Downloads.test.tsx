import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Downloads } from './Downloads'

// WIREFRAMES.md §4 as amended by its own Known Deviations #1: the wireframe
// drew a per-section list, and ROADMAP.md Phase 2 had already decided on ONE
// whole-corridor package. This screen builds to the roadmap, so several tests
// here assert the ABSENCE of the retired model - a section list, per-section
// overrides, roll-up totals, mixed-detail seams. Absence tests are the only
// way a superseded design stays superseded.
//
// WIREFRAMES.md `7a` also requires a failed download to RESUME rather than
// restart: re-fetching 314 MB from the start because a transfer dropped at
// 90% is exactly the failure someone on trailhead wifi cannot afford.

const PROPS = {
  status: { state: 'not-downloaded' as const },
  detailLevel: 'standard' as const,
  onChangeDetail: vi.fn(),
  onStart: vi.fn(),
  onResume: vi.fn(),
  onDelete: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Downloads', () => {
  it('offers a single whole-corridor package, not a list of sections', () => {
    render(<Downloads {...PROPS} />)

    expect(
      screen.getByText(/whole trail|entire trail|whole corridor/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/section/i)).not.toBeInTheDocument()
  })

  it('offers exactly the three detail levels with their real measured sizes', () => {
    render(<Downloads {...PROPS} />)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
    expect(screen.getByText(/64 MB/)).toBeInTheDocument()
    expect(screen.getByText(/314 MB/)).toBeInTheDocument()
    expect(screen.getByText(/1\.18 GB/)).toBeInTheDocument()
  })

  it('marks Standard as recommended', () => {
    render(<Downloads {...PROPS} />)

    expect(screen.getByRole('radio', { name: /standard/i })).toBeChecked()
    expect(screen.getByText(/recommended/i)).toBeInTheDocument()
  })

  it('reports a detail change rather than silently re-downloading', async () => {
    const user = userEvent.setup()
    render(<Downloads {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /fine/i }))

    expect(PROPS.onChangeDetail).toHaveBeenCalledWith('fine')
    expect(PROPS.onStart).not.toHaveBeenCalled()
  })

  it('starts the download when asked', async () => {
    const user = userEvent.setup()
    render(<Downloads {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /download/i }))

    expect(PROPS.onStart).toHaveBeenCalledTimes(1)
  })

  it('shows how far along a download is', () => {
    render(
      <Downloads
        {...PROPS}
        status={{
          state: 'downloading',
          receivedBytes: 157_000_000,
          totalBytes: 314_000_000,
        }}
      />,
    )

    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50')
  })

  it('states progress in bytes too, so the number means something concrete', () => {
    render(
      <Downloads
        {...PROPS}
        status={{
          state: 'downloading',
          receivedBytes: 157_000_000,
          totalBytes: 314_000_000,
        }}
      />,
    )

    // The received figure lives in its own width-reserving span, so the line
    // is asserted as the reader sees it: the paragraph's whole text.
    expect(screen.getByText(/of 314 MB/)).toHaveTextContent('157 MB of 314 MB')
  })

  it('counts whole megabytes, so the ticking figure has no decimal to spin', () => {
    // The counter re-renders on every chunk. With formatBytes it flickered:
    // the tenths digit spun unreadably, and trimming "10.0" to "10" changed
    // the string's width so the line jumped.
    render(
      <Downloads
        {...PROPS}
        status={{
          state: 'downloading',
          receivedBytes: 157_650_000,
          totalBytes: 314_000_000,
        }}
      />,
    )

    expect(screen.getByText('157 MB')).toBeInTheDocument()
    expect(screen.queryByText(/157\.\d/)).toBe(null)
  })

  it('reserves the counter its full width, sized to the total', () => {
    // "9 MB" growing to "10 MB" must not shuffle "of 314 MB" sideways: the
    // received figure sits right-aligned in a slot as wide as the total will
    // ever make it - ch units, exact because the byte line is monospace.
    render(
      <Downloads
        {...PROPS}
        status={{
          state: 'downloading',
          receivedBytes: 9_000_000,
          totalBytes: 314_000_000,
        }}
      />,
    )

    expect(screen.getByText('9 MB')).toHaveStyle({ minWidth: '6ch' })
  })

  it('offers to RESUME a failed download, never to restart it', async () => {
    const user = userEvent.setup()
    render(
      <Downloads
        {...PROPS}
        status={{ state: 'failed', receivedBytes: 280_000_000, totalBytes: 314_000_000 }}
      />,
    )

    expect(screen.queryByRole('button', { name: /restart|start over/i })).toBe(null)
    await user.click(screen.getByRole('button', { name: /resume/i }))

    expect(PROPS.onResume).toHaveBeenCalledTimes(1)
  })

  it('says how much is already on the phone when a download failed partway', () => {
    render(
      <Downloads
        {...PROPS}
        status={{ state: 'failed', receivedBytes: 280_000_000, totalBytes: 314_000_000 }}
      />,
    )

    expect(screen.getByText(/280 MB/)).toBeInTheDocument()
  })

  it('shows the downloaded state with what is stored and when', () => {
    render(
      <Downloads
        {...PROPS}
        status={{
          state: 'downloaded',
          totalBytes: 314_000_000,
          completedAt: new Date('2026-07-26T12:00:00Z'),
        }}
      />,
    )

    expect(screen.getByText(/314 MB/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
  })

  it('never shows roll-up totals or mixed-detail seam messaging', () => {
    render(<Downloads {...PROPS} />)

    expect(screen.queryByText(/remaining|seam|mixed detail/i)).toBe(null)
  })

  it('shows 0% rather than NaN% before the total size is known', () => {
    // The first progress callback can land before content-length has been
    // read, and "NaN%" on a progress bar reads as a broken app.
    render(
      <Downloads
        {...PROPS}
        status={{ state: 'downloading', receivedBytes: 0, totalBytes: 0 }}
      />,
    )

    expect(
      screen.getByRole('progressbar', { name: /download progress/i }),
    ).toHaveAttribute('aria-valuenow', '0')
  })
})

// --- On a machine that is not going up a mountain --------------------------

describe('downloads on a desktop', () => {
  function atWidth(isDesktop: boolean) {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: isDesktop,
        addEventListener: () => {},
        removeEventListener: () => {},
      })),
    )
  }

  afterEach(() => vi.unstubAllGlobals())

  it('says what the download is actually for when the browser has signal', () => {
    // "Once it's on your phone, the map works with no signal" is a promise
    // aimed at a phone. On a laptop it is answering a question nobody asked.
    atWidth(true)

    render(<Downloads {...PROPS} />)

    expect(screen.getByText(/phone you.ll actually be carrying/i)).toBeInTheDocument()
  })

  it('still offers the download itself', () => {
    // A laptop is a legitimate place to look at the map, and someone may well
    // be on a cabin connection. The reason is reframed; the capability is not
    // taken away.
    atWidth(true)

    render(<Downloads {...PROPS} />)

    expect(screen.getByRole('button', { name: /download the map/i })).toBeInTheDocument()
  })

  it('keeps the phone wording on a phone', () => {
    atWidth(false)

    render(<Downloads {...PROPS} />)

    expect(screen.getByText(/works with no signal/i)).toBeInTheDocument()
  })
})
