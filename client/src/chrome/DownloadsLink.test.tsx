import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DownloadsLink } from './DownloadsLink'

// The only route to the download window since the Downloads tab went
// (chrome/tabs.ts). Where it SITS - last in the legend, last in Settings - is
// asserted by those two, since it is a fact about them. What is asserted here
// is that it opens the window, that it says the right thing about the phone it
// is on, and that it admits a download that is still running with the window
// shut.

afterEach(() => {
  cleanup()
})

describe('DownloadsLink', () => {
  it('opens the download window', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<DownloadsLink onOpen={onOpen} />)

    await user.click(screen.getByRole('button', { name: /download/i }))

    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it('offers to CHOOSE a download on a phone that has none', () => {
    render(<DownloadsLink onOpen={vi.fn()} />)

    expect(screen.getByRole('button', { name: /choose what to download/i })).toBeVisible()
  })

  it('offers to CHANGE one once there is a download to change', () => {
    // "Choose what to download" is wrong for someone holding 314 MB of it, and
    // "change your download" is a claim about a phone that may have nothing.
    render(<DownloadsLink onOpen={vi.fn()} hasDownload />)

    expect(
      screen.getByRole('button', { name: /change what's downloaded/i }),
    ).toBeVisible()
    expect(screen.queryByRole('button', { name: /choose what to download/i })).toBeNull()
  })

  it('says how far a download in flight has got', () => {
    // The whole point: the transfer belongs to the shell, so shutting its
    // window used to leave an app that looked idle while it spent someone's
    // data. Said in the button's own words rather than through a
    // `role="progressbar"`, which a screen reader would drop - a button's
    // descendants are presentational.
    render(
      <DownloadsLink
        onOpen={vi.fn()}
        downloadActivity={{ kind: 'downloading', doneBytes: 40, totalBytes: 100 }}
      />,
    )

    expect(
      screen.getByRole('button', { name: /choose what to download.*downloading 40%/i }),
    ).toBeVisible()
  })

  it('draws the bar to the figure it just stated', () => {
    // The bar is what the eye reads; the percent beside it is what a screen
    // reader gets. Two roundings of one ratio, agreeing wherever the ratio
    // lands on a whole percent.
    const { container } = render(
      <DownloadsLink
        onOpen={vi.fn()}
        downloadActivity={{ kind: 'downloading', doneBytes: 3, totalBytes: 4 }}
      />,
    )

    expect(screen.getByText('Downloading 75%')).toBeVisible()
    expect(
      container.querySelector<HTMLElement>('.downloads-link__bar-fill')?.style.width,
    ).toBe('75%')
  })

  it('creeps the bar in tenths while the stated figure stays whole (#449)', () => {
    // A whole percent of the first sheet is 7.9 MB of the bar sitting still,
    // and a still bar is this app's own signal for "stalled". The fill moves
    // finer; the number a screen reader hears stays calm.
    const { container } = render(
      <DownloadsLink
        onOpen={vi.fn()}
        downloadActivity={{ kind: 'downloading', doneBytes: 2, totalBytes: 3 }}
      />,
    )

    expect(screen.getByText('Downloading 67%')).toBeVisible()
    expect(
      container.querySelector<HTMLElement>('.downloads-link__bar-fill')?.style.width,
    ).toBe('66.6%')
  })

  it('names the wait that is the phone rather than the network', () => {
    // #197's distinction, kept in the footer: someone on one bar of signal who
    // reads this as a stalled download will walk somewhere else for nothing.
    render(
      <DownloadsLink
        onOpen={vi.fn()}
        downloadActivity={{ kind: 'checking', doneBytes: 1, totalBytes: 2 }}
      />,
    )

    expect(screen.getByText('Checking 50%')).toBeVisible()
  })

  it('is still one tap to the window while a download runs', async () => {
    // The bar is inside the button on purpose - it is what the eye lands on,
    // so it is what a thumb goes for, and a bar that is not part of the
    // control is a tap that does nothing.
    const user = userEvent.setup()
    const onOpen = vi.fn()
    const { container } = render(
      <DownloadsLink
        onOpen={onOpen}
        hasDownload
        downloadActivity={{ kind: 'downloading', doneBytes: 1, totalBytes: 2 }}
      />,
    )

    await user.click(container.querySelector('.downloads-link__bar')!)

    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it('says the canary is running, without a bar it could not fill honestly', () => {
    // Before the transfer there is no total to be a percentage of, so the
    // word goes out on its own. A 0% bar here would be a figure invented to
    // fill the slot - and it is precisely a bar stuck at 0 that this state
    // exists to stop looking like.
    const { container } = render(
      <DownloadsLink onOpen={vi.fn()} downloadActivity={{ kind: 'preparing' }} />,
    )

    expect(screen.getByText('Getting trail data…')).toBeVisible()
    expect(container.querySelector('.downloads-link__bar')).toBeNull()
  })

  it('says nothing at all when nothing is moving', () => {
    // Which is nearly always. A footer holding room for a bar would spend that
    // room on every screen for the sake of the few minutes a year one runs.
    const { container } = render(<DownloadsLink onOpen={vi.fn()} hasDownload />)

    expect(container.querySelector('.downloads-link__bar')).toBeNull()
    expect(screen.queryByText(/%/)).toBeNull()
  })
})
