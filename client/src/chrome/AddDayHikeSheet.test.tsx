// Adding a day hike to a long hike (#1317).

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { AddDayHikeSheet } from './AddDayHikeSheet'

const PROPS = {
  candidates: [],
  onAdd: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('adding a day hike to a hike', () => {
  it('says only the miles on this trail are counted', () => {
    // The rule that makes the door offerable at all: a walk that wandered
    // onto side trails is still a day on this trail for the part that was.
    render(<AddDayHikeSheet {...PROPS} />)
    expect(
      screen.getByText(/only the miles on this trail are counted/i),
    ).toBeInTheDocument()
  })

  it('offers an eligible walk with where on the trail it was', async () => {
    const user = userEvent.setup()
    const onAdd = vi.fn()
    render(
      <AddDayHikeSheet
        {...PROPS}
        candidates={[
          {
            id: 'd1',
            name: 'Dragon’s Tooth',
            meta: '8.8 mi · walked 4 May · mi 712.3–716.7 on this trail',
            eligible: true,
          },
        ]}
        onAdd={onAdd}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Dragon’s Tooth/ }))
    expect(onAdd).toHaveBeenCalledWith('d1')
  })

  it('shows an ineligible walk with its reason rather than hiding it', () => {
    // Hiding it would leave a hiker hunting for a walk they can see on the
    // day-hike list one screen away; a dead button would teach them the app
    // is broken. LineSheet's rule.
    render(
      <AddDayHikeSheet
        {...PROPS}
        candidates={[
          {
            id: 'd2',
            name: 'Bear Mountain loop',
            meta: 'None of this walk is on this hike’s trail.',
            eligible: false,
          },
        ]}
      />,
    )

    const door = screen.getByRole('button', { name: /Bear Mountain loop/ })
    expect(door).toBeDisabled()
    expect(door).toHaveTextContent(/None of this walk is on this hike’s trail/)
  })

  it('says so plainly when there is nothing saved to offer', () => {
    render(<AddDayHikeSheet {...PROPS} />)
    expect(screen.getByText(/No saved day hikes yet/)).toBeInTheDocument()
  })
})
