// Sharing a finished hike (#1317), against features/COMMUNITY_BUILDING.md.
//
// Two tests carry the design: there is no public link and the screen says
// why, and neither path shares where the hiker is.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ShareHike } from './ShareHike'

const CARD = [
  'Springer → Katahdin',
  'Appalachian Trail',
  '',
  '2,198.4 mi walked · 0 mi to go',
  '14 Mar 2024 – 12 Aug 2026',
  '152 days walking',
  '9 sections',
  'northbound',
].join('\n')

const PROPS = {
  hikeName: 'Springer → Katahdin',
  cardText: CARD,
  recipients: [],
  units: 'imperial' as const,
  onInvite: vi.fn(),
  onClose: vi.fn(),
  canShare: false,
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('sharing a hike', () => {
  it('says the two ways hand over different things, and neither is location', () => {
    render(<ShareHike {...PROPS} />)

    expect(screen.getByText(/Neither shares where you are/)).toBeInTheDocument()
    expect(
      screen.getByText(/live location is its own opt-in, per session/),
    ).toBeInTheDocument()
  })

  it('says there is no public link, and why', () => {
    // COMMUNITY_BUILDING.md's own call. A hiker looking for a "copy link"
    // button is owed the reason it is not there.
    render(<ShareHike {...PROPS} />)

    expect(screen.getByText(/There is no public link, on purpose/)).toBeInTheDocument()
    expect(
      screen.getByText(/A link that reaches anybody reaches people you didn’t choose/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /copy link/i })).not.toBeInTheDocument()
  })

  it('says the in-app share is mutual and revocable', () => {
    render(<ShareHike {...PROPS} />)
    expect(
      screen.getByText(/they have to accept, and you can take it back/),
    ).toBeInTheDocument()
  })

  it('lists who it is shared with, and who has only been invited', () => {
    render(
      <ShareHike
        {...PROPS}
        recipients={[
          { id: 'a', name: 'Switchback', state: 'shared' },
          { id: 'b', name: 'Blue Blaze', state: 'invited' },
        ]}
      />,
    )

    expect(screen.getByText('shared · can see it')).toBeInTheDocument()
    expect(screen.getByText('invited · waiting')).toBeInTheDocument()
  })

  it('previews exactly the text it copies, and warns it cannot be taken back', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    // `stubGlobal` rather than assigning to navigator.clipboard, which jsdom
    // exposes with only a getter - LeaveWithSomeone.test.tsx's idiom.
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })

    render(<ShareHike {...PROPS} />)
    expect(
      screen.getByText(/once it has left, it cannot be taken back/),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Copy as plain text' }))
    expect(writeText).toHaveBeenCalledWith(CARD)
    expect(await screen.findByText('Copied.')).toBeInTheDocument()
  })

  it('offers Send it only where the phone can share', () => {
    // A control that looks pressable and is not teaches a hiker the app is
    // broken - LineSheet's rule.
    const { unmount } = render(<ShareHike {...PROPS} canShare={false} />)
    expect(screen.queryByRole('button', { name: 'Send it' })).not.toBeInTheDocument()
    unmount()

    render(<ShareHike {...PROPS} canShare />)
    expect(screen.getByRole('button', { name: 'Send it' })).toBeInTheDocument()
  })

  it('points a cancelled share at the copy path rather than calling it an error', async () => {
    const user = userEvent.setup()
    render(
      <ShareHike
        {...PROPS}
        canShare
        share={() => Promise.reject(new Error('cancelled'))}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Send it' }))
    expect(await screen.findByText(/you can copy it instead/)).toBeInTheDocument()
    expect(screen.queryByText(/failed|error/i)).not.toBeInTheDocument()
  })

  it('prints no percentage, nothing behind and nothing on track', () => {
    const { container } = render(<ShareHike {...PROPS} />)
    expect(container.textContent).not.toMatch(/%|behind|ahead of|on track|streak/i)
  })
})
