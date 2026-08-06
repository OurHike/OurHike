import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DownloadCard } from './DownloadCard'
import { hikingDetailOptions, rasterDetailOptions } from './DetailPicker'

// One download's card, in every state it can be in. These were the Downloads
// screen's own tests until #192 lifted the body into a card of its own; the
// states, and the reasons each is asserted, are unchanged.
//
// WIREFRAMES.md `7a` requires a failed download to RESUME rather than
// restart: re-fetching 314 MB from the start because a transfer dropped at
// 90% is exactly the failure someone on trailhead wifi cannot afford.

const PROPS = {
  title: 'Offline map',
  status: { state: 'not-downloaded' as const },
  detail: { options: rasterDetailOptions(), value: 'standard', onChange: vi.fn() },
  onStart: vi.fn(),
  onResume: vi.fn(),
  onDelete: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('DownloadCard', () => {
  it('offers exactly the three detail levels with their real measured sizes', () => {
    render(<DownloadCard {...PROPS} />)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
    expect(screen.getByText(/68\.9 MB/)).toBeInTheDocument()
    expect(screen.getByText(/300\.3 MB/)).toBeInTheDocument()
    expect(screen.getByText(/1\.18 GB/)).toBeInTheDocument()
  })

  it('marks Standard as recommended', () => {
    render(<DownloadCard {...PROPS} />)

    expect(screen.getByRole('radio', { name: /standard/i })).toBeChecked()
    expect(screen.getByText(/recommended/i)).toBeInTheDocument()
  })

  it('reports a detail change rather than silently re-downloading', async () => {
    const user = userEvent.setup()
    render(<DownloadCard {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /fine/i }))

    expect(PROPS.detail.onChange).toHaveBeenCalledWith('fine')
    expect(PROPS.onStart).not.toHaveBeenCalled()
  })

  it('greys out a level this sheet has none of, rather than dropping the row (#298)', () => {
    // The hiking sheet is cut at z13 and z14 - there is no Light. Under a
    // tab beside the raster's three, a two-row picker cannot say whether
    // this map has no Light version or whether the app forgot to ask.
    render(
      <DownloadCard
        {...PROPS}
        title="Hiking sheet"
        detail={{ ...PROPS.detail, options: hikingDetailOptions() }}
      />,
    )

    const levels = screen.getAllByRole('radio')
    expect(levels).toHaveLength(3)
    expect(screen.getByRole('radio', { name: /light/i })).toBeDisabled()
    expect(screen.getByRole('radio', { name: /light/i })).not.toBeChecked()
    expect(screen.getByRole('radio', { name: /standard/i })).toBeEnabled()
    expect(screen.getByRole('radio', { name: /fine/i })).toBeEnabled()
    expect(screen.getByText(/not offered/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument()
  })

  it('starts the download when asked', async () => {
    const user = userEvent.setup()
    render(<DownloadCard {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /download/i }))

    expect(PROPS.onStart).toHaveBeenCalledTimes(1)
  })

  it('shows how far along a download is', () => {
    render(
      <DownloadCard
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
      <DownloadCard
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
      <DownloadCard
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
      <DownloadCard
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
      <DownloadCard
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
      <DownloadCard
        {...PROPS}
        status={{ state: 'failed', receivedBytes: 280_000_000, totalBytes: 314_000_000 }}
      />,
    )

    expect(screen.getByText(/280 MB/)).toBeInTheDocument()
  })

  it('shows the downloaded state with what is stored and when', () => {
    render(
      <DownloadCard
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

  it('shows 0% rather than NaN% before the total size is known', () => {
    // The first progress callback can land before content-length has been
    // read, and "NaN%" on a progress bar reads as a broken app.
    render(
      <DownloadCard
        {...PROPS}
        status={{ state: 'downloading', receivedBytes: 0, totalBytes: 0 }}
      />,
    )

    expect(
      screen.getByRole('progressbar', { name: /download progress/i }),
    ).toHaveAttribute('aria-valuenow', '0')
  })
})

describe('naming what a card is about (#192)', () => {
  it('is reachable by the thing it belongs to, so two cards are never confused', () => {
    render(<DownloadCard {...PROPS} title="Terrain" />)

    expect(screen.getByRole('region', { name: 'Terrain' })).toBeInTheDocument()
  })

  it('says the name once, never as a heading of its own (#298)', () => {
    // The tab above the card names the sheet, and where there is no tab the
    // screen's own copy has. A heading here would be the third time.
    render(<DownloadCard {...PROPS} title="Terrain" />)

    expect(screen.queryByRole('heading')).toBe(null)
  })
})

describe('a failure belongs to the download it happened to (#192)', () => {
  it('reports this download’s error in its own card', () => {
    render(<DownloadCard {...PROPS} error="Archive download failed: 404 Not Found" />)

    expect(screen.getByRole('alert')).toHaveTextContent('404 Not Found')
  })

  it('stays quiet when nothing has failed', () => {
    render(<DownloadCard {...PROPS} />)

    expect(screen.queryByRole('alert')).toBe(null)
  })

  it('keeps offering the button the failure was about', () => {
    // "Nothing happened" is the one answer that leaves someone with no idea
    // whether to retry: the reason is stated, and retrying stays one tap.
    render(<DownloadCard {...PROPS} error="Archive download failed: 404 Not Found" />)

    expect(screen.getByRole('button', { name: /download the map/i })).toBeInTheDocument()
  })
})

describe('eviction, said plainly (#190)', () => {
  it('says the map was removed by the phone, never "not downloaded"', () => {
    render(
      <DownloadCard
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
    render(<DownloadCard {...PROPS} status={{ state: 'evicted', completedAt: null }} />)

    expect(screen.getByText(/no longer on this phone/i)).toBeInTheDocument()
  })

  it('starts a fresh download from the eviction message', async () => {
    render(<DownloadCard {...PROPS} status={{ state: 'evicted', completedAt: null }} />)

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
    render(<DownloadCard {...PROPS} status={DOWNLOADED} persistence="granted" />)

    expect(screen.queryByText(/reclaimable/i)).not.toBeInTheDocument()
  })

  it('states best-effort storage when the browser declined to protect it', () => {
    render(<DownloadCard {...PROPS} status={DOWNLOADED} persistence="denied" />)

    expect(screen.getByText(/reclaimable if storage runs very low/i)).toBeInTheDocument()
    expect(screen.getByText(/declined/i)).toBeInTheDocument()
  })

  it('states best-effort storage where the API does not exist, without claiming a denial', () => {
    render(<DownloadCard {...PROPS} status={DOWNLOADED} persistence="unsupported" />)

    expect(screen.getByText(/reclaimable if storage runs very low/i)).toBeInTheDocument()
    expect(screen.queryByText(/declined/i)).not.toBeInTheDocument()
  })

  it('keeps quiet while the answer has not arrived', () => {
    render(<DownloadCard {...PROPS} status={DOWNLOADED} persistence={null} />)

    expect(screen.queryByText(/reclaimable/i)).not.toBeInTheDocument()
  })
})

describe('checking what is already here (#197)', () => {
  const CHECKING = {
    state: 'checking' as const,
    checkedBytes: 120_000_000,
    totalBytes: 314_000_000,
  }

  it('says the phone is checking the part it already has', () => {
    render(<DownloadCard {...PROPS} status={CHECKING} />)

    expect(
      screen.getByText(/checking the part already on this phone/i),
    ).toBeInTheDocument()
  })

  it('says plainly that this part needs no signal', () => {
    // The whole reason this state exists: local work that is slow looks
    // exactly like a stalled transfer, and the two ask for opposite
    // responses from someone standing in a dead spot.
    render(<DownloadCard {...PROPS} status={CHECKING} />)

    expect(screen.getByText(/needs no signal/i)).toBeInTheDocument()
  })

  it('shows how far through it is, under its own label', () => {
    render(<DownloadCard {...PROPS} status={CHECKING} />)
    const bar = screen.getByRole('progressbar', { name: /checking downloaded data/i })

    expect(bar).toHaveAttribute('aria-valuenow', '38')
  })

  it('offers no button - there is nothing for the hiker to do yet', () => {
    render(<DownloadCard {...PROPS} status={CHECKING} />)

    expect(screen.queryByRole('button', { name: /download|resume|delete/i })).toBeNull()
  })
})

describe('a refused download, said plainly (#238)', () => {
  // Unlike every failure above, nothing was kept: the bytes were the right
  // length and the wrong map, so they were discarded before this card ever
  // rendered. The one thing the button must not say is Resume.

  it('says nothing was saved and the existing map is untouched, without hex', () => {
    render(<DownloadCard {...PROPS} status={{ state: 'hash-mismatch' }} />)

    expect(screen.getByText(/none of it was saved/i)).toBeInTheDocument()
    expect(screen.getByText(/already on this phone is untouched/i)).toBeInTheDocument()
    expect(screen.queryByText(/[0-9a-f]{8}/)).toBe(null)
  })

  it('offers to start over, never to resume', async () => {
    const user = userEvent.setup()
    render(<DownloadCard {...PROPS} status={{ state: 'hash-mismatch' }} />)

    expect(screen.queryByRole('button', { name: /resume/i })).toBe(null)
    await user.click(screen.getByRole('button', { name: /start the download over/i }))

    expect(PROPS.onStart).toHaveBeenCalledTimes(1)
    expect(PROPS.onResume).not.toHaveBeenCalled()
  })

  it('keeps the detail picker, since starting over is a fresh choice', () => {
    render(<DownloadCard {...PROPS} status={{ state: 'hash-mismatch' }} />)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
  })

  it('renders no progress figures - there is no partial to describe', () => {
    render(<DownloadCard {...PROPS} status={{ state: 'hash-mismatch' }} />)

    expect(screen.queryByText(/stopped at/i)).toBe(null)
    expect(screen.queryByRole('progressbar')).toBe(null)
  })
})
