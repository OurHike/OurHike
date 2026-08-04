import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PoiSheet, type PoiDetail } from './PoiSheet'

// WIREFRAMES.md's POI detail (`6a`-`6b`), which the screen map derives from
// OurHikeValues.md #4 - honesty about uncertainty - as much as from the data.
//
// The line that carries that value is the unverified one. The pin says the
// same thing with a broken rim, which is a channel someone has to have learned
// to read; this is where it is said in words, and only where it is true.

const SHELTER: PoiDetail = {
  id: 'atc_shelters:abc',
  name: 'Chairback Gap Lean-to',
  type: 'shelter',
  lat: 45.4732,
  lon: -69.1183,
  confidence: 'high',
  source: 'atc_shelters',
  mile: 2078.4,
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('PoiSheet', () => {
  it('names the waypoint and what kind of thing it is', () => {
    render(<PoiSheet poi={SHELTER} onClose={vi.fn()} />)

    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Lean-to' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Shelter')).toBeInTheDocument()
  })

  it('places it on the trail', () => {
    render(<PoiSheet poi={SHELTER} onClose={vi.fn()} />)

    expect(screen.getByText('mi 2,078.4')).toBeInTheDocument()
  })

  it('omits the mile rather than guessing one when the trail lines are missing', () => {
    // The centerline index is a separate download and can legitimately be
    // absent. A shelter with no mile is still worth a sheet - it just cannot
    // say where along the trail it is.
    render(<PoiSheet poi={{ ...SHELTER, mile: undefined }} onClose={vi.fn()} />)

    expect(screen.queryByText(/^mi /)).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: SHELTER.name })).toBeInTheDocument()
  })

  it('gives coordinates precise enough to read out to somebody', () => {
    render(<PoiSheet poi={SHELTER} onClose={vi.fn()} />)

    expect(screen.getByText(/45\.47320, -69\.11830/)).toBeInTheDocument()
  })

  it('writes coordinates with a plain hyphen, so they paste into another device', () => {
    render(<PoiSheet poi={SHELTER} onClose={vi.fn()} />)

    expect(screen.queryByText(/−/)).not.toBeInTheDocument()
  })

  it('says in words when nobody has confirmed the waypoint exists', () => {
    render(<PoiSheet poi={{ ...SHELTER, confidence: 'low' }} onClose={vi.fn()} />)

    expect(screen.getByText(/nobody has confirmed/i)).toBeInTheDocument()
  })

  it('does not cast doubt on a waypoint that came from facility data', () => {
    render(<PoiSheet poi={SHELTER} onClose={vi.fn()} />)

    expect(screen.queryByText(/unverified/i)).not.toBeInTheDocument()
  })

  it('says where the claim came from, in words rather than a source id', () => {
    render(<PoiSheet poi={SHELTER} onClose={vi.fn()} />)

    expect(screen.getByText(/Appalachian Trail Conservancy/)).toBeInTheDocument()
  })

  it('distinguishes an A.T. Community town from the ATC’s own facility data', () => {
    // The two are not interchangeable, and the difference is exactly why one
    // is published at low confidence: a town applied for a designation, which
    // is a proxy for resupply rather than a tagged resupply point.
    render(
      <PoiSheet
        poi={{ ...SHELTER, type: 'resupply', source: 'atc_communities' }}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText(/A\.T\. Community towns/)).toBeInTheDocument()
  })

  it('shows a source it has no wording for rather than hiding the POI’s origin', () => {
    // A release that adds a source should reach a hiker as something, the same
    // call the map makes when it draws an unknown POI type as a neutral pin.
    render(<PoiSheet poi={{ ...SHELTER, source: 'nynjtc_shelters' }} onClose={vi.fn()} />)

    expect(screen.getByText(/nynjtc_shelters/)).toBeInTheDocument()
  })

  it('treats a blank source as no source, not as a source called nothing', () => {
    render(<PoiSheet poi={{ ...SHELTER, source: '  ' }} onClose={vi.fn()} />)

    expect(screen.queryByText(/^From /)).not.toBeInTheDocument()
  })

  it('stays quiet about provenance for a download made before it was carried', () => {
    // Undefined here means "this copy of the data predates the field", not
    // "no source" - and a sheet with one line fewer beats a wrong claim.
    render(<PoiSheet poi={{ ...SHELTER, source: undefined }} onClose={vi.fn()} />)

    expect(screen.queryByText(/^From /)).not.toBeInTheDocument()
  })

  it('closes when asked', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<PoiSheet poi={SHELTER} onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: /close waypoint details/i }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not claim the rest of the screen is inert, because it is not', () => {
    // The map behind this sheet stays live and pannable. Announcing it as a
    // modal would tell a screen-reader user otherwise.
    render(<PoiSheet poi={SHELTER} onClose={vi.fn()} />)

    expect(screen.getByRole('dialog')).not.toHaveAttribute('aria-modal', 'true')
  })
})
