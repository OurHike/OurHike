import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MapAttribution } from './MapAttribution'

// The licence-critical property is that every source handed to this component
// is named somewhere in what it renders, in full, whether it is collapsed or
// not - collapsing may cost prominence, it may never cost the credit itself.
//
// Nothing here asserts what a browser hides, and deliberately: jsdom applies
// no UA stylesheet, so a closed `<details>` has all of its content in the
// document and a test that "proved" the collapse would be proving nothing.
// What is asserted instead is the structure that makes the collapse work - the
// summary is a real disclosure, and the credit that has to stay visible is the
// one in it.

afterEach(cleanup)

const LIVE = [
  '© OpenStreetMap contributors',
  'OpenFreeMap © OpenMapTiles',
  'Elevation: USGS 3DEP via AWS Terrain Tiles',
]

describe('MapAttribution', () => {
  it('names every source it was given, collapsed', () => {
    render(<MapAttribution credits={LIVE} />)

    for (const credit of LIVE) {
      expect(screen.getByText(credit, { exact: false })).toBeInTheDocument()
    }
  })

  it('keeps the OSM credit in the summary, where collapsing cannot take it', () => {
    render(<MapAttribution credits={LIVE} />)

    // The summary is the part of a `<details>` that is on screen in both
    // states, so which element holds the ODbL credit is the assertion - not
    // merely that the text is somewhere in the document, which it would be
    // even if it were the first thing collapsing hid.
    expect(screen.getByText(LIVE[0], { exact: false }).tagName).toBe('SUMMARY')
  })

  it('says how many credits are behind the summary rather than just trailing off', () => {
    render(<MapAttribution credits={LIVE} />)

    expect(screen.getByText(/2 more/)).toBeInTheDocument()
  })

  it('does not repeat the summary credit in the list beneath it', () => {
    render(<MapAttribution credits={LIVE} />)

    expect(screen.getAllByRole('listitem')).toHaveLength(LIVE.length - 1)
  })

  it('renders one line with no disclosure where the layout has room for it', () => {
    render(<MapAttribution credits={LIVE} inline />)

    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(screen.getByText(LIVE.join(' · '))).toBeInTheDocument()
  })

  it('does not build a disclosure over a single credit', () => {
    // What an offline background on an empty phone comes to: the trail line
    // and the POIs, and nothing else on screen to credit.
    render(<MapAttribution credits={['© OpenStreetMap contributors']} />)

    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(screen.getByText('© OpenStreetMap contributors')).toBeInTheDocument()
  })

  it('renders nothing rather than an empty strip when there is nothing to credit', () => {
    const { container } = render(<MapAttribution credits={[]} />)

    expect(container).toBeEmptyDOMElement()
  })
})
