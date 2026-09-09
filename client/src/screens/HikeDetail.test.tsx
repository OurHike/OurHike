// The hike detail (#1290, wireframe `1g`).
//
// What is pinned here is what the screen must not overstate. Two figures
// from two parties, always labelled; a time refused rather than computed
// from an unmeasured climb; a start read off a map's centre saying it was;
// the publisher's prose folded rather than dumped; and a walk logged onto
// the record already there rather than a second one made.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HikeDetail } from './HikeDetail'
import type { SuggestedHike } from '../lib/suggestedHikes'
import { STANDARD_PACE } from '../lib/pace'

// This project does not run Vitest with `globals: true`, so Testing
// Library never registers its own auto-cleanup and each file does it here.
// Without this the second render in a file inherits the first one's DOM and
// every `getByText` finds two of everything.
afterEach(cleanup)

const PACE = STANDARD_PACE

function hike(over: Partial<SuggestedHike> = {}): SuggestedHike {
  return {
    id: 'nynjtc_favorite_hikes:hike-vista-loop-trail',
    name: 'Vista Loop Trail',
    miles: 3.61,
    difficulty: 'moderate-strenuous',
    author: { kind: 'club', name: 'New York-New Jersey Trail Conference' },
    segments: [
      [
        { coord: [-74.18, 41.07], poiId: null },
        { coord: [-74.19, 41.08], poiId: null },
      ],
    ],
    ...over,
  }
}

const DETAIL: SuggestedHike['detail'] = {
  url: 'https://www.nynjtc.org/hike/hike-vista-loop-trail/',
  publishedMiles: 4.5,
  overview: ['A well-rounded loop with three viewpoints.'],
  description: ['Start at the kiosk.', 'Turn right at the pond.', 'Climb to Hawk Rock.'],
  publication: {
    submittedBy: 'Daniel Chazin',
    submittedOn: '2016-08-24',
    verifiedOn: '2021-08-15',
  },
  start: { lat: 41.077853, lon: -74.187596, basis: 'marker' },
  routeType: 'Loop',
  park: 'Ramapo Valley County Reservation',
  trails: ['Vista Loop Trail'],
  hikerNote: 'The turnaround sits where their description puts it, not at a junction.',
}

function show(over: Partial<SuggestedHike> = {}, props: Record<string, unknown> = {}) {
  return render(
    <HikeDetail
      hike={hike(over)}
      pace={PACE}
      units="imperial"
      onBack={vi.fn()}
      {...props}
    />,
  )
}

describe('the two figures, which are allowed to disagree', () => {
  it('prints the publisher’s own length beside this phone’s, each named', () => {
    show({ detail: DETAIL })

    expect(screen.getByText(/3\.6 mi/)).toBeInTheDocument()
    expect(
      screen.getByText(/measured on the trail lines this phone holds/),
    ).toHaveTextContent('New York-New Jersey Trail Conference says 4.5 mi')
  })

  it('says only whose the measurement is when the publisher stated no length', () => {
    show({ detail: { ...DETAIL, publishedMiles: undefined } })

    const line = screen.getByText(/measured on the trail lines this phone holds/)
    expect(line).not.toHaveTextContent('says')
  })

  it('refuses a time rather than pricing an unmeasured climb as flat ground', () => {
    show({ detail: DETAIL })

    expect(screen.getByText(/no time — climb unmeasured/)).toBeInTheDocument()
  })

  it('prices the walk once the climb is there', () => {
    show({ climb: { gainFt: 720, lossFt: 720 }, detail: DETAIL })

    expect(screen.queryByText(/no time — climb unmeasured/)).not.toBeInTheDocument()
    expect(screen.getByText(/\+720 ft/)).toBeInTheDocument()
  })

  it('shows the reviewed note about how this route differs from their page', () => {
    show({ detail: DETAIL })

    expect(
      screen.getByText(
        'The turnaround sits where their description puts it, not at a junction.',
      ),
    ).toBeInTheDocument()
  })
})

describe('getting there', () => {
  it('offers directions to the publisher’s own coordinates, and says what that opens', () => {
    show({ detail: DETAIL })

    expect(screen.getByRole('link', { name: /Directions/ })).toHaveAttribute(
      'href',
      'geo:41.077853,-74.187596',
    )
    expect(screen.getByText(/Nothing here plans the drive/)).toBeInTheDocument()
  })

  it('says when the start was read off a map’s centre rather than a placed pin', () => {
    show({
      detail: { ...DETAIL, start: { lat: 40.96, lon: -73.92, basis: 'map_centre' } },
    })

    expect(screen.getByText(/rather than a placed pin/)).toBeInTheDocument()
  })

  it('says nothing about a start the publisher never gave', () => {
    show({ detail: { ...DETAIL, start: undefined } })

    expect(screen.queryByRole('link', { name: /Directions/ })).not.toBeInTheDocument()
  })
})

