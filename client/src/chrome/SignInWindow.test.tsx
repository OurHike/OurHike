import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SignInWindow } from './SignInWindow'

// The ask as a window rather than a screen (#1596). What these pin is the
// behaviour a stylesheet cannot give it: that it is a modal dialog, that
// Escape leaves, and that nothing inside is armed by the focus it takes.

afterEach(cleanup)

describe('SignInWindow', () => {
  it('is a modal dialog named for the view inside it', () => {
    render(
      <SignInWindow label="Sign in" onClose={vi.fn()}>
        <p>the ask</p>
      </SignInWindow>,
    )
    const dialog = screen.getByRole('dialog', { name: 'Sign in' })

    expect(dialog).toHaveAttribute('aria-modal', 'true')
  })

  it('renders whatever view it is given, which is how one window holds both steps', () => {
    render(
      <SignInWindow label="Sign in with email" onClose={vi.fn()}>
        <button type="button">Email me a code</button>
      </SignInWindow>,
    )

    expect(screen.getByRole('button', { name: 'Email me a code' })).toBeInTheDocument()
  })

  it('takes focus itself on mount, so Escape works before anything is tabbed to', () => {
    // And so that a stray Enter does not start an OAuth round trip on
    // whichever provider happens to be first - which is what autofocusing the
    // first button would have armed.
    render(
      <SignInWindow label="Sign in" onClose={vi.fn()}>
        <button type="button">Continue with Google</button>
      </SignInWindow>,
    )

    expect(screen.getByRole('dialog')).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Continue with Google' })).not.toHaveFocus()
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <SignInWindow label="Sign in" onClose={onClose}>
        <p>the ask</p>
      </SignInWindow>,
    )

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on Escape from a control inside it, not only from the window itself', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <SignInWindow label="Sign in" onClose={onClose}>
        <input aria-label="Email" />
      </SignInWindow>,
    )
    await user.click(screen.getByLabelText('Email'))

    await user.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not close on any other key, so typing an address is not an exit', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <SignInWindow label="Sign in with email" onClose={onClose}>
        <input aria-label="Email" />
      </SignInWindow>,
    )
    await user.click(screen.getByLabelText('Email'))

    await user.keyboard('hiker@example.com{Enter}')

    expect(onClose).not.toHaveBeenCalled()
  })

  it('adds no close control of its own, because the view inside carries one', () => {
    // Two controls doing one job is worse for a screen reader than none -
    // the call screens/ReportForm.tsx's own comment makes about its Cancel.
    render(
      <SignInWindow label="Sign in" onClose={vi.fn()}>
        <button type="button">Not now</button>
      </SignInWindow>,
    )

    expect(screen.getAllByRole('button')).toHaveLength(1)
  })
})
