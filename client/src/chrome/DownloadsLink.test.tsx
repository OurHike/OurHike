import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DownloadsLink } from './DownloadsLink'

// The only route to the download window since the Downloads tab went
// (chrome/tabs.ts). Where it SITS - last in the legend, last in Settings - is
// asserted by those two, since it is a fact about them. What is asserted here
// is that it opens the window and that it says the right thing about the phone
// it is on.

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
})
