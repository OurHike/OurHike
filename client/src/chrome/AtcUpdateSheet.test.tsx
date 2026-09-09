import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { AtcUpdateSheet } from './AtcUpdateSheet'
import type { AtcUpdate } from '../lib/atcUpdates'
import type { Stewards } from '../lib/stewards'

// features/ATC_TRAIL_UPDATES.md §4 and #461.
//
// This sheet exists because of one sentence: OurHike did not verify this, the
// ATC published it, and those are different statements. Everything below is a
// way of not letting that distinction quietly disappear.

const UPDATE: AtcUpdate = {
  atc_id: 'va-creeper-trail-closure-detour',
  title: 'SW Virginia: VA Creeper Trail Closure/Detour',
  category: 'Closure',
  states: ['VA'],
  start_mile_marker: 476.6,
  end_mile_marker: 485.8,
  obstructs_trail: true,
  updated_at: '2026-07-17T00:00:00Z',
  source_url: 'https://appalachiantrail.org/trail-updates/va-creeper/',
}

const REVIEWED = new Date('2026-08-12T00:00:00Z')

/**
 * The published registry, as `pipeline/export_sources.py` writes it for the
 * ATC (verified against the checked-in `sources.json`, 2026-08-27).
 *
 * Passed rather than stubbed with a literal, because the point of #1083 is
 * that this sheet no longer knows the organization's name - it looks it up.
 * A test that hard-coded the string here would pass whether or not the lookup
 * happened, which is exactly the thing being changed.
 */
const STEWARDS: Stewards = [
  {
    provider: 'ATC',
    name: 'Appalachian Trail Conservancy',
    trust: null,
    licence: '© ATC, used with permission',
    attribution: null,
    layers: ['ATC Trail Updates'],
    keys: ['atc_trail_updates'],
  },
]

afterEach(cleanup)

describe('whose claim this is', () => {
  it('names the Appalachian Trail Conservancy on the notice itself', () => {
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    // Three places now, not one: the attribution line, the link, and the
    // disclaimer all read the name off the registry since #1083, where two of
    // them used to spell "ATC". `getAllByText` rather than a narrower matcher
    // because the point of the case is that the org is named, not where.
    expect(screen.getAllByText(/Appalachian Trail Conservancy/).length).toBeGreaterThan(0)
  })

  it('says plainly that OurHike has not checked the trail', () => {
    // Without this the sheet reads as OurHike asserting a closure it never
    // verified, which misrepresents the ATC as much as it misleads the hiker.
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('note')).toHaveTextContent(/not OurHike’s/)
  })

  it('keeps the promise ClosureSheet makes about detours', () => {
    // The one wrong belief that could put somebody somewhere worse than the
    // closed trail is that the app is routing them around it.
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('note')).toHaveTextContent(/does not work out detours/)
  })

  it('shows ATC’s own category rather than a closure reason', () => {
    // `ClosureReason` would render a Detour as "Closed" - a claim ATC did
    // not make.
    render(
      <AtcUpdateSheet
        update={{ ...UPDATE, category: 'Detour' }}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('heading')).toHaveTextContent('Detour')
  })
})

describe('both dates, because there are two', () => {
  it('shows the date ATC last edited the notice', () => {
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText(/updated July 17, 2026/)).toBeInTheDocument()
  })

  it('shows when OurHike last checked ATC’s page, separately', () => {
    // A notice ATC edited yesterday that nobody here has looked at since May
    // is a real state. Showing only one date would hide half of it.
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(
      screen.getByText(
        /OurHike last checked Appalachian Trail Conservancy’s updates on August 12, 2026/,
      ),
    ).toBeInTheDocument()
  })

  it('says it cannot tell rather than inventing a review date', () => {
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={null}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText(/can’t tell when it last checked/)).toBeInTheDocument()
  })

  it('drops ATC’s date rather than rendering an unparseable one', () => {
    // "Updated —" invites the reader to supply their own guess, and an
    // invented date on a safety notice is worse than an absent one.
    render(
      <AtcUpdateSheet
        update={{ ...UPDATE, updated_at: 'not a date' }}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('Appalachian Trail Conservancy')).toBeInTheDocument()
    expect(screen.queryByText(/updated/)).not.toBeInTheDocument()
  })
})

describe('the link, which is the detail', () => {
  it('links out to ATC’s own page', () => {
    // The artifact carries facts and not ATC's prose, so this link is the
    // whole of what a hiker can read about the notice.
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('link')).toHaveAttribute('href', UPDATE.source_url)
  })

  it('opens it in a new tab without handing over the opener', () => {
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('link')).toHaveAttribute('rel', 'noreferrer')
  })

  it('renders no link at all for a javascript: URL', () => {
    // The same rule ClosureSheet applies to `reroute_url`. The pipeline
    // refuses one on the way in too, so this is the second line rather than
    // the only one.
    render(
      <AtcUpdateSheet
        update={{ ...UPDATE, source_url: 'javascript:alert(1)' }}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})

describe('where it is', () => {
  it('gives the mile range to a tenth, with the states', () => {
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('VA · mi 476.6 – 485.8')).toBeInTheDocument()
  })

  it('writes a point notice as one mile', () => {
    render(
      <AtcUpdateSheet
        update={{
          ...UPDATE,
          start_mile_marker: 1503.6,
          end_mile_marker: 1503.6,
          states: ['CT'],
        }}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('CT · mi 1,503.6')).toBeInTheDocument()
  })

  it('closes when asked', () => {
    const onClose = vi.fn()
    render(
      <AtcUpdateSheet
        update={UPDATE}
        reviewedAt={REVIEWED}
        stewards={STEWARDS}
        onClose={onClose}
      />,
    )

    screen.getByRole('button').click()

    expect(onClose).toHaveBeenCalled()
  })
})
