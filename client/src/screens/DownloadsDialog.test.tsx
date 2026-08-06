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
  it('announces itself as a modal dialog with a name', () => {
    open()

    const dialog = screen.getByRole('dialog', { name: /offline map/i })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
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
