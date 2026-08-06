import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Downloads, type PackageDownload } from './Downloads'
import {
  BASEMAP_PACKAGE,
  CORRIDOR_BACKGROUND_PACKAGE,
  DEM_PACKAGE,
} from '../lib/packages'

// WIREFRAMES.md §4 as amended by its own Known Deviations #1: the wireframe
// drew a per-section list, and ROADMAP.md Phase 2 had already decided on ONE
// whole-corridor package. This screen builds to the roadmap, so several tests
// here assert the ABSENCE of the retired model - a section list, per-section
// overrides, roll-up totals, mixed-detail seams. Absence tests are the only
// way a superseded design stays superseded.
//
// What the screen DOES list since #192 is packages: the pieces one trail's
// map is made of (raster sheet, vector basemap, DEM). That is a different
// axis from sections, and the difference is why it is allowed to be a list -
// sections were a choice a hiker had to get right mile by mile, packages are
// a manifest one tap takes all of.
//
// Each card's own states live in PackageCard.test.tsx.

function entry(overrides: Partial<PackageDownload> = {}): PackageDownload {
  return {
    pkg: CORRIDOR_BACKGROUND_PACKAGE,
    status: { state: 'not-downloaded' },
    sizeBytes: 314_000_000,
    detail: { level: 'standard', onChange: vi.fn() },
    onStart: vi.fn(),
    onResume: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Downloads', () => {
  it('offers whole-trail packages, not a list of sections', () => {
    render(<Downloads packages={[entry()]} />)

    expect(
      screen.getByText(/whole trail|entire trail|whole corridor/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/section/i)).not.toBeInTheDocument()
  })

  it('never shows roll-up totals or mixed-detail seam messaging', () => {
    render(<Downloads packages={[entry()]} />)

    expect(screen.queryByText(/remaining|seam|mixed detail/i)).toBe(null)
  })

  it('starts the download when asked', async () => {
    const user = userEvent.setup()
    const only = entry()
    render(<Downloads packages={[only]} />)

    await user.click(screen.getByRole('button', { name: /download/i }))

    expect(only.onStart).toHaveBeenCalledTimes(1)
  })

  it('renders the detail picker of the package that has tiers', () => {
    render(<Downloads packages={[entry()]} />)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
  })
})

// --- Several packages, reported independently (#192) ------------------------

