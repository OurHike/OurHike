import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Downloads, type SheetDownload } from './Downloads'
import { hikingDetailOptions, rasterDetailOptions } from './DetailPicker'

// WIREFRAMES.md §4 as amended by its own Known Deviations #1: the wireframe
// drew a per-section list, and ROADMAP.md Phase 2 had already decided on ONE
// whole-corridor package. This screen builds to the roadmap, so several tests
// here assert the ABSENCE of the retired model - a section list, per-section
// overrides, roll-up totals, mixed-detail seams. Absence tests are the only
// way a superseded design stays superseded.
//
// What #237 made plural is the SHEET, and only the sheet: the hiking sheet
// everyone gets, and the USGS raster a hiker opts into. Each sheet is still
// one download with one state and one button - which archives it takes is
// storage, not a choice (lib/packages.ts), and the archives are combined
// before they reach this screen (lib/backgroundStatus.ts).
//
// The card's own states live in DownloadCard.test.tsx.
//
// Since #298 the sheets are TABBED rather than stacked, so most of what
// follows names the sheet it is about and opens that tab first. That is the
// behaviour under test as much as the assertion after it: a hiker comparing
// two maps sees one of them at a time, with the other a tap away.

/** Opens a sheet's tab, the way a hiker reaches the card behind it. */
async function openTab(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
  await user.click(screen.getByRole('tab', { name }))
}

function sheet(overrides: Partial<SheetDownload> = {}): SheetDownload {
  return {
    id: 'usgs-sheet',
    title: 'USGS sheet',
    summary: 'The official government topo, as an optional second map.',
    status: { state: 'not-downloaded' as const },
    sizeBytes: 314_000_000,
    detail: {
      options: rasterDetailOptions(),
      value: 'standard',
      onChange: vi.fn(),
      name: 'usgs-detail',
    },
    onStart: vi.fn(),
    onResume: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  }
}

/** The two-sheet world: the hiking sheet first with its own two-level
 *  picker (#276), the USGS raster second with the tier picker. */
