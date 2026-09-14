import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Notice } from './Notice'

afterEach(cleanup)

describe('Notice', () => {
  it('prints the title and the sentence under it', () => {
    render(
      <Notice
        tone="warn"
        title="The topo sheet is not on this phone"
        body="412 MB. Trails and waypoints work without it."
      />,
    )

    expect(screen.getByText('The topo sheet is not on this phone')).toBeInTheDocument()
    expect(
      screen.getByText('412 MB. Trails and waypoints work without it.'),
    ).toBeInTheDocument()
  })

  it('carries its next step as a real button, and none when there is none', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    const { rerender } = render(
      <Notice
        tone="warn"
        title="Not on the phone"
        action={{ label: 'Download', onClick }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Download' }))
    expect(onClick).toHaveBeenCalledTimes(1)

    // Omitted, never disabled: a refusal is a sentence, not a greyed control.
    rerender(<Notice tone="warn" title="Not on the phone" />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('offers a link under the body as a second door', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Notice
        tone="urgent"
        title="A closure crosses day 5"
        body="Bridge out at northbound mile 1,354.2."
        link={{ label: 'Put the detour in day 5 ›', onClick }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Put the detour in day 5 ›' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('announces a warning once and leaves a quiet fact silent', () => {
    const { rerender } = render(<Notice tone="urgent" title="Closed" />)
    expect(screen.getByRole('status')).toHaveTextContent('Closed')

    rerender(<Notice tone="quiet" title="Couldn't check" />)
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('draws the tone as a class the stylesheet keys on', () => {
    const { container } = render(<Notice tone="warn" title="x" />)

    expect(container.firstElementChild).toHaveClass('notice', 'notice--warn')
  })
})
