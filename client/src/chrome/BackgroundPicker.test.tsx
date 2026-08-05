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

  it('offers the way to the download, since this is the only control that mentions one', () => {
    // The Downloads tab went on 2026-08-05 (chrome/tabs.ts) and this link is
    // what took its place.
    const onOpenDownloads = vi.fn()
    render(
      <BackgroundPicker
        value="usgs_topo_offline"
        onChange={vi.fn()}
        onOpenDownloads={onOpenDownloads}
      />,
    )

    expect(
      screen.getByRole('button', { name: /choose what to download/i }),
    ).toBeInTheDocument()
  })

  it('opens the download window when that link is used', async () => {
    const user = userEvent.setup()
    const onOpenDownloads = vi.fn()
    const onChange = vi.fn()
    render(
      <BackgroundPicker
        value="hiking_topo_live"
        onChange={onChange}
        onOpenDownloads={onOpenDownloads}
      />,
    )

    await user.click(screen.getByRole('button', { name: /download/i }))

    expect(onOpenDownloads).toHaveBeenCalledTimes(1)
    // Asking about the download is not choosing a background. The link sits
    // outside both labels precisely so it cannot toggle the radio it is under.
    expect(onChange).not.toHaveBeenCalled()
  })

  it('says CHANGE rather than choose once there is a download to change', () => {
    render(
      <BackgroundPicker
        value="usgs_topo_offline"
        onChange={vi.fn()}
        onOpenDownloads={vi.fn()}
        hasDownload
      />,
    )

    expect(
      screen.getByRole('button', { name: /change what's downloaded/i }),
    ).toBeVisible()
    expect(screen.queryByRole('button', { name: /choose what to download/i })).toBeNull()
  })

  it('draws no link at all where there is no window to open', () => {
    // Same rule the picker already follows for a shell that cannot write the
    // preference: a control that does nothing is worse than no control.
    render(<BackgroundPicker value="usgs_topo_offline" onChange={vi.fn()} />)

    expect(screen.queryByRole('button', { name: /download/i })).toBeNull()
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