describe('the publisher’s words', () => {
  it('folds the turn-by-turn behind a button, and opens the whole of it', async () => {
    const user = userEvent.setup()
    show({ detail: DETAIL })

    expect(screen.getByText('Start at the kiosk.')).toBeInTheDocument()
    expect(screen.queryByText('Climb to Hawk Rock.')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Read all 3 paragraphs' }))

    expect(screen.getByText('Climb to Hawk Rock.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Read all/ })).not.toBeInTheDocument()
  })

  it('names who wrote it and when they last stood behind it', () => {
    show({ detail: DETAIL })

    expect(screen.getByText(/Written by Daniel Chazin/)).toHaveTextContent(
      'last verified 2021-08-15',
    )
  })

  it('links back to their page and never to Avenza', () => {
    show({ detail: DETAIL })

    expect(screen.getByRole('link', { name: /Read it on their page/ })).toHaveAttribute(
      'href',
      DETAIL!.url,
    )
    expect(screen.queryByText(/Avenza/i)).not.toBeInTheDocument()
  })

  it('says the line on the map is ours, built from their description', () => {
    show({ detail: DETAIL })

    expect(screen.getByText(/not a track anybody walked with a GPS/)).toBeInTheDocument()
  })

  it('draws a route carrying no detail at all, rather than failing', () => {
    show({ detail: undefined })

    expect(screen.getByRole('heading', { name: 'Vista Loop Trail' })).toBeInTheDocument()
    expect(
      screen.queryByRole('link', { name: /Read it on their page/ }),
    ).not.toBeInTheDocument()
  })
})

describe('saving, and walking it again', () => {
  it('offers no save button while nothing can save', () => {
    show({ detail: DETAIL })

    expect(screen.queryByRole('button', { name: /Save|Log a/ })).not.toBeInTheDocument()
  })

  it('saves a route the hiker does not have', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    show({ detail: DETAIL }, { onSave })

    await user.click(screen.getByRole('button', { name: 'Save to my hikes' }))

    expect(onSave).toHaveBeenCalledOnce()
  })

  it('offers a walk, not another copy, once it is already saved', () => {
    show({ detail: DETAIL }, { onSave: vi.fn(), savedWalks: [] })

    expect(screen.getByRole('button', { name: 'Log a walk' })).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Save to my hikes' }),
    ).not.toBeInTheDocument()
  })

  it('offers ANOTHER walk only once there is one to be another of', () => {
    show({ detail: DETAIL }, { onSave: vi.fn(), savedWalks: ['2026-03-14'] })

    expect(screen.getByRole('button', { name: 'Log another walk' })).toBeInTheDocument()
  })

  it('says when they last walked it', () => {
    show({ detail: DETAIL }, { onSave: vi.fn(), savedWalks: ['2026-03-14'] })

    expect(screen.getByText(/You walked this on 14 Mar\.$/)).toBeInTheDocument()
  })

  it('counts a second walk in words rather than a number', () => {
    show(
      { detail: DETAIL },
      { onSave: vi.fn(), savedWalks: ['2026-03-14', '2026-01-02'] },
    )

    expect(screen.getByText(/and once before/)).toBeInTheDocument()
  })

  it('counts the rest, without turning the count into a score', () => {
    show(
      { detail: DETAIL },
      { onSave: vi.fn(), savedWalks: ['2026-03-14', '2026-01-02', '2025-11-30'] },
    )

    expect(screen.getByText(/and 2 times before/)).toBeInTheDocument()
  })

  it('offers no map button until the map has a saved record to draw', () => {
    show({ detail: DETAIL }, { onSave: vi.fn() })

    expect(screen.queryByRole('button', { name: 'Open on map' })).not.toBeInTheDocument()
  })

  it('says nothing about walks on a route saved but never logged', () => {
    show({ detail: DETAIL }, { onSave: vi.fn(), savedWalks: [] })

    expect(screen.queryByText(/You walked this/)).not.toBeInTheDocument()
  })

  it('scores nothing, ranks nothing and congratulates nobody', () => {
    show(
      { detail: DETAIL },
      { onSave: vi.fn(), savedWalks: ['2026-03-14', '2026-01-02'] },
    )

    const words = document.body.textContent ?? ''
    for (const forbidden of [
      'streak',
      'record',
      'faster',
      'slower',
      'ahead',
      'behind',
      'best',
    ]) {
      expect(words.toLowerCase()).not.toContain(forbidden)
    }
  })
})

describe('the publisher’s rating', () => {
  it('quotes their word for it, in their own spelling', () => {
    show({ detail: DETAIL })

    expect(screen.getByText('Moderate to Strenuous')).toBeInTheDocument()
  })

  it('shows no badge at all for a route nobody rated', () => {
    show({ difficulty: null, detail: DETAIL })

    expect(screen.queryByText(/Moderate|Easy|Strenuous/)).not.toBeInTheDocument()
  })
})
