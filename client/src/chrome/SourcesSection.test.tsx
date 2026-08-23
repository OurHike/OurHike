import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { SourcesSection } from './SourcesSection'
import type { Stewards } from '../lib/stewards'

// The sentences are lib/stewards.ts's and pipeline/export_sources.py's; this
// is about the component's own duties - render what a steward recorded, omit
// what it did not, and never compose a claim about somebody else's terms.

const ATC = {
  provider: 'ATC',
  name: 'Appalachian Trail Conservancy',
  trust: null,
  licence: '© ATC, used with permission',
  attribution: null,
  layers: ['A.T. Centerline', 'A.T. Shelters'],
}

const OSM = {
  provider: 'OpenStreetMap contributors',
  name: 'OpenStreetMap contributors',
  trust: 'community',
  licence: null,
  attribution: '(c) OpenStreetMap contributors',
  layers: ['OSM water point sources'],
}

const BOTH: Stewards = [ATC, OSM]

afterEach(cleanup)

describe('the sources section', () => {
  it('names every organization whose data is on the phone', () => {
    render(<SourcesSection stewards={BOTH} />)

    expect(screen.getByText('Appalachian Trail Conservancy')).toBeInTheDocument()
    expect(screen.getByText('OpenStreetMap contributors')).toBeInTheDocument()
  })

  it('renders a licence and an attribution verbatim', () => {
    // Both are conditions somebody agreed to. Neither is this app's wording to
    // adjust, so they are asserted as exact strings.
    render(<SourcesSection stewards={BOTH} />)

    expect(screen.getByText('© ATC, used with permission')).toBeInTheDocument()
    expect(screen.getByText('(c) OpenStreetMap contributors')).toBeInTheDocument()
  })

  it('omits the line a steward did not record, with no placeholder', () => {
    // The ATC records a licence and no attribution; OSM the reverse. Neither
    // gap may render as "unknown", which would be this app making a claim
    // about an organization's terms.
    render(<SourcesSection stewards={BOTH} />)

    expect(screen.queryByText(/unknown/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/not recorded/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/none/i)).not.toBeInTheDocument()
  })

  it('shows a trust tier only where one is recorded', () => {
    render(<SourcesSection stewards={BOTH} />)

    expect(screen.getByText('community')).toBeInTheDocument()
    expect(screen.queryByText('authoritative')).not.toBeInTheDocument()
  })

  it('renders nothing at all when there are no stewards', () => {
    // A phone with nothing downloaded, or a release built before the exporter
    // existed. A heading over an empty list reads as a rendering fault.
    const { container } = render(<SourcesSection stewards={[]} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('offers no control, because there is nothing here to act on', () => {
    const { container } = render(<SourcesSection stewards={BOTH} />)

    expect(container.querySelectorAll('button, input, select, a')).toHaveLength(0)
  })

  it('does not promise anything about donations while no card carries one', () => {
    // The wireframe's framing sentence continues "...and takes its own
    // donations — OurHike takes no cut and holds no money". The registry has
    // no donate fields at all (#932), so that half would be a promise about
    // something not on the screen.
    render(<SourcesSection stewards={BOTH} />)

    expect(screen.queryByText(/donation|donate|money/i)).not.toBeInTheDocument()
  })

  it('counts a steward’s layers without summarising them', () => {
    render(<SourcesSection stewards={[ATC]} />)

    expect(screen.getByText(/2 layers/)).toBeInTheDocument()
  })
})
