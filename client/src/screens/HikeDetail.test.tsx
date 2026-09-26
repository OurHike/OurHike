// The hike detail (#1290, wireframe `1g`).
//
// What is pinned here is what the screen must not overstate. Two figures
// from two parties, always labelled; a time refused rather than computed
// from an unmeasured climb; a start read off a map's centre saying it was;
// the publisher's prose folded rather than dumped; and a walk logged onto
// the record already there rather than a second one made.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import 'fake-indexeddb/auto'
import { set } from 'idb-keyval'
import { HikeDetail } from './HikeDetail'
import { conditionsCacheKey } from '../lib/conditionsCache'
import { suggestedHikeDetailKey } from '../lib/config'
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
      // Offline, so useHikeDetail (#1473) reaches no network and hands back
      // the fixture's own `detail` untouched. Everything below therefore
      // still tests THIS screen rather than the fetch under it - the split
      // moved where the prose comes from, not what the screen does with it.
      online={false}
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

  it('gains the publisher’s length when the prose lands, having printed without it', async () => {
    // THE ONE THAT CAUGHT IT (#1473). `publishedMiles` is not a SHELF_FIELD,
    // so after the split it arrives with the prose - and this line was still
    // reading it off the shelf record, where it now never is. Every fixture
    // above puts it on `hike.detail` by hand and so passed either way; this
    // is the only one that puts it where a real phone finds it.
    await set(conditionsCacheKey(suggestedHikeDetailKey('50')), {
      document: { id: 'nynjtc_hike_finder:50', publishedMiles: 4.5 },
      storedAt: new Date().toISOString(),
    })
    // No `detail` on the shelf record, which is the post-split shape: the
    // figures are there, the publisher's own number is not.
    show({ id: 'nynjtc_hike_finder:50', detail: undefined })

    // Printed before the read comes back - the phone's own half never waits
    // on the publisher's.
    expect(
      screen.getByText(/measured on the trail lines this phone holds/),
    ).not.toHaveTextContent('says')

    await waitFor(() =>
      expect(
        screen.getByText(/measured on the trail lines this phone holds/),
      ).toHaveTextContent('New York-New Jersey Trail Conference says 4.5 mi'),
    )
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

    const link = screen.getByRole('link', { name: /Read it on their page/ })
    expect(link).toHaveAttribute('href', DETAIL!.url)
    // Beside the app, as every other external link opens: the installed
    // web app is the tab, and navigating it away loses the hike.
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noreferrer')
    expect(screen.queryByText(/Avenza/i)).not.toBeInTheDocument()
  })

  it('renders no source link when the publisher’s URL is not a web page (#1578)', () => {
    // The URL is the publisher's own export, kept as any non-empty string by
    // lib/suggestedHikesData.ts; the screen is where the scheme is checked.
    show({ detail: { ...DETAIL!, url: 'data:text/html,<p>their page</p>' } })

    expect(screen.queryByRole('link', { name: /Read it on their page/ })).toBeNull()
    expect(screen.getByText(/route and words/)).toBeInTheDocument()
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

describe('the publisher’s paper map (#1574)', () => {
  /** NYNJTC as the stewards artifact carries it: the hike finder is one of
   *  its registry keys, the store grants this screen, and one product lists
   *  Harriman on two sheets. */
  const NYNJTC = {
    provider: 'NYNJTC',
    name: 'New York-New Jersey Trail Conference',
    trust: 'authoritative',
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: ['NYNJTC Hike Finder export'],
    keys: ['nynjtc_hike_finder'],
    support: null,
    store: {
      storeUrl: 'https://store.nynjtc.org/collections/maps',
      storeCta: 'Trail Maps',
      storeSurfaces: ['sources_screen', 'hike_detail'],
      paperMaps: [
        {
          handle: 'harriman-bear-mountain-trails-map',
          title: 'Harriman-Bear Mountain Trails Map',
          url: 'https://store.nynjtc.org/products/harriman-bear-mountain-trails-map?utm_source=ourhike',
          sheets: ['118', '119'],
          covers: [],
          sheetCovers: {
            '118': ['Southern Harriman State Park'],
            '119': ['Northern Harriman State Park', 'Bear Mountain State Park'],
          },
        },
      ],
    },
  }
  const IN_HARRIMAN = { ...DETAIL, park: 'Harriman State Park' }

  it('links the park’s sheets to the publisher’s own store product, title verbatim', () => {
    show({ id: 'nynjtc_hike_finder:1', detail: IN_HARRIMAN }, { stewards: [NYNJTC] })

    const link = screen.getByRole('link', { name: 'Harriman-Bear Mountain Trails Map ›' })
    expect(link).toHaveAttribute(
      'href',
      'https://store.nynjtc.org/products/harriman-bear-mountain-trails-map?utm_source=ourhike',
    )
    expect(
      screen.getByText(
        'The park is on sheets 118 and 119 of the New York-New Jersey Trail Conference’s',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/takes no cut and holds no money/)).toBeInTheDocument()
  })

  it('prints no map line for a park no sheet names', () => {
    show({ id: 'nynjtc_hike_finder:1', detail: DETAIL }, { stewards: [NYNJTC] })

    expect(screen.queryByText(/Trails Map ›/)).not.toBeInTheDocument()
    expect(screen.queryByText(/takes no cut/)).not.toBeInTheDocument()
  })

  it('prints no map line when the publisher is not a steward this phone holds', () => {
    show({ id: 'nynjtc_hike_finder:1', detail: IN_HARRIMAN })

    expect(screen.queryByText(/Trails Map ›/)).not.toBeInTheDocument()
  })

  it('prints no map line where the organization has not granted the hike detail', () => {
    const elsewhere = {
      ...NYNJTC,
      store: { ...NYNJTC.store, storeSurfaces: ['sources_screen'] },
    }
    show({ id: 'nynjtc_hike_finder:1', detail: IN_HARRIMAN }, { stewards: [elsewhere] })

    expect(screen.queryByText(/Trails Map ›/)).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Podcast episodes picked for the hike (#1683).

describe('the podcast episodes picked for this hike', () => {
  const EPISODE = {
    spotifyId: '0aBcDeFgHiJkLmNoPqRsTu',
    title: 'The park’s history',
    show: 'A show',
    minutes: 48,
    hikes: ['nynjtc_favorite_hikes:hike-vista-loop-trail'],
    atMiles: [],
  }

  it('is the last thing on the screen, below the provenance (the maintainer, 2026-09-26)', () => {
    const { container } = show({ detail: DETAIL }, { podcastEpisodes: [EPISODE] })

    const body = container.querySelector('.hike-detail__body') as HTMLElement
    const last = body.lastElementChild as HTMLElement
    expect(last.querySelector('.hike-detail__rule')?.textContent).toBe(
      'Listen before you go',
    )
    expect(last.textContent).toContain('The park’s history')
    expect(last.previousElementSibling?.tagName).toBe('FOOTER')
  })

  it('draws no section for a hike nobody picked an episode for', () => {
    show({ detail: DETAIL })
    expect(screen.queryByText('Listen before you go')).not.toBeInTheDocument()
  })
})