function twoSheets(): [SheetDownload, SheetDownload] {
  return [
    sheet({
      id: 'hiking-sheet',
      title: 'Hiking sheet',
      summary: 'The map you are looking at - cartography and terrain, offline.',
      sizeBytes: 1_160_000_000,
      detail: {
        options: hikingDetailOptions(),
        value: 'standard',
        onChange: vi.fn(),
        name: 'hiking-detail',
      },
    }),
    sheet(),
  ]
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Downloads', () => {
  it('offers whole-trail downloads, not a list of sections', () => {
    render(<Downloads sheets={[sheet()]} />)

    expect(
      screen.getByText(/whole trail|entire trail|whole corridor/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/section/i)).not.toBeInTheDocument()
  })

  it('offers one button per sheet, never one per archive underneath', async () => {
    // The DEM and the vector basemap are pieces of the hiking sheet. A hiker
    // who had to tick archives off could get it wrong, and being wrong means
    // no terrain on a ridge. One button on the sheet's own tab, and exactly
    // one - a tab shows a sheet, not its archives.
    const user = userEvent.setup()
    render(<Downloads sheets={twoSheets()} />)

    expect(screen.getAllByRole('button', { name: /download the map/i })).toHaveLength(1)

    await openTab(user, /usgs sheet/i)

    expect(screen.getAllByRole('button', { name: /download the map/i })).toHaveLength(1)
  })

  it('never shows roll-up totals or mixed-detail seam messaging', () => {
    render(<Downloads sheets={twoSheets()} />)

    expect(screen.queryByText(/remaining|seam|mixed detail/i)).toBe(null)
  })

  it('offers exactly the three detail levels with their real measured sizes', () => {
    render(<Downloads sheets={[sheet()]} />)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
    // Sizes from rasterDetailOptions() - downloadDetail.ts's measured figures.
    expect(screen.getByText(/65 MB/)).toBeInTheDocument()
    expect(screen.getByText(/315\.1 MB/)).toBeInTheDocument()
    expect(screen.getByText(/1\.18 GB/)).toBeInTheDocument()
  })

  it('reports a detail change rather than silently re-downloading', async () => {
    const user = userEvent.setup()
    const usgs = sheet()
    render(<Downloads sheets={[usgs]} />)

    await user.click(screen.getByRole('radio', { name: /fine/i }))

    expect(usgs.detail?.onChange).toHaveBeenCalledWith('fine')
    expect(usgs.onStart).not.toHaveBeenCalled()
  })

  it('starts the download when asked', async () => {
    const user = userEvent.setup()
    const usgs = sheet()
    render(<Downloads sheets={[usgs]} />)

    await user.click(screen.getByRole('button', { name: /download/i }))

    expect(usgs.onStart).toHaveBeenCalledTimes(1)
  })

  it('resumes rather than restarts when part of it is already here', async () => {
    const user = userEvent.setup()
    const usgs = sheet({
      status: { state: 'failed', receivedBytes: 280_000_000, totalBytes: 314_000_000 },
    })
    render(<Downloads sheets={[usgs]} />)

    expect(screen.queryByRole('button', { name: /restart|start over/i })).toBe(null)
    await user.click(screen.getByRole('button', { name: /resume/i }))

    expect(usgs.onResume).toHaveBeenCalledTimes(1)
  })

  it('deletes a whole sheet, after asking twice', async () => {
    const user = userEvent.setup()
    const usgs = sheet({
      status: {
        state: 'downloaded',
        totalBytes: 314_000_000,
        completedAt: new Date('2026-07-26T12:00:00Z'),
      },
    })
    render(<Downloads sheets={[usgs]} />)

    // The first tap arms, the second destroys - a mis-tap on a phone must
    // never be enough to delete a map that needs signal to restore.
    await user.click(screen.getByRole('button', { name: /delete the map/i }))
    expect(usgs.onDelete).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /yes, delete it/i }))

    expect(usgs.onDelete).toHaveBeenCalledTimes(1)
  })

  it('reports a sheet’s failure', () => {
    // The fixture is the shape lib/archiveDownload.ts actually throws now -
    // a hiker sentence with the status in parentheses, never leading.
    const failure = 'The server could not send the map (it answered 404).'
    render(<Downloads sheets={[sheet({ error: failure })]} />)

    expect(screen.getByRole('alert')).toHaveTextContent(failure)
  })

  it('does not list the trail’s own data as something to download', () => {
    // The centerline, spurs, POIs and elevation profile are fetched by
    // default wherever they are missing (lib/trailData.ts). Offering them
    // here would present a decision that has already been made, and imply
    // the map could be had without them.
    render(<Downloads sheets={twoSheets()} />)

    expect(screen.queryByText(/centerline|points of interest|trail data/i)).toBe(null)
  })
})

// --- Two sheets, two decisions (#237) --------------------------------------

