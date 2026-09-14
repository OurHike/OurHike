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
  terms: null,
  termsSource: null,
  layers: ['A.T. Centerline', 'A.T. Shelters'],
  keys: [],
}

const OSM = {
  provider: 'OpenStreetMap contributors',
  name: 'OpenStreetMap contributors',
  trust: 'community',
  licence: null,
  attribution: '(c) OpenStreetMap contributors',
  terms: null,
  termsSource: null,
  layers: ['OSM water point sources'],
  keys: [],
}

/** A steward whose block quotes its terms whole — NJDEP's shape, which is the
 *  reason `terms` exists at all: their agreement forbids redistributing the
 *  data without the metadata, so the agreement has to be on the screen the
 *  data is accounted for on. Shortened here; the claim is the mechanism, and
 *  pinning 1,901 characters of somebody else's licence in a test would pin the
 *  fixture rather than the screen. */
const WITH_TERMS = {
  provider: 'NJDEP',
  name: 'New Jersey Department of Environmental Protection',
  trust: 'authoritative',
  licence: 'NJDEP Data Distribution Agreement: reuse permitted on conditions',
  attribution:
    'This (map/publication/report) was developed using NJDEP GIS digital data.',
  terms: 'Terms of Agreement 1. All data is provided, as is.',
  termsSource: 'https://example.invalid/item',
  layers: ['NJ State Park Service Trails'],
  keys: ['njdep_park_trails'],
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
    // donations — OurHike takes no cut and holds no money". The registry now
    // DOES carry donate fields for three of its seven stewards, added on this
    // branch - so the reason changed on 2026-08-27 even though the assertion
    // did not. What is still missing is a rendered link on the card, and that
    // half would be a promise about something not on the screen. See the
    // component's own comment, which carries the full version.
    render(<SourcesSection stewards={BOTH} />)

    expect(screen.queryByText(/donation|donate|money/i)).not.toBeInTheDocument()
  })

  it('counts a steward’s layers without summarising them', () => {
    render(<SourcesSection stewards={[ATC]} />)

    expect(screen.getByText(/2 layers/)).toBeInTheDocument()
  })

  it('carries a steward’s full terms, closed, where their block quotes them', () => {
    // NJDEP's condition 2 in one assertion: the agreement is ON the screen
    // with the data, not summarised into the one-line licence above it. Closed
    // by default, because 1,901 characters open would bury every other
    // organization's card - present and one tap away is what "provided with"
    // asks for.
    render(<SourcesSection stewards={[WITH_TERMS]} />)

    const disclosure = screen.getByText('The full terms')
    expect(disclosure).toBeInTheDocument()
    expect(disclosure.closest('details')).not.toHaveAttribute('open')

    // Verbatim, and reachable: jsdom renders a closed <details>'s children, so
    // this asserts the text is THERE rather than that it is visible — which is
    // the right claim, since the licence condition is about the terms being
    // carried, and the disclosure state is a layout decision above it.
    expect(
      screen.getByText('Terms of Agreement 1. All data is provided, as is.'),
    ).toBeInTheDocument()
    // And where the copy came from, so it can be checked against the
    // steward's own — the only way anybody catches this app's copy drifting.
    expect(screen.getByText(/https:\/\/example\.invalid\/item/)).toBeInTheDocument()
  })

  it('offers no disclosure for a steward whose block quotes nothing', () => {
    // Most stewards record only a short form, and that is not a gap to fill
    // with an empty "The full terms" that opens on nothing.
    render(<SourcesSection stewards={BOTH} />)

    expect(screen.queryByText('The full terms')).not.toBeInTheDocument()
  })
})
