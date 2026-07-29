import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IdentitySetup } from './IdentitySetup'

// WIREFRAMES.md §6: "trail name + reporter type (thru / section / day /
// maintainer; maintainer is club-granted and stays unverified until
// confirmed)."
//
// Anyone may select maintainer - it is not gated in the UI. What stops it
// being a self-assigned badge is that it means nothing until a club confirms
// it, and the screen has to say so plainly rather than letting someone
// believe they have just granted themselves standing they do not have.

const PROPS = {
  onSave: vi.fn(),
  onSkip: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('IdentitySetup', () => {
  it('asks for a trail name', () => {
    render(<IdentitySetup {...PROPS} />)

    expect(screen.getByRole('textbox', { name: /trail name/i })).toBeInTheDocument()
  })

  it('offers the four reporter types', () => {
    render(<IdentitySetup {...PROPS} />)

    expect(screen.getAllByRole('radio')).toHaveLength(4)
  })

  it('saves the trail name and reporter type together', async () => {
    const user = userEvent.setup()
    render(<IdentitySetup {...PROPS} />)

    await user.type(screen.getByRole('textbox', { name: /trail name/i }), 'Switchback')
    await user.click(screen.getByRole('radio', { name: /section hiker/i }))
    await user.click(screen.getByRole('button', { name: /save|continue/i }))

    expect(PROPS.onSave).toHaveBeenCalledWith({
      trailName: 'Switchback',
      reporterType: 'section',
    })
  })

  it('lets someone pick maintainer - it is not gated in the interface', async () => {
    const user = userEvent.setup()
    render(<IdentitySetup {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /maintainer/i }))

    expect(screen.getByRole('radio', { name: /maintainer/i })).toBeChecked()
  })

  it('says plainly that a maintainer claim stays unverified until a club confirms it', async () => {
    const user = userEvent.setup()
    render(<IdentitySetup {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /maintainer/i }))

    expect(screen.getByText(/unverified|until.*club confirms/i)).toBeInTheDocument()
  })

  it('says nothing about verification for the self-declared hiker types', async () => {
    const user = userEvent.setup()
    render(<IdentitySetup {...PROPS} />)

    await user.click(screen.getByRole('radio', { name: /thru-hiker/i }))

    expect(screen.queryByText(/unverified/i)).toBe(null)
  })

  it('can be skipped - a trail name is not a condition of contributing', async () => {
    const user = userEvent.setup()
    render(<IdentitySetup {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /skip/i }))

    expect(PROPS.onSkip).toHaveBeenCalled()
  })
})
