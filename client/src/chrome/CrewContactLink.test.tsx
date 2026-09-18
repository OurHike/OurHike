import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { CrewContactLink } from './CrewContactLink'

// The one link both crew surfaces render (#1578). What this file holds: a
// contact becomes a link only when it is an address, a number or a page, a
// page opens beside the app, and a string that is none of those renders
// nothing rather than a link the phone would act on.

afterEach(() => {
  cleanup()
})

describe('CrewContactLink', () => {
  it('links an address and a number in place, with no new tab', () => {
    render(<CrewContactLink contact="mailto:crew@example.org" className="x" />)
    const link = screen.getByRole('link', { name: /ask the crew about joining/i })
    expect(link.getAttribute('href')).toBe('mailto:crew@example.org')
    expect(link.getAttribute('target')).toBeNull()

    cleanup()
    render(<CrewContactLink contact="tel:+12125551234" className="x" />)
    expect(screen.getByRole('link').getAttribute('href')).toBe('tel:+12125551234')
  })

  it('opens a page beside the app, as every other external link does', () => {
    render(<CrewContactLink contact="https://example.org/volunteer" className="x" />)
    const link = screen.getByRole('link', { name: /ask the crew about joining/i })
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toBe('noreferrer')
  })

  it('renders nothing for no contact, and nothing for a contact that is not a channel', () => {
    const { container } = render(<CrewContactLink contact={null} className="x" />)
    expect(container).toBeEmptyDOMElement()

    cleanup()
    render(<CrewContactLink contact="data:text/html,<p>join</p>" className="x" />)
    expect(screen.queryByRole('link')).toBeNull()

    cleanup()
    render(
      <CrewContactLink contact="intent://join/#Intent;scheme=zxing;end" className="x" />,
    )
    expect(screen.queryByRole('link')).toBeNull()
  })
})