describe('the USGS sheet as its own decision (#237)', () => {
  it('names every sheet on the strip, so the choice is visible before it is made', () => {
    render(<Downloads sheets={twoSheets()} />)

    expect(screen.getByRole('tab', { name: /hiking sheet/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /usgs sheet/i })).toBeInTheDocument()
  })

  it('opens on the default background, not on the optional gigabyte', () => {
    // BACKGROUND_SHEETS is ordered default-first (lib/packages.ts). Opening
    // on the USGS raster would put the map nobody has to take in front of
    // the one everybody navigates by.
    render(<Downloads sheets={twoSheets()} />)

    expect(screen.getByRole('tab', { name: /hiking sheet/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('region', { name: /hiking sheet/i })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /usgs sheet/i })).toBe(null)
  })

  it('shows the sheet whose tab was tapped, and only that one', async () => {
    const user = userEvent.setup()
    render(<Downloads sheets={twoSheets()} />)

    await openTab(user, /usgs sheet/i)

    expect(screen.getByRole('region', { name: /usgs sheet/i })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /hiking sheet/i })).toBe(null)
  })

  it('draws no tab strip when one sheet is all there is to choose between', () => {
    // A strip of one is a heading pretending to be a control, and the scope
    // paragraph has already named the download.
    render(<Downloads sheets={[sheet()]} />)

    expect(screen.queryByRole('tab')).toBe(null)
    expect(screen.queryByRole('heading', { name: /usgs sheet/i })).toBe(null)
    expect(screen.getByRole('region', { name: /usgs sheet/i })).toBeInTheDocument()
  })

  it('gives each sheet its own buttons, wired to its own handlers', async () => {
    const user = userEvent.setup()
    const [hiking, usgs] = twoSheets()
    render(<Downloads sheets={[hiking, usgs]} />)

    const hikingCard = screen.getByRole('region', { name: /hiking sheet/i })
    await user.click(within(hikingCard).getByRole('button', { name: /download/i }))

    expect(hiking.onStart).toHaveBeenCalledTimes(1)
    expect(usgs.onStart).not.toHaveBeenCalled()
  })

  it('gives each sheet its own picker, with its own level set (#276)', async () => {
    // The USGS raster has Light/Standard/Fine; the hiking sheet has its z13
    // Standard cut and z14 Fine one. Distinct radio-group names keep one
    // card's choice from toggling the other's.
    const user = userEvent.setup()
    render(<Downloads sheets={twoSheets()} />)

    // Read as strings before switching: React reuses the input elements
    // between panels, so a held reference reports the new panel's name.
    const hikingGroup = (screen.getAllByRole('radio')[0] as HTMLInputElement).name
    await openTab(user, /usgs sheet/i)
    const usgsGroup = (screen.getAllByRole('radio')[0] as HTMLInputElement).name

    expect(hikingGroup).toBe('hiking-detail')
    expect(usgsGroup).toBe('usgs-detail')
  })

  it('draws the same three rungs under either tab, greyed where the sheet has none (#298)', async () => {
    // Two level sets meant two differently-shaped pickers, and switching
    // tabs made the cheapest row disappear. Same ladder under both now:
    // what differs is what each rung costs, not whether it was asked.
    const user = userEvent.setup()
    render(<Downloads sheets={twoSheets()} />)

    expect(screen.getAllByRole('radio')).toHaveLength(3)
    expect(screen.getByRole('radio', { name: /light/i })).toBeDisabled()
    expect(screen.getByRole('radio', { name: /standard/i })).toBeEnabled()

    await openTab(user, /usgs sheet/i)

    const usgsLevels = screen.getAllByRole('radio')
    expect(usgsLevels).toHaveLength(3)
    for (const level of usgsLevels) expect(level).toBeEnabled()
  })

  it('keeps one sheet’s failure off the other’s card', async () => {
    const user = userEvent.setup()
    const [hiking, usgs] = twoSheets()
    render(
      <Downloads
        sheets={[
          hiking,
          { ...usgs, error: 'The server could not send the map (it answered 404).' },
        ]}
      />,
    )

    expect(screen.queryByRole('alert')).toBe(null)

    await openTab(user, /usgs sheet/i)

    expect(screen.getByRole('alert')).toHaveTextContent('404')
  })

  it('deleting one sheet never touches the other', async () => {
    // #237's acceptance line: a hiker can drop the USGS sheet without
    // touching the background they navigate by.
    const user = userEvent.setup()
    const [hiking, usgs] = twoSheets()
    const downloadedUsgs = {
      ...usgs,
      status: {
        state: 'downloaded' as const,
        totalBytes: 314_000_000,
        completedAt: new Date('2026-07-26T12:00:00Z'),
      },
    }
    render(<Downloads sheets={[hiking, downloadedUsgs]} />)
    await openTab(user, /usgs sheet/i)

    const usgsCard = screen.getByRole('region', { name: /usgs sheet/i })
    await user.click(within(usgsCard).getByRole('button', { name: /delete the map/i }))
    await user.click(within(usgsCard).getByRole('button', { name: /yes, delete it/i }))

    expect(downloadedUsgs.onDelete).toHaveBeenCalledTimes(1)
    expect(hiking.onDelete).not.toHaveBeenCalled()
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

    render(<Downloads sheets={[sheet()]} />)

    expect(screen.getByText(/phone you.ll actually be carrying/i)).toBeInTheDocument()
  })

  it('still offers the download itself', () => {
    // A laptop is a legitimate place to look at the map, and someone may well
    // be on a cabin connection. The reason is reframed; the capability is not
    // taken away.
    atWidth(true)

    render(<Downloads sheets={[sheet()]} />)

    expect(screen.getByRole('button', { name: /download the map/i })).toBeInTheDocument()
  })

  it('keeps the phone wording on a phone', () => {
    atWidth(false)

    render(<Downloads sheets={[sheet()]} />)

    expect(screen.getByText(/works with no signal/i)).toBeInTheDocument()
  })
})

