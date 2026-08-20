import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { ClubSheet } from './ClubSheet'
import type { ClubDetail } from '../lib/clubDetail'

// The sentences are lib/clubDetail.ts's and are tested there; this is about
// the component's own two duties - render every line the detail carries, and
// OMIT rather than placeholder the ones it does not (#598). The omissions are
// the point: a club with no region, and a stretch with no maintained mileage
// because no club is recorded for it, are ordinary states rather than errors.

const FULL: ClubDetail = {
  heading: 'Potomac Appalachian Trail Club',
  subtitle: 'PATC · MARO',
  rangeLine: 'mi 940.2 – 1,180.9',
  extentLine: '238.9 mi maintained, in 2 sections',
  absenceLine: null,
  scaleLine: null,
  attributionSourceLine: 'Who maintains it: the ATC’s trail centerline',
  nameSourceLine: 'Club name: the ATC’s club-section map',
}

const UNRECORDED: ClubDetail = {
  heading: 'Club not recorded',
  subtitle: null,
  rangeLine: 'mi 1,013.4 – 1,015.2',
  extentLine: null,
  absenceLine: 'ATC’s centerline does not name a club along here.',
  scaleLine: '1.8 mi of the trail are like this, in 1 run.',
  attributionSourceLine: 'Who maintains it: the ATC’s trail centerline',
  nameSourceLine: null,
}

afterEach(cleanup)

describe('the club sheet', () => {
  it('renders every line the detail carries', () => {
    render(<ClubSheet detail={FULL} onClose={vi.fn()} />)

    expect(screen.getByText('Potomac Appalachian Trail Club')).toBeInTheDocument()
    expect(screen.getByText('PATC · MARO')).toBeInTheDocument()
    expect(screen.getByText('mi 940.2 – 1,180.9')).toBeInTheDocument()
    expect(screen.getByText('238.9 mi maintained, in 2 sections')).toBeInTheDocument()
  })

  it('names both sources, because they are two different claims', () => {
    // Which club is decided by a layer edited days ago; how the name is
    // spelled by one edited two years ago. One line naming "the ATC" would
    // flatten exactly the distinction the exporter publishes them to keep.
    render(<ClubSheet detail={FULL} onClose={vi.fn()} />)

    expect(
      screen.getByText('Who maintains it: the ATC’s trail centerline'),
    ).toBeInTheDocument()
    expect(screen.getByText('Club name: the ATC’s club-section map')).toBeInTheDocument()
  })

  it('omits what the detail does not carry, rather than placeholdering it', () => {
    render(<ClubSheet detail={UNRECORDED} onClose={vi.fn()} />)

    // No subtitle, no maintained mileage, no club-name source: an unrecorded
    // stretch has none of the three, and a blank or an "Unknown" would read as
    // a rendering fault rather than as the ordinary gap it is.
    expect(screen.queryByText(/maintained, in/)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Club name:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Unknown|—\s*$/)).not.toBeInTheDocument()
  })

  it('says the source cannot name a club, never that nobody maintains it', () => {
    render(<ClubSheet detail={UNRECORDED} onClose={vi.fn()} />)

    expect(screen.getByText('Club not recorded')).toBeInTheDocument()
    expect(
      screen.getByText('ATC’s centerline does not name a club along here.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('1.8 mi of the trail are like this, in 1 run.'),
    ).toBeInTheDocument()
  })

  it('closes on the close control', async () => {
    const onClose = vi.fn()
    render(<ClubSheet detail={FULL} onClose={onClose} />)

    screen.getByRole('button', { name: 'Close' }).click()

    expect(onClose).toHaveBeenCalled()
  })

  it('is a dialog, and says what it is about', () => {
    render(<ClubSheet detail={FULL} onClose={vi.fn()} />)
    expect(
      screen.getByRole('dialog', { name: 'Who maintains this trail' }),
    ).toBeInTheDocument()
  })
})
