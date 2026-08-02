import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { WaypointLanes } from './WaypointLanes'

// WIREFRAMES.md §1.4: three lanes of 19px - WATER, SLEEP, ELSE - with mono
// labels in the left gutter and pins positioned by percentage along the mile
// window. The clustering maths lives in lib/waypointLanes.ts and is tested
// there; this covers the rendering of it.

const WINDOW = { startMile: 1400, endMile: 1410 }

const POINTS = [
  { id: 'w1', type: 'water', mile: 1402 },
  { id: 'w2', type: 'water', mile: 1402.05 },
  { id: 'w3', type: 'water', mile: 1402.1 },
  { id: 's1', type: 'shelter', mile: 1406 },
  { id: 'r1', type: 'resupply', mile: 1408 },
]

const PROPS = { points: POINTS, ...WINDOW }

afterEach(() => {
  cleanup()
})

describe('WaypointLanes', () => {
  it('renders the three lanes with their gutter labels', () => {
    render(<WaypointLanes {...PROPS} />)

    expect(screen.getByText('WATER')).toBeInTheDocument()
    expect(screen.getByText('SLEEP')).toBeInTheDocument()
    expect(screen.getByText('ELSE')).toBeInTheDocument()
  })

  it('puts each waypoint in the right lane', () => {
    render(<WaypointLanes {...PROPS} />)

    expect(within(screen.getByTestId('lane-sleep')).getAllByRole('button')).toHaveLength(
      1,
    )
    expect(within(screen.getByTestId('lane-else')).getAllByRole('button')).toHaveLength(1)
  })

  it('collapses a tight cluster into a single pill showing how many it swallowed', () => {
    render(<WaypointLanes {...PROPS} />)
    const waterPins = within(screen.getByTestId('lane-water')).getAllByRole('button')

    expect(waterPins).toHaveLength(1)
    expect(waterPins[0]).toHaveTextContent('3')
  })

  it('does not put a count on a lone pin', () => {
    render(<WaypointLanes {...PROPS} />)
    const shelter = within(screen.getByTestId('lane-sleep')).getByRole('button')

    expect(shelter).not.toHaveTextContent('1')
  })

  it('positions a pin by percentage, so it lines up with the profile above it', () => {
    render(<WaypointLanes {...PROPS} />)
    const shelter = within(screen.getByTestId('lane-sleep')).getByRole('button')

    // 1406 of 1400-1410 is 60%.
    expect(shelter.style.left).toBe('60%')
  })

  it('names each pin for assistive tech instead of leaving a bare glyph', () => {
    render(<WaypointLanes {...PROPS} />)

    expect(
      within(screen.getByTestId('lane-sleep')).getByRole('button', { name: /shelter/i }),
    ).toBeInTheDocument()
  })

  it('says how many a pill stands for in its accessible name', () => {
    render(<WaypointLanes {...PROPS} />)

    expect(
      within(screen.getByTestId('lane-water')).getByRole('button', { name: /3 water/i }),
    ).toBeInTheDocument()
  })

  it('still renders all three lanes when nothing is in the window', () => {
    render(<WaypointLanes {...PROPS} points={[]} />)

    expect(screen.getByTestId('lane-water')).toBeInTheDocument()
    expect(screen.getByTestId('lane-sleep')).toBeInTheDocument()
    expect(screen.getByTestId('lane-else')).toBeInTheDocument()
  })

  it('draws a waypoint type it has no glyph for rather than dropping it', () => {
    // The pipeline can publish a POI type this build has never heard of. A
    // neutral dot on the lane is the honest rendering; leaving it off the
    // ribbon entirely would hide a real thing on the trail.
    render(<WaypointLanes {...PROPS} points={[{ id: 'x1', type: 'yurt', mile: 1405 }]} />)

    expect(screen.getByTestId('lane-else')).toHaveTextContent('•')
  })
})
