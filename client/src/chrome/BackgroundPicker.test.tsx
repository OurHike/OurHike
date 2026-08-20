import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BackgroundPicker } from './BackgroundPicker'
import { BACKGROUND_SOURCES } from '../lib/userPreferences'

// The control that moved the background choice out of Settings and onto the
// map. What matters here is that it is a real form control - two radios in one
// group, keyboard-operable, writing the canonical field - and that it shows
// the CHOICE rather than what happens to be drawn.

afterEach(() => {
  cleanup()
})

describe('BackgroundPicker', () => {
  describe('when the offline background cannot be had (#855)', () => {
    // The USGS sheet is withdrawn, so on a phone that never took it there is
    // one background and nothing to choose. What this asserts is that the
    // control disappears WHOLE - not that it drops to one radio, and not that
    // it keeps its notes.

    it('renders nothing rather than a choice of one', () => {
      const { container } = render(
        <BackgroundPicker
          value="hiking_topo_live"
          onChange={vi.fn()}
          offlineBackgroundAvailable={false}
        />,
      )

      expect(container).toBeEmptyDOMElement()
    })

    it('says nothing about a download that would honour the old choice', () => {
      // The note under the picker reads "Download the map and this setting
      // takes effect", which is exactly the promise the withdrawal broke.
      // Rendering it here would send a hiker to a Downloads window that no
      // longer carries the sheet.
      render(
        <BackgroundPicker
          value="usgs_topo_offline"
          onChange={vi.fn()}
          override="nothing-downloaded"
          offlineBackgroundAvailable={false}
        />,
      )

      expect(screen.queryByText(/nothing is downloaded yet/i)).toBeNull()
      expect(screen.queryByRole('radio')).toBeNull()
    })

    it('is offered by default, so a screen that says nothing loses no control', () => {
      // The prop defaults to true on purpose: forgetting to pass it must not
      // silently hide the background choice on some screen nobody rechecked.
      render(<BackgroundPicker value="hiking_topo_live" onChange={vi.fn()} />)

      expect(screen.getAllByRole('radio')).toHaveLength(BACKGROUND_SOURCES.length)
    })
  })

  it('offers exactly the backgrounds the map can draw', () => {
    render(<BackgroundPicker value="hiking_topo_live" onChange={vi.fn()} />)

    const values = screen
      .getAllByRole('radio')
      .map((radio) => (radio as HTMLInputElement).value)

    expect(values.sort()).toEqual([...BACKGROUND_SOURCES].sort())
  })

  it('shows which one is chosen', () => {
    render(<BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} />)

    expect(screen.getByRole('radio', { name: /downloaded/i })).toBeChecked()
    expect(screen.getByRole('radio', { name: /live/i })).not.toBeChecked()
  })

  it('reports the choice against the canonical field name', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<BackgroundPicker value="hiking_topo_live" onChange={onChange} />)

    await user.click(screen.getByRole('radio', { name: /downloaded/i }))

    expect(onChange).toHaveBeenCalledWith('usgs_topo_offline')
  })

  it('groups its radios so two pickers on one page are not one four-way choice', () => {
    // Radio inputs group by `name` across the whole document, so the prefix is
    // not cosmetic - the legend's picker and Settings' would fight over one
    // selection without it.
    render(
      <>
        <BackgroundPicker value="hiking_topo_live" onChange={vi.fn()} idPrefix="a" />
        <BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} idPrefix="b" />
      </>,
    )

    const names = new Set(
      screen.getAllByRole('radio').map((r) => (r as HTMLInputElement).name),
    )
    expect(names.size).toBe(2)
    expect(
      screen.getAllByRole('radio').filter((r) => (r as HTMLInputElement).checked),
    ).toHaveLength(2)
  })

  it('says the live sheet still falls back to the download with no signal', () => {
    // The one thing someone choosing between these actually needs to know, and
    // the one thing a provider name would not tell them.
    render(<BackgroundPicker value="hiking_topo_live" onChange={vi.fn()} />)

    expect(screen.getByText(/no signal/i)).toBeInTheDocument()
  })

  it('says the offline choice fetches nothing, which is why anyone picks it', () => {
    render(<BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} />)

    expect(screen.getByText(/no background data is fetched/i)).toBeInTheDocument()
  })

  it('never lets an option read as a report on what is on the phone', () => {
    // Reported as a bug by someone holding the whole corridor: the offline
    // option's hint was "No data fetched", and under a label reading
    // "Downloaded" that is taken as "no data downloaded" rather than as a
    // description of what the option does. Both options are rendered here
    // because the trap is the shape of the string, not which choice it is on -
    // and the ONLY place either can appear is inside a label, three words
    // under a status-shaped word.
    render(<BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} />)

    for (const radio of screen.getAllByRole('radio')) {
      expect(radio.closest('label')?.textContent).not.toMatch(/no data|nothing/i)
    }
  })

  it('stays quiet when the choice is being honoured', () => {
    render(<BackgroundPicker value="hiking_topo_live" onChange={vi.fn()} />)

    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('explains a Data Saver override where the choice is made', () => {
    render(
      <BackgroundPicker
        value="hiking_topo_live"
        onChange={vi.fn()}
        override="data-saver"
      />,
    )

    expect(screen.getByText(/data saver is on/i)).toBeInTheDocument()
    expect(screen.getByText(/turn data saver off/i)).toBeInTheDocument()
  })

  it('explains an empty phone without blaming Data Saver for it', () => {
    // Opposite in kind: here the app is fetching tiles rather than withholding
    // them, and borrowing the other notice's words would be a map that lies
    // about what it is doing with someone's data.
    render(
      <BackgroundPicker
        value="usgs_topo_offline"
        onChange={vi.fn()}
        override="nothing-downloaded"
      />,
    )

    expect(screen.getByText(/nothing is downloaded yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/data saver is on/i)).not.toBeInTheDocument()
  })

  it('carries no download control of its own', () => {
    // It briefly did, on the grounds that this is the only other control that
    // mentions the downloaded map - which put a once-a-season errand at the
    // top of the legend, where this picker then sat. Both are at the foot of
    // that panel now and still two controls: the link is its own component
    // (chrome/DownloadsLink.tsx), rendered beside this one by the legend, and
    // what is left here is a background choice and nothing else. A picker that
    // grew its own download button would be a second route to the window for
    // Settings to draw as well.
    render(<BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} />)

    expect(screen.queryByRole('button')).toBeNull()
  })

  it('explains a view zoomed out past what the download covers', () => {
    // #216. The choice is being honoured exactly and still draws nothing, so
    // this needs its own words - and it ends with the remedy, because "zoom
    // in" is the whole fix and blank paper gives no hint of it.
    render(
      <BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} belowArchiveZoom />,
    )

    expect(screen.getByText(/starts closer in than this/i)).toBeInTheDocument()
    expect(screen.getByText(/zoom in/i)).toBeInTheDocument()
  })

  it('does not blame an override for it, since nothing was overridden', () => {
    render(
      <BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} belowArchiveZoom />,
    )

    expect(screen.queryByText(/data saver is on/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/nothing is downloaded yet/i)).not.toBeInTheDocument()
  })

  it('stays quiet about coverage while the download reaches the view', () => {
    render(<BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} />)

    expect(screen.queryByText(/starts closer in/i)).not.toBeInTheDocument()
  })

  it('keeps showing the choice, not the background that is actually drawn', () => {
    // A picker that snapped to "downloaded" because Data Saver was on would be
    // unusable: the hiker could never see, let alone change, what they picked.
    render(
      <BackgroundPicker
        value="hiking_topo_live"
        onChange={vi.fn()}
        override="data-saver"
      />,
    )

    expect(screen.getByRole('radio', { name: /live/i })).toBeChecked()
  })
})
