// You are not on your route (#1041, frame `D11`).
//
// The refusal IS the feature here, so it is the thing under test: this card
// must never acquire a way back. There is no marked trail between a hiker in
// the laurel and their route, and a routed line across that ground would look
// exactly like a path on the screen somebody uses to decide where to walk.

import { describe, expect, it, vi, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { OffRouteBand, OffRouteCard } from './OffRouteCard'
import type { OffRoute } from '../lib/dayHikeFollow'

const OFF: OffRoute = {
  kind: 'off-route',
  offRouteFeet: 300,
  nearest: {
    walkedMi: 2.6,
    feet: 300,
    // North-east of the hiker.
    bearingDeg: 45,
    at: { lon: -74.09, lat: 41.25 },
  },
  totalMi: 6.2,
}

const PROPS = { follow: OFF, onShowRoute: vi.fn(), onStopFollowing: vi.fn() }

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('OffRouteBand', () => {
  it('is an alert, and says which way it is wrong', () => {
    render(<OffRouteBand follow={OFF} />)

    const band = screen.getByRole('alert')
    expect(band).toHaveTextContent('You are not on your route')
    expect(band).toHaveTextContent('300 ft')
  })
})

describe('OffRouteCard', () => {
  it('gives a distance and a bearing, in words a body can be pointed by', () => {
    render(<OffRouteCard {...PROPS} />)

    expect(screen.getByText(/300 ft/)).toBeInTheDocument()
    expect(screen.getByText(/north-east/)).toBeInTheDocument()
  })

  it('says out loud that it will not draw a way back', () => {
    render(<OffRouteCard {...PROPS} />)

    expect(screen.getByText('We will not draw you a line back')).toBeInTheDocument()
    expect(
      screen.getByText(/no marked trail between you and your route/),
    ).toBeInTheDocument()
  })

  it('offers only the two things it can honestly do', () => {
    // Frame `D11` draws "Point me at it" and "Re-route from a trail". The
    // first needs a live compass heading nothing in this client reads; the
    // second needs the builder re-entered mid-walk (#983). A button for
    // either would be a promise the app cannot keep.
    render(<OffRouteCard {...PROPS} />)

    expect(
      screen.getByRole('button', { name: 'Show the whole route' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop following' })).toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(2)
  })

  it('switches to miles once feet stop being a number to pace out', () => {
    render(
      <OffRouteCard
        {...PROPS}
        follow={{ ...OFF, nearest: { ...OFF.nearest, feet: 2640 } }}
      />,
    )

    expect(screen.getByText(/0.5 mi/)).toBeInTheDocument()
  })

  it('puts the whole walk back on screen when asked', async () => {
    render(<OffRouteCard {...PROPS} />)

    await userEvent.click(screen.getByRole('button', { name: 'Show the whole route' }))
    expect(PROPS.onShowRoute).toHaveBeenCalled()
  })
})
