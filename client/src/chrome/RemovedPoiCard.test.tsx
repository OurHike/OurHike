import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RemovedPoiCard } from './RemovedPoiCard'
import { whatHappened, retiredWhen } from './removedPoiText'
import type { Tombstone } from '../lib/poiIdentity'

// The card a place gets after it stops existing (#831, POI_IDENTITY.md §4).
//
// What this replaces is not an error message — it is NOTHING. A stored anchor
// pointing at a retired id renders no card at all today, so a hiker whose
// photos are on a water point ATC dropped last September taps it and the app
// appears to ignore them.
//
// The test that matters most is the one about the sentence. #831 and §4 both
// say the copy "cannot hard-code 'no longer in ATC's data'", because the real
// tombstones come from two sources and one of them is not the ATC — so a
// hard-coded sentence would be a false statement about a share of every card
// this will ever draw.

function stone(over: Partial<Tombstone> = {}): Tombstone {
  return {
    id: 'atc_csi:gone',
    poiType: 'water',
    source: 'atc_csi',
    retired: '2026-08-19',
    lon: -77.5121,
    lat: 39.9367,
    name: 'Water near Punchbowl Shelter',
    ...over,
  }
}

afterEach(cleanup)

describe('what happened to this place', () => {
  it('names the source the row actually carries', () => {
    render(<RemovedPoiCard tombstone={stone()} onClose={vi.fn()} />)

    expect(
      screen.getByText(/distance-to-water measurements/i, { exact: false }),
    ).toBeTruthy()
  })

  it('does not say ATC about a place that was never ATC’s', () => {
    // opentrail.org is one of the two sources producing real tombstones, and
    // it is not the Appalachian Trail Conservancy. This is the assertion the
    // issue asks for by name.
    render(
      <RemovedPoiCard tombstone={stone({ source: 'opentrail_at' })} onClose={vi.fn()} />,
    )

    expect(screen.getByText(/opentrail\.org/i, { exact: false })).toBeTruthy()
    expect(screen.queryByText(/Appalachian Trail Conservancy/i)).toBeNull()
  })

  it('falls back to the raw id for a source this build has never heard of', () => {
    // A release that adds a source should still show a hiker something — the
    // same call sourceLabel already makes for the live card.
    expect(whatHappened(stone({ source: 'nps_facilities' }))).toContain('nps_facilities')
  })

  it('says when, in words rather than a stamp', () => {
    expect(retiredWhen('2026-08-19')).toBe('August 19, 2026')
  })

  it('shows the raw value rather than "Invalid Date" for an unparseable stamp', () => {
    // Not expected — the pipeline writes a release date — but rendering
    // "Invalid Date" on the card that exists to explain a disappearance would
    // be the second confusing thing in a row.
    expect(retiredWhen('whenever')).toBe('whenever')
  })
})

describe('when nothing took its place', () => {
  it('says so, rather than offering somewhere near', () => {
    // Every one of the 93 real tombstones is this case today. The resolver
    // refuses to guess a successor; the card must not undo that by pointing
    // at a neighbour.
    render(<RemovedPoiCard tombstone={stone()} onClose={vi.fn()} />)

    expect(screen.getByText(/nothing took its place/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /^open /i })).toBeNull()
  })

  it('tells the hiker their own content is not gone with it', () => {
    render(<RemovedPoiCard tombstone={stone()} onClose={vi.fn()} />)

    expect(screen.getByText(/still yours and still on this phone/i)).toBeTruthy()
  })
})

describe('when upstream merged it into somewhere', () => {
  it('names where it went and offers a way there', async () => {
    const onOpenSuccessor = vi.fn()
    render(
      <RemovedPoiCard
        tombstone={stone()}
        successorName="Rocky Run Shelters"
        onOpenSuccessor={onOpenSuccessor}
        onClose={vi.fn()}
      />,
    )

    // The name appears twice on purpose — in the sentence and on the button —
    // so this asks for the sentence specifically.
    expect(screen.getByText(/merged into/i).textContent).toContain('Rocky Run Shelters')
    await userEvent.click(
      screen.getByRole('button', { name: /open rocky run shelters/i }),
    )

    expect(onOpenSuccessor).toHaveBeenCalledTimes(1)
  })

  it('offers the way there rather than following it silently', () => {
    // A hiker who photographed a shelter is owed the knowledge that the place
    // they are looking at is now called something else. Re-anchoring without
    // saying so would make the rename invisible.
    render(
      <RemovedPoiCard
        tombstone={stone()}
        successorName="Rocky Run Shelters"
        onOpenSuccessor={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText(/merged into/i)).toBeTruthy()
    expect(screen.queryByText(/nothing took its place/i)).toBeNull()
  })
})

describe('the rest of the card', () => {
  it('names an unnamed place by its type rather than leaving a blank heading', () => {
    const { name: _name, ...unnamed } = stone()
    render(<RemovedPoiCard tombstone={unnamed as Tombstone} onClose={vi.fn()} />)

    expect(screen.getByRole('heading', { name: /a water source|a water/i })).toBeTruthy()
  })

  it('says where the place was', () => {
    render(<RemovedPoiCard tombstone={stone()} onClose={vi.fn()} />)

    expect(screen.getByText(/39\.9367, -77\.5121/)).toBeTruthy()
  })

  it('closes', async () => {
    const onClose = vi.fn()
    render(<RemovedPoiCard tombstone={stone()} onClose={onClose} />)

    await userEvent.click(screen.getByRole('button', { name: /close/i }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
