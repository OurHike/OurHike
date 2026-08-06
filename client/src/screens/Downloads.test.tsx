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

describe('eviction, said plainly (#190)', () => {
  it('says the map was removed by the phone, never "not downloaded"', () => {
    render(
      <Downloads
        {...PROPS}
        status={{ state: 'evicted', completedAt: new Date('2026-07-20T08:00:00Z') }}
      />,
    )

    expect(screen.getByText(/no longer on this phone/i)).toBeInTheDocument()
    expect(screen.getByText(/removed it to free up space/i)).toBeInTheDocument()
    expect(screen.getByText(/July 20/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /download it again/i })).toBeInTheDocument()
  })

  it('still reads honestly when the completion date did not survive', () => {
    render(<Downloads {...PROPS} status={{ state: 'evicted', completedAt: null }} />)

    expect(screen.getByText(/no longer on this phone/i)).toBeInTheDocument()
  })

  it('starts a fresh download from the eviction message', async () => {
    render(<Downloads {...PROPS} status={{ state: 'evicted', completedAt: null }} />)

    await userEvent.click(screen.getByRole('button', { name: /download it again/i }))

    expect(PROPS.onStart).toHaveBeenCalled()
  })
})

describe('durability, at its honest weight (#190)', () => {
  const DOWNLOADED = {
    state: 'downloaded' as const,
    totalBytes: 314_000_000,
    completedAt: new Date('2026-08-01T08:00:00Z'),
  }

  it('says nothing extra when persistence was granted - protected is the expected state', () => {
    render(<Downloads {...PROPS} status={DOWNLOADED} persistence="granted" />)

    expect(screen.queryByText(/reclaimable/i)).not.toBeInTheDocument()
  })

  it('states best-effort storage when the browser declined to protect it', () => {
    render(<Downloads {...PROPS} status={DOWNLOADED} persistence="denied" />)

    expect(screen.getByText(/reclaimable if storage runs very low/i)).toBeInTheDocument()
    expect(screen.getByText(/declined/i)).toBeInTheDocument()
  })

  it('states best-effort storage where the API does not exist, without claiming a denial', () => {
    render(<Downloads {...PROPS} status={DOWNLOADED} persistence="unsupported" />)

    expect(screen.getByText(/reclaimable if storage runs very low/i)).toBeInTheDocument()
    expect(screen.queryByText(/declined/i)).not.toBeInTheDocument()
  })

  it('keeps quiet while the answer has not arrived', () => {
    render(<Downloads {...PROPS} status={DOWNLOADED} persistence={null} />)

    expect(screen.queryByText(/reclaimable/i)).not.toBeInTheDocument()
  })
})

describe('room for the download (#190)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function stubEstimate(quota: number, usage: number) {
    vi.stubGlobal('navigator', {
      ...globalThis.navigator,
      storage: { estimate: () => Promise.resolve({ quota, usage }) },
    })
  }

  it('warns before starting when the chosen tier may not fit', async () => {
    // Standard is 314 MB; leave ~100 MB free.
    stubEstimate(1_000_000_000, 900_000_000)

    render(<Downloads {...PROPS} />)

    expect(await screen.findByRole('status')).toHaveTextContent(/may not fit/i)
    // Warned, never refused: the button is still there.
    expect(screen.getByRole('button', { name: /download the map/i })).toBeInTheDocument()
  })

  it('stays quiet when there is room', async () => {
    stubEstimate(10_000_000_000, 1_000_000_000)

    render(<Downloads {...PROPS} />)

    // The estimate resolves async; give it a beat before asserting absence.
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('stays quiet where the browser will not say', () => {
    render(<Downloads {...PROPS} />)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
