import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { LineSheet } from './LineSheet'
import type { LineDetail } from '../lib/lineDetail'

// The sentences are lib/lineDetail.ts's and are tested there; this is about
// the component's own two duties - render every line the detail carries, and
// OMIT rather than placeholder the ones it does not (#134). A null rendered
// as "Unknown destination" would read as a data error rather than the
// ordinary situation it is for ~12% of spurs.

const FULL: LineDetail = {
  heading: 'Blue blaze · spur',
  name: 'Rocky Run Spur Trail',
  destinationLine: 'To Rocky Run Shelter — 0.2 mi each way',
  roundTripLine: '≈20m there and back',
  junctionLine: 'Joins the AT at mi 1,043.2',
  sourceLine: 'From the Appalachian Trail Conservancy’s side trails data.',
}

afterEach(cleanup)

describe('the line-detail sheet', () => {
  it('renders every line the detail carries', () => {
    render(<LineSheet detail={FULL} onClose={vi.fn()} />)

    expect(screen.getByRole('heading')).toHaveTextContent('Blue blaze · spur')
    expect(screen.getByText('Rocky Run Spur Trail')).toBeInTheDocument()
    expect(screen.getByText('To Rocky Run Shelter — 0.2 mi each way')).toBeInTheDocument()
    expect(screen.getByText('≈20m there and back')).toBeInTheDocument()
    expect(screen.getByText('Joins the AT at mi 1,043.2')).toBeInTheDocument()
    expect(
      screen.getByText('From the Appalachian Trail Conservancy’s side trails data.'),
    ).toBeInTheDocument()
  })

  it('omits absent facts entirely, with no placeholder standing in', () => {
    render(
      <LineSheet
        detail={{
          heading: 'White blaze · Appalachian Trail',
          name: null,
          destinationLine: null,
          roundTripLine: null,
          junctionLine: null,
          sourceLine: null,
        }}
        onClose={vi.fn()}
      />,
    )

    // The heading and the close control are all there is.
    expect(screen.getByRole('dialog').querySelectorAll('p')).toHaveLength(0)
    expect(screen.queryByText(/unknown/i)).not.toBeInTheDocument()
  })

  it('closes from its own button', async () => {
    const onClose = vi.fn()
    render(<LineSheet detail={FULL} onClose={onClose} />)

    screen.getByRole('button', { name: /close/i }).click()

    expect(onClose).toHaveBeenCalled()
  })
})