describe('a trail made of several packages', () => {
  const THREE: PackageDownload[] = [
    entry(),
    entry({
      pkg: BASEMAP_PACKAGE,
      detail: undefined,
      sizeBytes: 200_000_000,
      status: {
        state: 'downloaded',
        totalBytes: 200_000_000,
        completedAt: new Date('2026-08-01T08:00:00Z'),
      },
    }),
    entry({
      pkg: DEM_PACKAGE,
      detail: undefined,
      sizeBytes: 480_000_000,
      status: { state: 'failed', receivedBytes: 100_000_000, totalBytes: 480_000_000 },
    }),
  ]

  it('lists every package the trail is made of', () => {
    render(<Downloads packages={THREE} />)

    for (const { pkg } of THREE) {
      expect(screen.getByRole('region', { name: pkg.title })).toBeInTheDocument()
    }
  })

  it('reports each package’s own state, not one state for all of them', () => {
    render(<Downloads packages={THREE} />)

    const sheet = within(screen.getByRole('region', { name: BASEMAP_PACKAGE.title }))
    const terrain = within(screen.getByRole('region', { name: DEM_PACKAGE.title }))

    // Downloaded: what is stored, and the way to reclaim it.
    expect(sheet.getByRole('button', { name: /delete/i })).toBeInTheDocument()
    // Interrupted: how far it got, and resume rather than restart.
    expect(terrain.getByText(/Stopped at 100 MB of 480 MB/)).toBeInTheDocument()
    expect(terrain.getByRole('button', { name: /resume/i })).toBeInTheDocument()
  })

  it('acts on the package whose button was pressed', async () => {
    const user = userEvent.setup()
    render(<Downloads packages={THREE} />)

    await user.click(
      within(screen.getByRole('region', { name: DEM_PACKAGE.title })).getByRole(
        'button',
        { name: /resume/i },
      ),
    )

    expect(THREE[2].onResume).toHaveBeenCalledTimes(1)
    expect(THREE[0].onStart).not.toHaveBeenCalled()
    expect(THREE[1].onDelete).not.toHaveBeenCalled()
  })

  it('reports a failure against the package it happened to', () => {
    render(
      <Downloads
        packages={[
          entry(),
          entry({
            pkg: DEM_PACKAGE,
            detail: undefined,
            error: 'Archive download failed: 404 Not Found',
          }),
        ]}
      />,
    )

    const terrain = within(screen.getByRole('region', { name: DEM_PACKAGE.title }))
    const sheet = within(
      screen.getByRole('region', { name: CORRIDOR_BACKGROUND_PACKAGE.title }),
    )

    expect(terrain.getByRole('alert')).toHaveTextContent('404 Not Found')
    expect(sheet.queryByRole('alert')).toBe(null)
  })

  it('offers one tap for everything that is missing', async () => {
    const user = userEvent.setup()
    const onStartAll = vi.fn()
    render(<Downloads packages={THREE} onStartAll={onStartAll} />)

    await user.click(screen.getByRole('button', { name: /download everything/i }))

    expect(onStartAll).toHaveBeenCalledTimes(1)
  })

  it('does not offer a whole-trail tap when there is only one package', () => {
    // It would be a second button doing exactly what the card's own button
    // does, one line above it.
    render(<Downloads packages={[entry()]} onStartAll={vi.fn()} />)

    expect(screen.queryByRole('button', { name: /download everything/i })).toBe(null)
  })

  it('does not offer it when everything is already on the phone', () => {
    const downloaded = (pkg: PackageDownload['pkg']): PackageDownload =>
      entry({
        pkg,
        detail: undefined,
        status: {
          state: 'downloaded',
          totalBytes: 1,
          completedAt: new Date('2026-08-01T08:00:00Z'),
        },
      })

    render(
      <Downloads
        packages={[downloaded(CORRIDOR_BACKGROUND_PACKAGE), downloaded(DEM_PACKAGE)]}
        onStartAll={vi.fn()}
      />,
    )

    expect(screen.queryByRole('button', { name: /download everything/i })).toBe(null)
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

    render(<Downloads packages={[entry()]} />)

    expect(screen.getByText(/phone you.ll actually be carrying/i)).toBeInTheDocument()
  })

  it('still offers the download itself', () => {
    // A laptop is a legitimate place to look at the map, and someone may well
    // be on a cabin connection. The reason is reframed; the capability is not
    // taken away.
    atWidth(true)

    render(<Downloads packages={[entry()]} />)

    expect(screen.getByRole('button', { name: /download the map/i })).toBeInTheDocument()
  })

  it('keeps the phone wording on a phone', () => {
    atWidth(false)

    render(<Downloads packages={[entry()]} />)

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

    render(<Downloads packages={[entry()]} />)

    expect(await screen.findByRole('status')).toHaveTextContent(/may not fit/i)
    // Warned, never refused: the button is still there.
    expect(screen.getByRole('button', { name: /download the map/i })).toBeInTheDocument()
  })

  it('stays quiet when there is room', async () => {
    stubEstimate(10_000_000_000, 1_000_000_000)

    render(<Downloads packages={[entry()]} />)

    // The estimate resolves async; give it a beat before asserting absence.
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('stays quiet where the browser will not say', () => {
    render(<Downloads packages={[entry()]} />)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('counts every package still to come, not just the first', async () => {
    // 314 MB + 480 MB against 600 MB free: neither package alone would trip
    // the warning, and a hiker who taps "download everything" would run out
    // of room partway with nothing having said so.
    stubEstimate(1_000_000_000, 400_000_000)

    render(
      <Downloads
        packages={[
          entry(),
          entry({ pkg: DEM_PACKAGE, detail: undefined, sizeBytes: 480_000_000 }),
        ]}
      />,
    )

    expect(await screen.findByRole('status')).toHaveTextContent('794 MB')
  })

  it('leaves out what is already on the phone', async () => {
    // 600 MB free, and the 480 MB package is already stored: only the 314 MB
    // one is still to come, and it fits.
    stubEstimate(1_000_000_000, 400_000_000)

    render(
      <Downloads
        packages={[
          entry(),
          entry({
            pkg: DEM_PACKAGE,
            detail: undefined,
            sizeBytes: 480_000_000,
            status: {
              state: 'downloaded',
              totalBytes: 480_000_000,
              completedAt: new Date('2026-08-01T08:00:00Z'),
            },
          }),
        ]}
      />,
    )

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('leaves out a package whose size nobody has measured', async () => {
    // A null size is not a zero and not a guess. The sizes shown before a
    // download are held to ±0.6% against measured artifacts; an estimate
    // folded into this total would carry the same weight as a measurement.
    stubEstimate(1_000_000_000, 400_000_000)

    render(
      <Downloads
        packages={[
          entry(),
          entry({ pkg: DEM_PACKAGE, detail: undefined, sizeBytes: null }),
        ]}
      />,
    )

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('says the eviction wording when what is missing was removed by the phone', async () => {
    stubEstimate(1_000_000_000, 900_000_000)

    render(
      <Downloads
        packages={[entry({ status: { state: 'evicted', completedAt: null } })]}
      />,
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      /space still looks tight/i,
    )
  })
})
