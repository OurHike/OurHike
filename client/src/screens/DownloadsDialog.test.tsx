import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DownloadsDialog } from './DownloadsDialog'

// The window the Downloads tab became. What matters here is that it behaves
// like a window: it says what it is, it can be got out of three ways, and
// getting out of it is not something a near-miss can do by accident - the
// panel holds a Delete button, and the whole corridor is what gets deleted.

afterEach(() => {
  cleanup()
})

function open(onClose = vi.fn()) {
  render(
    <DownloadsDialog onClose={onClose}>
      <p>the download itself</p>
    </DownloadsDialog>,
  )
  return onClose
}

describe('DownloadsDialog', () => {
  it('announces itself as a named dialog', () => {
    open()

    expect(screen.getByRole('dialog', { name: /offline map/i })).toBeInTheDocument()
  })

  it('does not claim to be modal, because it does not trap focus (#315)', () => {
    // The assertion here used to require `aria-modal="true"`, pinning the
    // defect. This file's own header refuses a focus trap - "half of one is
    // worse than none because it looks handled" - and `aria-modal` was that
    // same mistake one layer up, promising assistive tech an inertness
    // nothing delivers. If a trap is ever built the attribute comes back
    // with it, in the same change.
    open()

    expect(screen.getByRole('dialog', { name: /offline map/i })).not.toHaveAttribute(
      'aria-modal',
    )
  })

  it('shows what the shell put in it', () => {
    open()

    expect(screen.getByText('the download itself')).toBeInTheDocument()
  })

  it('closes on the close button', async () => {
    const user = userEvent.setup()
    const onClose = open()

    await user.click(screen.getByRole('button', { name: /close/i }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on Escape, which is what every dialog on the web teaches', async () => {
    const user = userEvent.setup()
    const onClose = open()

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on the backdrop', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { container } = render(
      <DownloadsDialog onClose={onClose}>
        <p>the download itself</p>
      </DownloadsDialog>,
    )

    await user.click(container.querySelector('.downloads-dialog') as HTMLElement)

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not close on a click inside the panel', async () => {
    // Every click in the panel bubbles out through the backdrop element too.
    // Dismissing on those would mean a tap that lands slightly off "Resume"
    // throwing away the window instead - and the panel below this one also
    // holds "Delete the map."
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <DownloadsDialog onClose={onClose}>
        <button type="button">Download the map</button>
      </DownloadsDialog>,
    )

    await user.click(screen.getByRole('button', { name: 'Download the map' }))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('moves focus into the window, so a screen reader lands on what appeared', () => {
    open()

    expect(screen.getByRole('dialog', { name: /offline map/i })).toHaveFocus()
  })
})
