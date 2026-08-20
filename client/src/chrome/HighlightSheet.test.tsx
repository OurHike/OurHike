import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { HighlightSheet } from './HighlightSheet'
import type { HighlightDetail } from '../lib/highlightDetail'

// The sentences are lib/highlightDetail.ts's and are tested there; this is the
// component's own two duties - render every line the detail carries, and OMIT
// rather than placeholder the ones it does not (#858).

const FULL: HighlightDetail = {
  heading: 'McAfee Knob',
  subtitle: 'Appalachian Trail · mi 705.6 – 709.1',
  derivedLine: '3.5 mi · 1,740 ft ascent · ≈2 h',
  derivedSourceLine: 'Worked out on your phone from the elevation profile.',
  legLines: [],
  basisLabel: 'On our list',
  basisLine: 'We put this on a list of well-known routes. Editorial, not a measurement.',
  citationLine: 'OurHike, 20 Aug 2026',
  clubLine: 'Maintained by RATC.',
  walkedLine: 'You have walked 2.0 mi of this.',
  cautionLine: null,
  paceRelativeLine: null,
}

const CROSS_TRAIL: HighlightDetail = {
  heading: 'Franconia Ridge Loop',
  subtitle: '3 trails · 8.9 mi',
  // No ascent: the published profile is the A.T.'s, and two of these legs are
  // not on it.
  derivedLine: '8.9 mi',
  // ...and so no provenance line either: what is left is a distance summed
  // from the mileposts, which the profile had no part in.
  derivedSourceLine: null,
  legLines: [
    'Appalachian Trail — 1.7 mi',
    'Falling Waters Trail — 3.2 mi',
    'Old Bridle Path — 4.0 mi',
  ],
  basisLabel: 'On our list',
  basisLine: 'We put this on a list of well-known routes. Editorial, not a measurement.',
  citationLine: null,
  clubLine: null,
  walkedLine: null,
  cautionLine: null,
  paceRelativeLine: null,
}

afterEach(cleanup)

describe('the highlight sheet', () => {
  it('renders every line the detail carries', () => {
    render(<HighlightSheet detail={FULL} onClose={vi.fn()} />)

    expect(screen.getByText('McAfee Knob')).toBeInTheDocument()
    expect(screen.getByText('Appalachian Trail · mi 705.6 – 709.1')).toBeInTheDocument()
    expect(screen.getByText('3.5 mi · 1,740 ft ascent · ≈2 h')).toBeInTheDocument()
    expect(screen.getByText('On our list')).toBeInTheDocument()
    expect(screen.getByText('Maintained by RATC.')).toBeInTheDocument()
    expect(screen.getByText('You have walked 2.0 mi of this.')).toBeInTheDocument()
  })

  it('says the numbers were worked out here rather than published', () => {
    render(<HighlightSheet detail={FULL} onClose={vi.fn()} />)
    expect(
      screen.getByText('Worked out on your phone from the elevation profile.'),
    ).toBeInTheDocument()
  })

  it('lists the legs of a cross-trail walk, and omits them for a single one', () => {
    render(<HighlightSheet detail={CROSS_TRAIL} onClose={vi.fn()} />)
    expect(screen.getByText('Falling Waters Trail — 3.2 mi')).toBeInTheDocument()

    cleanup()
    render(<HighlightSheet detail={FULL} onClose={vi.fn()} />)
    // A single-leg highlight would just repeat its own subtitle.
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })

  it('omits what the detail does not carry rather than placeholdering it', () => {
    render(<HighlightSheet detail={CROSS_TRAIL} onClose={vi.fn()} />)

    expect(screen.queryByText(/Worked out on your phone/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Maintained by/)).not.toBeInTheDocument()
    expect(screen.queryByText(/You have walked/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Unknown|—\s*$/)).not.toBeInTheDocument()
  })

  it('shows one basis chip, never two', () => {
    // Two would read as corroboration - two independent sources agreeing -
    // when they are two different questions with one answer between them.
    render(<HighlightSheet detail={FULL} onClose={vi.fn()} />)
    expect(screen.getAllByText(/On our list|Listed by ATC/)).toHaveLength(1)
  })

  /**
   * #851's line. Naismith cannot see terrain, and Mahoosuc Arm is already
   * published - so when a record carries a caution it has to be impossible to
   * skim past.
   */
  it('shows a caution directly under the numbers it qualifies', () => {
    const notch: HighlightDetail = {
      ...FULL,
      heading: 'Mahoosuc Arm',
      cautionLine:
        'The usual estimate does not fit this one — allow considerably longer.',
    }
    render(<HighlightSheet detail={notch} onClose={vi.fn()} />)

    const caution = screen.getByText(
      'The usual estimate does not fit this one — allow considerably longer.',
    )
    expect(caution).toBeInTheDocument()
    // Immediately after the derived numbers, not down with the provenance: a
    // hiker who reads only the top of the sheet is exactly who it is for.
    const derived = screen.getByText('3.5 mi · 1,740 ft ascent · ≈2 h')
    expect(derived.compareDocumentPosition(caution)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it('shows the pace line directly under the time it qualifies (#880)', () => {
    const adjusted: HighlightDetail = {
      ...FULL,
      derivedLine: '3.5 mi · 1,740 ft ascent · ≈2h 50m',
      paceRelativeLine: 'was ≈2h 10m · 1.3× standard',
    }
    render(<HighlightSheet detail={adjusted} onClose={vi.fn()} />)

    const pace = screen.getByText('was ≈2h 10m · 1.3× standard')
    const derived = screen.getByText('3.5 mi · 1,740 ft ascent · ≈2h 50m')
    expect(derived.compareDocumentPosition(pace)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('shows no pace line at the standard pace', () => {
    render(<HighlightSheet detail={FULL} onClose={vi.fn()} />)
    expect(screen.queryByText(/× standard/)).not.toBeInTheDocument()
  })

  it('shows no caution while no record carries one', () => {
    render(<HighlightSheet detail={FULL} onClose={vi.fn()} />)
    expect(screen.queryByText(/does not fit|allow considerably/)).not.toBeInTheDocument()
  })

  it('closes on the close control', () => {
    const onClose = vi.fn()
    render(<HighlightSheet detail={FULL} onClose={onClose} />)
    screen.getByRole('button', { name: 'Close' }).click()
    expect(onClose).toHaveBeenCalled()
  })

  it('is a dialog, and says what it is about', () => {
    render(<HighlightSheet detail={FULL} onClose={vi.fn()} />)
    expect(screen.getByRole('dialog', { name: 'Worth going to' })).toBeInTheDocument()
  })
})
