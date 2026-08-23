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
  extentLine: null,
  closureLine: null,
  switchNote: null,
}

/** A nearby trail: somebody else's network, with the three lines an A.T. spur
 *  never carries (#783). */
const NEARBY: LineDetail = {
  heading: 'Yellow blaze · side trail',
  name: 'Suffern–Bear Mountain Trail',
  destinationLine: null,
  roundTripLine: null,
  junctionLine: null,
  sourceLine:
    'From New York State Office of Parks, Recreation and Historic Preservation.',
  extentLine: '24.0 mi · Harriman State Park',
  closureLine: null,
  switchNote: 'Not the trail you chose. Switching happens in the picker.',
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
          extentLine: null,
          closureLine: null,
          switchNote: null,
        }}
        onClose={vi.fn()}
      />,
    )

    // The heading and the close control are all there is.
    expect(screen.getByRole('dialog').querySelectorAll('p')).toHaveLength(0)
    expect(screen.queryByText(/unknown/i)).not.toBeInTheDocument()
  })

  it('renders a nearby trail’s extent, provenance and the refusal to switch', () => {
    render(<LineSheet detail={NEARBY} onClose={vi.fn()} />)

    expect(screen.getByText('24.0 mi · Harriman State Park')).toBeInTheDocument()
    expect(
      screen.getByText(
        'From New York State Office of Parks, Recreation and Historic Preservation.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Not the trail you chose. Switching happens in the picker.'),
    ).toBeInTheDocument()
  })

  it('offers no action at all on a nearby trail — the decision, not an oversight', () => {
    // features/NEARBY_TRAILS.md §2: switching trails swaps the mile frame, the
    // ribbon, the Naismith numbers and the amenity POI set at once, and a
    // one-tap switch at a junction is an accidental context loss in exactly
    // the moment a wrong screen costs most. The close control is the only
    // button this sheet may ever have.
    render(<LineSheet detail={NEARBY} onClose={vi.fn()} />)

    const buttons = screen.getByRole('dialog').querySelectorAll('button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0]).toHaveTextContent('Close')
  })

  it('says which kind of closed a long-term closure is, rather than drawing it differently', () => {
    render(
      <LineSheet
        detail={{
          ...NEARBY,
          closureLine: 'Closed by NYS OPRHP · layer edited 4 Aug 2026',
        }}
        onClose={vi.fn()}
      />,
    )

    expect(
      screen.getByText('Closed by NYS OPRHP · layer edited 4 Aug 2026'),
    ).toBeInTheDocument()
  })

  it('closes from its own button', async () => {
    const onClose = vi.fn()
    render(<LineSheet detail={FULL} onClose={onClose} />)

    screen.getByRole('button', { name: /close/i }).click()

    expect(onClose).toHaveBeenCalled()
  })
})
