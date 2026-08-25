// Leave this with someone (#1008, frame D6). The rules under test are the
// safety-shaped ones: the typed lines flow into the card verbatim, the app
// never turns a walking estimate into a return time, and each hand-over
// path reports only what actually happened.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { LeaveWithSomeone } from './LeaveWithSomeone'
import type { DayHike } from '../lib/dayHikes'

const HIKE: DayHike = {
  id: 'hike-1',
  name: 'Pine Meadow loop',
  date: '2026-09-12',
  segments: [
    [
      { coord: [-74.095, 41.25], poiId: null },
      { coord: [-74.085, 41.25], poiId: null },
    ],
  ],
  figures: {
    miles: 6.2,
    legs: [
      { name: 'Pine Meadow Trail', source: 'nynjtc', blaze_color: 'red', miles: 6.2 },
    ],
  },
  looped: true,
  recorded: 'planned',
}

/** The live derivation, which is what the card gets in the normal case. */
const FIGURES = {
  miles: 6.2,
  legs: [{ name: 'Pine Meadow Trail' }],
  fromCache: false,
  gapMiles: 0,
  stretches: 1,
}

/** A fixed day, so the header's written/planned logic is testable. */
const TODAY = '2026-09-12'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('the card', () => {
  it('previews the plan and carries a typed line into it verbatim', async () => {
    const user = userEvent.setup()
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={false}
        today={TODAY}
      />,
    )

    expect(screen.getByText(/Pine Meadow loop · sat 12 sep/)).toBeInTheDocument()
    expect(screen.getByText(/6\.2 mi on marked trails/)).toBeInTheDocument()

    await user.type(screen.getByLabelText(/If I.{0,3}m not back by/), '6:00 pm')
    expect(
      screen.getByText(/If I'm not back by 6:00 pm, something's wrong\./),
    ).toBeInTheDocument()
  })

  it('says the not-back-by line is the hiker’s to write', () => {
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={false}
        today={TODAY}
      />,
    )
    expect(
      screen.getByText(/We won.{0,3}t guess an arrival time from a walking estimate/),
    ).toBeInTheDocument()
  })

  it('computes no time of its own, anywhere on the sheet', () => {
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={false}
        today={TODAY}
      />,
    )
    expect(document.body.textContent).not.toContain('≈')
    // The only clock digits allowed are the placeholder's own example.
    const preview = screen.getByText(/on marked trails/).textContent ?? ''
    expect(preview).not.toMatch(/\d{1,2}:\d{2}/)
  })
})

describe('handing it over', () => {
  it('offers Send it only where the share sheet exists', () => {
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={false}
        today={TODAY}
      />,
    )
    expect(screen.queryByRole('button', { name: 'Send it' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy as plain text' })).toBeInTheDocument()
  })

  it('sends the composed text through the share sheet and says Sent', async () => {
    const user = userEvent.setup()
    const share = vi.fn().mockResolvedValue(undefined)
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={true}
        share={share}
        today={TODAY}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Send it' }))
    expect(share).toHaveBeenCalledWith(expect.stringContaining('Pine Meadow loop'))
    expect(await screen.findByRole('status')).toHaveTextContent('Sent.')
  })

  it('a share that did not happen points at the copy path, without crying error', async () => {
    const user = userEvent.setup()
    const share = vi.fn().mockRejectedValue(new Error('dismissed'))
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={true}
        share={share}
        today={TODAY}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Send it' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      /Nothing was sent\. Copy as plain text works everywhere\./,
    )
  })

  it('copies the exact card text, read back from the clipboard', async () => {
    const user = userEvent.setup()
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={false}
        today={TODAY}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Copy as plain text' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Copied.')
    const copied = await navigator.clipboard.readText()
    expect(copied).toContain('Pine Meadow loop · sat 12 sep')
    expect(copied).toContain('It does not track me.')
  })

  it('retires "Copied." the moment the card changes under it', async () => {
    // The status vouches for bytes that already left. Left standing, it
    // would vouch for a card missing the line typed after it - and the
    // field typed last is the one this sheet exists for.
    const user = userEvent.setup()
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={false}
        today={TODAY}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Copy as plain text' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Copied.')

    await user.type(screen.getByLabelText(/If I.{0,3}m not back by/), '6')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('admits a refused clipboard rather than reporting a copy that never happened', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('navigator', {
      ...navigator,
      clipboard: {
        writeText: () => Promise.reject(new Error('no')),
      },
    })
    render(
      <LeaveWithSomeone
        hike={HIKE}
        figures={FIGURES}
        units="imperial"
        onClose={vi.fn()}
        canShare={false}
        today={TODAY}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Copy as plain text' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      /would not let the app use the clipboard/,
    )
  })
})