describe('room for the download (#190)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function stubEstimate(quota: number, usage: number) {
    // Returns the promise the component will await, so an absence assertion
    // can wait on the estimate itself having landed (#323) - the observable
    // that proves the sequence completed, where the 20 ms real-clock sleep
    // this replaces passed on a broken implementation exactly as readily.
    const estimate = Promise.resolve({ quota, usage })
    vi.stubGlobal('navigator', {
      ...globalThis.navigator,
      storage: { estimate: () => estimate },
    })
    return estimate
  }

  it('warns before starting when the chosen tier may not fit', async () => {
    // Standard is 314 MB; leave ~100 MB free.
    stubEstimate(1_000_000_000, 900_000_000)

    render(<Downloads sheets={[sheet()]} />)

    expect(await screen.findByRole('status')).toHaveTextContent(/may not fit/i)
    // Warned, never refused: the button is still there.
    expect(screen.getByRole('button', { name: /download the map/i })).toBeInTheDocument()
  })

  it('measures the room against the WHOLE sheet, not one archive of it', async () => {
    // 600 MB free against a sheet whose archives come to 794 MB. Each piece
    // would fit on its own, and one tap brings all of them - so a warning
    // weighed against a single archive would never fire, and the download
    // would run out of room partway with nothing having said so.
    stubEstimate(1_000_000_000, 400_000_000)

    render(<Downloads sheets={[sheet({ sizeBytes: 794_000_000 })]} />)

    expect(await screen.findByRole('status')).toHaveTextContent('794 MB')
  })

  it('warns per sheet, against that sheet’s own size', async () => {
    // 600 MB free: the 314 MB USGS tier fits, the 1.16 GB hiking sheet does
    // not. One warning, under the sheet it is true of.
    stubEstimate(1_000_000_000, 400_000_000)

    render(<Downloads sheets={twoSheets()} />)

    const warnings = await screen.findAllByRole('status')
    expect(warnings).toHaveLength(1)
    expect(warnings[0]).toHaveTextContent('1.16 GB')
  })

  it('stays quiet when there is room', async () => {
    const estimated = stubEstimate(10_000_000_000, 1_000_000_000)

    render(<Downloads sheets={[sheet()]} />)

    // Once the estimate the component awaited has resolved and act has
    // flushed the resulting state, an absent warning is evidence rather
    // than a race won (#323).
    await act(async () => {
      await estimated
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('stays quiet where the browser will not say', () => {
    render(<Downloads sheets={[sheet()]} />)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('says the eviction wording when the phone was the one that removed it', async () => {
    stubEstimate(1_000_000_000, 900_000_000)

    render(
      <Downloads sheets={[sheet({ status: { state: 'evicted', completedAt: null } })]} />,
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      /space still looks tight/i,
    )
  })

  it('warns after a refused download too, which restarts from zero (#238)', async () => {
    // A hash mismatch kept nothing, so the next tap fetches the whole size
    // again - exactly when a full disk is worth knowing about.
    stubEstimate(1_000_000_000, 900_000_000)

    render(<Downloads sheets={[sheet({ status: { state: 'hash-mismatch' } })]} />)

    expect(await screen.findByRole('status')).toHaveTextContent(/may not fit/i)
  })

  it('stays quiet once it is on the phone', async () => {
    const estimated = stubEstimate(1_000_000_000, 900_000_000)

    render(
      <Downloads
        sheets={[
          sheet({
            status: {
              state: 'downloaded',
              totalBytes: 314_000_000,
              completedAt: new Date('2026-08-01T08:00:00Z'),
            },
          }),
        ]}
      />,
    )

    await act(async () => {
      await estimated
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
