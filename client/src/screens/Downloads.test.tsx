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
// #192 made the background several archives underneath, and the tests below
// assert that this changed NOTHING here: the background is one download with
// one state and one button. Which archives it takes is storage, not a choice
// (lib/packages.ts), and the archives are combined before they reach this
// screen (lib/backgroundStatus.ts).
//
// The card's own states live in DownloadCard.test.tsx.

const PROPS = {
  status: { state: 'not-downloaded' as const },
  title: 'Offline map',
  summary: 'The whole corridor as a map you can read with no signal.',
  sizeBytes: 314_000_000,
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
  it('offers a single whole-corridor download, not a list of sections', () => {
    render(<Downloads {...PROPS} />)

    expect(
      screen.getByText(/whole trail|entire trail|whole corridor/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/section/i)).not.toBeInTheDocument()
  })

  it('offers one button, not one per archive the background is made of', () => {
    // The DEM, the raster sheet and the vector basemap are pieces of one
    // thing. A hiker who had to tick them off could get it wrong, and being
    // wrong means no terrain on a ridge.
    render(<Downloads {...PROPS} />)

    expect(screen.getAllByRole('button', { name: /download/i })).toHaveLength(1)
  })

  it('never shows roll-up totals or mixed-detail seam messaging', () => {
    render(<Downloads {...PROPS} />)

    expect(screen.queryByText(/remaining|seam|mixed detail/i)).toBe(null)
  })

  it('offers exactly the three detail levels with their real measured sizes', () => {
    render(<Downloads {...PROPS} />)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
    expect(screen.getByText(/64 MB/)).toBeInTheDocument()
    expect(screen.getByText(/314 MB/)).toBeInTheDocument()
    expect(screen.getByText(/1\.18 GB/)).toBeInTheDocument()
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

  it('resumes rather than restarts when part of it is already here', async () => {
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

  it('deletes the whole background from one button', async () => {
    const user = userEvent.setup()
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

    await user.click(screen.getByRole('button', { name: /delete/i }))

    expect(PROPS.onDelete).toHaveBeenCalledTimes(1)
  })

  it('reports the background’s failure', () => {
    render(<Downloads {...PROPS} error="Archive download failed: 404 Not Found" />)

    expect(screen.getByRole('alert')).toHaveTextContent('404 Not Found')
  })

  it('does not list the trail’s own data as something to download', () => {
    // The centerline, spurs, POIs and elevation profile are fetched by
    // default wherever they are missing (lib/trailData.ts). Offering them
    // here would present a decision that has already been made, and imply
    // the map could be had without them.
    render(<Downloads {...PROPS} />)

    expect(screen.queryByText(/centerline|points of interest|trail data/i)).toBe(null)
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

  it('measures the room against the WHOLE background, not one archive of it', async () => {
    // 600 MB free against a background whose archives come to 794 MB. Each
    // piece would fit on its own, and one tap brings all of them - so a
    // warning weighed against a single archive would never fire, and the
    // download would run out of room partway with nothing having said so.
    stubEstimate(1_000_000_000, 400_000_000)

    render(<Downloads {...PROPS} sizeBytes={794_000_000} />)

    expect(await screen.findByRole('status')).toHaveTextContent('794 MB')
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

  it('says the eviction wording when the phone was the one that removed it', async () => {
    stubEstimate(1_000_000_000, 900_000_000)

    render(<Downloads {...PROPS} status={{ state: 'evicted', completedAt: null }} />)

    expect(await screen.findByRole('status')).toHaveTextContent(
      /space still looks tight/i,
    )
  })

  it('stays quiet once it is on the phone', async () => {
    stubEstimate(1_000_000_000, 900_000_000)

    render(
      <Downloads
        {...PROPS}
        status={{
          state: 'downloaded',
          totalBytes: 314_000_000,
          completedAt: new Date('2026-08-01T08:00:00Z'),
        }}
      />,
    )

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
