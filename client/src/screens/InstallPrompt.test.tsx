import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { InstallPrompt } from './InstallPrompt'

// The bug this screen exists to close: the landing page at /OurHike/ carries no
// manifest and no service worker, so a browser's "Add to Home screen" there
// makes a plain bookmark that looks exactly like a successful install. Only the
// app can be installed, so the prompt lives here.

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('InstallPrompt', () => {
  it('offers a real install button on Android once the browser confirms it qualifies', async () => {
    const onInstall = vi.fn()
    const user = userEvent.setup()
    render(<InstallPrompt platform="android" canPrompt onInstall={onInstall} />)

    await user.click(screen.getByRole('button', { name: /install ourhike/i }))

    expect(onInstall).toHaveBeenCalledTimes(1)
  })

  it('shows steps instead of a button until the browser confirms it qualifies', () => {
    // A button that might do nothing is worse than no button on the one screen
    // whose job is getting someone installed.
    render(<InstallPrompt platform="android" canPrompt={false} onInstall={vi.fn()} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByText(/install app/i)).toBeInTheDocument()
  })

  it('never offers a button on iOS, which has no install API at all', () => {
    render(<InstallPrompt platform="ios" canPrompt onInstall={vi.fn()} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByText(/add to home screen/i)).toBeInTheDocument()
  })

  it('tells iOS users it has to be Safari, since other iOS browsers cannot install', () => {
    render(<InstallPrompt platform="ios" canPrompt={false} onInstall={vi.fn()} />)

    expect(screen.getByRole('note')).toHaveTextContent(/safari/i)
  })

  it('disappears once the app is installed', () => {
    const { container } = render(
      <InstallPrompt platform="installed" canPrompt={false} onInstall={vi.fn()} />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('stays out of the way on desktop, where installing a trail map means little', () => {
    const { container } = render(
      <InstallPrompt platform="other" canPrompt onInstall={vi.fn()} />,
    )

    expect(container).toBeEmptyDOMElement()
  })
})
