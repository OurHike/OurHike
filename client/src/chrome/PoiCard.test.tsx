import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { PoiCard, type PoiDetail } from './PoiCard'
import { CARD_GAP_PX } from './poiCardPlacement'
import {
  poiColor,
  poiGlyphPath,
  POI_FALLBACK_COLOR,
  POI_PIN_SIZE,
  UNKNOWN_POI_TYPE,
} from '../map/poiIcons'

// WIREFRAMES.md's waypoint detail, which the screen map derives from
// OurHikeValues.md #4 - honesty about uncertainty - as much as from the data.
//
// The line that carries that value is the unverified one. The pin says the
// same thing with a broken rim, which is a channel someone has to have learned
// to read; this is where it is said in words, and only where it is true.
//
// The card floats beside the pin it describes, so alongside the facts there is
// an anchor to test: it projects the POI's own coordinates through the live
// map, follows every camera move, and lets go of the listeners when it closes.

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

/**
 * Content tests pass no map on purpose: with nothing to anchor to, the card
 * renders unpositioned but complete, which is also the honest production
 * behaviour for the instant before the shell has been handed the map.
 */
function renderCard(poi: PoiDetail, onClose = vi.fn()) {
  return render(<PoiCard poi={poi} map={null} onClose={onClose} />)
}

beforeEach(() => {
  resetMapLibreMock()
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('PoiCard', () => {
  it('names the waypoint and what kind of thing it is', () => {
    renderCard(SHELTER)

    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Lean-to' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Shelter')).toBeInTheDocument()
  })

  it('places it on the trail', () => {
    renderCard(SHELTER)

    expect(screen.getByText('mi 2,078.4')).toBeInTheDocument()
  })

  it('says how many the shelter sleeps', () => {
    renderCard({ ...SHELTER, capacity: 8 })

    // "Sleeps 8", not a bare 8: beside a mile, a lone number reads as
    // another distance.
    expect(screen.getByText('Sleeps 8')).toBeInTheDocument()
  })

  it('omits the capacity rather than implying nobody fits', () => {
    // Most POI types have no capacity at all, and ATC's shelter layer does
    // not carry one - the pipeline joins it from a list that leaves some
    // shelters blank on purpose (build_shelter_capacity.py). Absent means
    // unknown, and a hiker choosing whether to push on to the next shelter
    // is better served by silence than by a figure nobody published.
    renderCard({ ...SHELTER, capacity: undefined })

    expect(screen.queryByText(/Sleeps/)).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: SHELTER.name })).toBeInTheDocument()
  })

  it('says what the place is', () => {
    renderCard({
      ...SHELTER,
      description: 'Two-storey log shelter, sleeps 8, with a fireplace. Built 1954.',
    })

    expect(
      screen.getByText('Two-storey log shelter, sleeps 8, with a fireplace. Built 1954.'),
    ).toBeInTheDocument()
  })

  it('omits the description rather than showing an empty line', () => {
    // Only shelters and campsites have one, and a phone that downloaded
    // before the field existed has none at all.
    renderCard({ ...SHELTER, description: undefined })

    expect(screen.getByRole('heading', { name: SHELTER.name })).toBeInTheDocument()
    expect(screen.queryByText(/shelter, sleeps/)).not.toBeInTheDocument()
  })

  it('omits the mile rather than guessing one when the trail lines are missing', () => {
    // The centerline index is a separate download and can legitimately be
    // absent. A shelter with no mile is still worth a card - it just cannot
    // say where along the trail it is.
    renderCard({ ...SHELTER, mile: undefined })

    expect(screen.queryByText(/^mi /)).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: SHELTER.name })).toBeInTheDocument()
  })

  it('gives coordinates precise enough to read out to somebody', () => {
    renderCard(SHELTER)

    expect(screen.getByText(/45\.47320, -69\.11830/)).toBeInTheDocument()
  })

  it('writes coordinates with a plain hyphen, so they paste into another device', () => {
    renderCard(SHELTER)

    expect(screen.queryByText(/−/)).not.toBeInTheDocument()
  })

  it('says in words when nobody has confirmed the waypoint exists', () => {
    renderCard({ ...SHELTER, confidence: 'low' })

    expect(screen.getByText(/nobody has confirmed/i)).toBeInTheDocument()
  })

  it('does not cast doubt on a waypoint that came from facility data', () => {
    renderCard(SHELTER)

    expect(screen.queryByText(/unverified/i)).not.toBeInTheDocument()
  })

  it('says where the claim came from, in words rather than a source id', () => {
    renderCard(SHELTER)

    expect(screen.getByText(/Appalachian Trail Conservancy/)).toBeInTheDocument()
  })

  it('distinguishes an A.T. Community town from the ATC’s own facility data', () => {
    // The two are not interchangeable, and the difference is exactly why one
    // is published at low confidence: a town applied for a designation, which
    // is a proxy for resupply rather than a tagged resupply point.
    renderCard({ ...SHELTER, type: 'resupply', source: 'atc_communities' })

    expect(screen.getByText(/A\.T\. Community towns/)).toBeInTheDocument()
  })

  it('names each of the ATC facility layers as the kind of data it is', () => {
    // Three layers, three sentences, because the card's job here is to let a
    // hiker weigh the claim - and "the ATC's privy data" and "the ATC's list
    // of A.T. Community towns" are not the same kind of statement. The raw
    // id would be a fourth thing again: honest, and unreadable.
    const sources = [
      ['atc_viewpoints', /vista data/],
      ['atc_parking', /parking data/],
      ['atc_privies', /privy data/],
    ] as const

    for (const [source, wording] of sources) {
      const { unmount } = renderCard({ ...SHELTER, source })
      expect(screen.getByText(wording)).toBeInTheDocument()
      unmount()
    }
  })

  it('shows a source it has no wording for rather than hiding the POI’s origin', () => {
    // A release that adds a source should reach a hiker as something, the same
    // call the map makes when it draws an unknown POI type as a neutral pin.
    renderCard({ ...SHELTER, source: 'nynjtc_shelters' })

    expect(screen.getByText(/nynjtc_shelters/)).toBeInTheDocument()
  })

  it('treats a blank source as no source, not as a source called nothing', () => {
    renderCard({ ...SHELTER, source: '  ' })

    expect(screen.queryByText(/^From /)).not.toBeInTheDocument()
  })

  it('stays quiet about provenance for a download made before it was carried', () => {
    // Undefined here means "this copy of the data predates the field", not
    // "no source" - and a card with one line fewer beats a wrong claim.
    renderCard({ ...SHELTER, source: undefined })

    expect(screen.queryByText(/^From /)).not.toBeInTheDocument()
  })

  it('closes when asked', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    renderCard(SHELTER, onClose)

    await user.click(screen.getByRole('button', { name: /close waypoint details/i }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not claim the rest of the screen is inert, because it is not', () => {
    // The map behind this card stays live and pannable - panning is how the
    // card is used. Announcing it as a modal would tell a screen-reader user
    // otherwise.
    renderCard(SHELTER)

    expect(screen.getByRole('dialog')).not.toHaveAttribute('aria-modal', 'true')
  })
})

describe('the photo slot', () => {
  it('shows the category silhouette when the waypoint has no photo', () => {
    // The placeholder is honest iconography, not a stock photo pretending to
    // be the shelter - and it stays the everyday state: most waypoints have
    // no eligible photo even now that the pipeline can carry imagery.
    renderCard(SHELTER)

    expect(screen.getByTestId('poi-card-placeholder')).toBeInTheDocument()
    expect(screen.queryByTestId('poi-card-photo')).not.toBeInTheDocument()
  })

  it('draws the placeholder in the pins’ own shape language', () => {
    renderCard(SHELTER)

    const path = screen.getByTestId('poi-card-placeholder').querySelector('path')
    // Two subpaths: the shelter's body and the doorway the even-odd fill
    // keeps open - the same silhouette the pin carries.
    expect(path?.getAttribute('d')).toMatch(/^M.*Z.*M.*Z$/)
    expect(path?.getAttribute('fill-rule')).toBe('evenodd')
  })

  it('shows the photo when the data carries one', () => {
    renderCard({ ...SHELTER, photoUrl: 'blob:photo-of-the-lean-to' })

    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute(
      'src',
      'blob:photo-of-the-lean-to',
    )
    expect(screen.queryByTestId('poi-card-placeholder')).not.toBeInTheDocument()
  })

  it('does not let a photo claim to be the waypoint - the name line does that', () => {
    renderCard({ ...SHELTER, photoUrl: 'blob:photo' })

    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('alt', '')
  })

  it('falls back to the placeholder when the photo fails to load', () => {
    // Offline-first app: a photo URL the cache no longer holds is a routine
    // Tuesday, not an error state worth a broken-image glyph over the name.
    renderCard({ ...SHELTER, photoUrl: 'blob:gone' })

    fireEvent.error(screen.getByTestId('poi-card-photo'))

    expect(screen.getByTestId('poi-card-placeholder')).toBeInTheDocument()
    expect(screen.queryByTestId('poi-card-photo')).not.toBeInTheDocument()
  })

  // A shippable Commons photo the way the pipeline publishes one: URL plus
  // the three credit facts and the file page. CC BY/BY-SA photos always
  // arrive with an author - the pipeline enforces that, because the credit
  // is the licence's condition of use.
  const PHOTO = {
    photoUrl: 'blob:photo-of-the-lean-to',
    photoPage: 'https://commons.wikimedia.org/wiki/File:Chairback_Gap_Lean-to.jpg',
    photoAuthor: 'A. Hiker',
    photoLicense: 'CC BY-SA 4.0',
    photoTaken: '2025-06-18',
  }

  it('credits the photographer, licence and month, linking to the file page', () => {
    // The credit is load-bearing: CC BY/BY-SA photos are only OurHike's to
    // show while the attribution shows with them, same deal as the map's
    // ODbL line. The month is this app's own honesty rule - a photo's age
    // is a fact the hiker gets, not a detail to hide.
    renderCard({ ...SHELTER, ...PHOTO })

    const credit = screen.getByRole('link', {
      name: 'Photo: A. Hiker · CC BY-SA 4.0 · Jun 2025',
    })
    expect(credit).toHaveAttribute('href', PHOTO.photoPage)
    // A new tab, and no opener handle into the running map.
    expect(credit).toHaveAttribute('target', '_blank')
    expect(credit).toHaveAttribute('rel', 'noreferrer')
  })

  it('credits a public-domain photo by licence alone when nobody is named', () => {
    // Public domain and CC0 photos legitimately have no author to credit -
    // the line shortens rather than printing a blank where a name would go.
    renderCard({
      ...SHELTER,
      photoUrl: 'blob:pd-photo',
      photoPage: 'https://commons.wikimedia.org/wiki/File:PD.jpg',
      photoLicense: 'Public domain',
    })

    expect(screen.getByRole('link', { name: 'Photo: Public domain' })).toBeInTheDocument()
  })

  it('says nothing under a photo that carries no credit facts at all', () => {
    // No pipeline path produces a photo without credit facts today (the
    // fetch rejects CC files with no author and always records a licence),
    // so this is the component's own contract, not a data state: a bare
    // photoUrl renders no credit line, because "Photo:" with nothing after
    // it would be noise pretending to be attribution.
    renderCard({ ...SHELTER, photoUrl: 'blob:bare' })

    expect(screen.queryByText(/^Photo:/)).not.toBeInTheDocument()
  })

  it('drops the credit with the photo when the photo fails to load', () => {
    // The credit is a fact about a photo on screen. Once the slot falls back
    // to the placeholder there is nothing being used that needs crediting -
    // and a credit under the silhouette would claim the glyph was somebody's
    // photograph.
    renderCard({ ...SHELTER, ...PHOTO })

    fireEvent.error(screen.getByTestId('poi-card-photo'))

    expect(screen.queryByText(/^Photo:/)).not.toBeInTheDocument()
  })

  it('gives a category this build has never heard of the neutral pin’s own look', () => {
    // Same call the map makes when it draws the pin itself: a later import
    // adding a type should reach the card as the placeholder diamond on the
    // fallback accent, not a blank slot behind a client release.
    renderCard({ ...SHELTER, type: 'hot_springs' })

    const card = screen.getByRole('dialog', { name: /waypoint/i })
    expect(card.style.getPropertyValue('--poi-accent')).toBe(POI_FALLBACK_COLOR)
    expect(
      screen.getByTestId('poi-card-placeholder').querySelector('path')?.getAttribute('d'),
    ).toBe(poiGlyphPath(UNKNOWN_POI_TYPE))
  })
})

describe('anchoring to the pin', () => {
  /** A live mock map, typed the way the component takes it. */
  function liveMap(): { mock: MockMap; map: MapLibreMap } {
    const mock = new MockMap({})
    return { mock, map: mock as unknown as MapLibreMap }
  }

  it('projects the POI’s own coordinates, not some other point', () => {
    const { mock, map } = liveMap()

    render(<PoiCard poi={SHELTER} map={map} onClose={vi.fn()} />)

    expect(mock.projectCalls).toContainEqual([SHELTER.lon, SHELTER.lat])
  })

  it('floats the card above the projected pin', () => {
    const { mock, map } = liveMap()
    // The mock's projection is test-settable; a fixed point makes the
    // expected transform a hand-checkable sum rather than a re-derivation.
    mock.projection = () => ({ x: 200, y: 300 })

    render(<PoiCard poi={SHELTER} map={map} onClose={vi.fn()} />)

    // jsdom measures the card (and canvas) at zero, so placement degrades to
    // "centred on the pin, above it": x stays 200, y clears half a pin plus
    // the gap. poiCardPlacement.test.ts covers the real-size behaviour.
    const expectedTop = 300 - POI_PIN_SIZE / 2 - CARD_GAP_PX
    expect(screen.getByRole('dialog', { name: /waypoint/i })).toHaveStyle({
      transform: `translate(200px, ${expectedTop}px)`,
    })
  })

  it('rides along when the camera moves', () => {
    const { mock, map } = liveMap()
    mock.projection = () => ({ x: 200, y: 300 })

    render(<PoiCard poi={SHELTER} map={map} onClose={vi.fn()} />)

    // The pan: the same pin now projects somewhere else, and MapLibre says so
    // with a 'move' - the exact order the real map delivers them in.
    mock.projection = () => ({ x: 150, y: 260 })
    act(() => {
      mock.emit('move')
    })

    const expectedTop = 260 - POI_PIN_SIZE / 2 - CARD_GAP_PX
    expect(screen.getByRole('dialog', { name: /waypoint/i })).toHaveStyle({
      transform: `translate(150px, ${expectedTop}px)`,
    })
  })

  it('re-projects on a move that changed nothing, and keeps the same placement', () => {
    // The idle half of riding along: 'move' also fires for camera work that
    // leaves the pin where it was, and the card's answer is the same pixels -
    // asserted against a fresh projection call, so "unchanged" means
    // "recomputed and equal", not "never looked".
    const { mock, map } = liveMap()
    mock.projection = () => ({ x: 200, y: 300 })
    render(<PoiCard poi={SHELTER} map={map} onClose={vi.fn()} />)
    const card = screen.getByRole('dialog', { name: /waypoint/i })
    const before = card.style.transform
    const projections = mock.projectCalls.length

    act(() => {
      mock.emit('move')
    })

    expect(mock.projectCalls.length).toBeGreaterThan(projections)
    expect(card.style.transform).toBe(before)
  })

  it('re-anchors when the poi changes without a remount', () => {
    const { mock, map } = liveMap()
    const { rerender } = render(<PoiCard poi={SHELTER} map={map} onClose={vi.fn()} />)

    rerender(
      <PoiCard
        poi={{ ...SHELTER, id: 'other', lon: -70, lat: 44 }}
        map={map}
        onClose={vi.fn()}
      />,
    )

    expect(mock.projectCalls).toContainEqual([-70, 44])
  })

  it('lets go of the map when it closes, so a dismissed card is not still listening', () => {
    const { mock, map } = liveMap()
    const { unmount } = render(<PoiCard poi={SHELTER} map={map} onClose={vi.fn()} />)

    unmount()

    expect(mock.listenerCount('move')).toBe(0)
    expect(mock.listenerCount('resize')).toBe(0)
  })

  it('renders complete but unanchored with no map, rather than not at all', () => {
    // The shell learns about the map from an effect, so a card can exist an
    // instant before the map does - and a readable, closable card at the
    // canvas origin beats a missing one.
    renderCard(SHELTER)

    const card = screen.getByRole('dialog', { name: /waypoint/i })
    expect(card.style.transform).toBe('')
  })
})

describe('PoiCard photo gallery', () => {
  // Three photos of one shelter, the way ATC's layers actually publish them:
  // same author and licence, different capture dates. 89% of POIs carrying a
  // photo carry more than one (#471).
  const GALLERY = [
    { url: 'blob:one', author: 'ATC', license: '© ATC', taken: '2016-09-12' },
    { url: 'blob:two', author: 'ATC', license: '© ATC', taken: '2016-09-13' },
    { url: 'blob:three', author: 'ATC', license: '© ATC', taken: '2017-06-06' },
  ]

  it('shows no controls for a single photo, because there is nowhere to go', () => {
    renderCard({ ...SHELTER, photoUrl: 'blob:only' })

    expect(screen.queryByTestId('poi-card-photo-next')).not.toBeInTheDocument()
    expect(screen.queryByTestId('poi-card-photo-count')).not.toBeInTheDocument()
  })

  it('steps to the next photo and says where you are', () => {
    renderCard({ ...SHELTER, photoUrl: 'blob:one', photos: GALLERY })

    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:one')
    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('1 of 3')

    fireEvent.click(screen.getByTestId('poi-card-photo-next'))

    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:two')
    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('2 of 3')
  })

  it('wraps at both ends rather than offering a control that does nothing', () => {
    renderCard({ ...SHELTER, photoUrl: 'blob:one', photos: GALLERY })

    fireEvent.click(screen.getByTestId('poi-card-photo-prev'))
    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:three')

    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:one')
  })

  it('moves the credit with the photo, because the licence is owed per photograph', () => {
    // The card must never show one photo over another photo's credit line.
    renderCard({ ...SHELTER, photoUrl: 'blob:one', photos: GALLERY })

    expect(screen.getByText(/Sep 2016/)).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    fireEvent.click(screen.getByTestId('poi-card-photo-next'))

    expect(screen.getByText(/Jun 2017/)).toBeInTheDocument()
    expect(screen.queryByText(/Sep 2016/)).not.toBeInTheDocument()
  })

  it('links the credit to the photo on screen, not to the first one', () => {
    renderCard({
      ...SHELTER,
      photoUrl: 'blob:one',
      photos: [
        {
          url: 'blob:one',
          author: 'ATC',
          page: 'https://drive.google.com/file/d/one/view',
        },
        {
          url: 'blob:two',
          author: 'ATC',
          page: 'https://drive.google.com/file/d/two/view',
        },
      ],
    })

    fireEvent.click(screen.getByTestId('poi-card-photo-next'))

    expect(screen.getByRole('link', { name: /Photo:/ })).toHaveAttribute(
      'href',
      'https://drive.google.com/file/d/two/view',
    )
  })

  it('lets a hiker past a photo that failed to load', () => {
    // Offline-first: photo 2 of 5 missing from the cache must not trap
    // someone on a broken slot with the rest unreachable.
    //
    // This test asserted the opposite until #481 - that the controls
    // DISAPPEAR when a photo fails - while its own comment said they must
    // not trap anyone. The controls were gated on the current photo having
    // rendered, on the reasoning that paging a placeholder leads nowhere;
    // true when every photo has failed, and this fires when the displayed
    // one has, which on a freshly opened card is always the first.
    renderCard({ ...SHELTER, photoUrl: 'blob:one', photos: GALLERY })

    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    fireEvent.error(screen.getByTestId('poi-card-photo'))
    expect(screen.getByTestId('poi-card-placeholder')).toBeInTheDocument()

    // The way out of a bad image, which is the whole point.
    fireEvent.click(screen.getByTestId('poi-card-photo-next'))

    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:three')
    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('3 of 3')
  })

  it('keeps the controls reachable when the very first photo will not load', () => {
    // The common shape of the bug: nothing has been tapped yet, photo 1 is
    // missing from the cache, and every other photograph of the shelter was
    // unreachable behind a placeholder.
    renderCard({ ...SHELTER, photoUrl: 'blob:one', photos: GALLERY })

    fireEvent.error(screen.getByTestId('poi-card-photo'))

    expect(screen.getByTestId('poi-card-placeholder')).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('1 of 3')
    fireEvent.click(screen.getByTestId('poi-card-photo-next'))

    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:two')
  })

  it('starts a different waypoint at its own first photo', () => {
    const { rerender } = render(
      <PoiCard
        poi={{ ...SHELTER, photoUrl: 'blob:one', photos: GALLERY }}
        map={null}
        onClose={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('2 of 3')

    rerender(
      <PoiCard
        poi={{
          ...SHELTER,
          id: 'atc_shelters:other',
          photoUrl: 'blob:one',
          photos: GALLERY,
        }}
        map={null}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('1 of 3')
  })
})

// A shelter, its privy and its campsite are one place with parts, and since
// #524 gave the site one pin the members have had no pin of their own - so the
// strip of chips under the name is the only gesture in the app that reaches
// them (#526, features/POI_SITES.md §5). What is asserted here is that the row
// is a complete picture of the place, that tapping a chip really replaces the
// card rather than revealing a second one, and that the two mechanical traps
// the issue named are actually shut.
describe('the parts of one site', () => {
  // Latitude-only offsets, so the metres on the chips are hand-checkable
  // against the pipeline's own constant (111,320 m per degree) rather than
  // re-derived from the code under test: 0.00036° is 40.1 m and 0.000225° is
  // 25.0 m. poiSites.test.ts owns the formula itself.
  const PRIVY: PoiDetail = {
    id: 'atc_privies:xyz',
    name: 'Chairback Gap Privy',
    type: 'privy',
    lat: 45.47356,
    lon: -69.1183,
    // The everyday case rather than a contrived one: ATC's privy layer is
    // published unverified, which is why the swap has an unverified line to
    // assert on.
    confidence: 'low',
    source: 'atc_privies',
  }

  const CAMPSITE: PoiDetail = {
    id: 'atc_campsites:xyz',
    name: 'Chairback Gap Campsite',
    type: 'campsite',
    lat: 45.473425,
    lon: -69.1183,
    confidence: 'high',
    description: 'Four tent pads below the lean-to.',
  }

  const SITE: readonly PoiDetail[] = [SHELTER, PRIVY, CAMPSITE]

  function renderSite(site: readonly PoiDetail[] = SITE, poi: PoiDetail = SHELTER) {
    return render(<PoiCard poi={poi} site={site} map={null} onClose={vi.fn()} />)
  }

  const chips = () => screen.getAllByTestId('poi-card-chip')

  it('lists every part of the place, the one you are already on included', () => {
    // The issue's own sketch listed the members only, on the reasoning that the
    // anchor is the card you are reading. The maintainer asked for the anchor
    // too, and it earns its place twice: the row is then the whole place rather
    // than the place minus the part you can see, and it is the way back.
    renderSite()

    expect(chips()).toHaveLength(3)
    expect(screen.getByRole('button', { name: 'Shelter' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Privy 40 m' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Campsite 25 m' })).toBeInTheDocument()
  })

  it('puts the pin you tapped first, and says that is where you are', () => {
    renderSite()

    expect(chips()[0]).toHaveAccessibleName('Shelter')
    expect(chips()[0]).toHaveAttribute('aria-current', 'true')
    // Exactly one, or "which part am I reading" has two answers.
    expect(
      chips().filter((chip) => chip.getAttribute('aria-current') === 'true'),
    ).toHaveLength(1)
  })

  it('names the place once, on the strip, rather than on every part', () => {
    // features/POI_SITES.md's open question 5. The heading follows the part on
    // screen because the coordinates under it do; the site's own name goes here,
    // where it costs no height and a screen reader still gets it.
    renderSite()

    expect(
      screen.getByRole('group', { name: 'Parts of Chairback Gap Lean-to' }),
    ).toBeInTheDocument()

    // AND STILL AFTER A TAP, which is the half a first-render assertion cannot
    // see: labelling the group from `shown` rather than from the anchor reads
    // identically on open and then announces "Parts of Chairback Gap Privy"
    // once you are in it - telling a screen-reader user that a privy has parts,
    // which is false about the structure they are navigating, and taking the
    // site's own name off the card entirely. The heading moves; the strip's
    // label is the one thing here that must not.
    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))

    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Privy' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('group', { name: 'Parts of Chairback Gap Lean-to' }),
    ).toBeInTheDocument()
  })

  it('says how far each part is, and puts no distance on the pin itself', () => {
    // "Privy · 40 m" is the design's own chip. The anchor carries no number
    // because "0 m" from itself is not a fact anybody needed.
    renderSite()

    expect(chips()[1]).toHaveTextContent('40 m')
    expect(chips()[2]).toHaveTextContent('25 m')
    expect(chips()[0]).not.toHaveTextContent(/m$/)
  })

  it('carries the same icon the map draws for each part', () => {
    // One copy of the pin, which is the rule map/MapIcon.tsx is built on: a chip
    // that drew its own privy silhouette would drift from the map's the first
    // time either moved, and the chip's whole job is to be recognised.
    renderSite()

    const glyphs = chips().map((chip) => chip.querySelector('path')?.getAttribute('d'))
    expect(glyphs).toEqual([
      poiGlyphPath('shelter'),
      poiGlyphPath('privy'),
      poiGlyphPath('campsite'),
    ])

    // And in the slot that gives it a size. MapIcon's SVG has no intrinsic
    // dimensions, so a chip that asked for the pin without the class gets
    // whatever the flex row decides - which jsdom would render happily and a
    // stylesheet-contract test cannot see, because the rule would still be
    // there with nothing using it.
    for (const chip of chips()) {
      expect(chip.querySelector('svg')).toHaveClass('poi-card__chip-icon')
    }
  })

  it('carries each part’s own rim, broken where nobody has checked', () => {
    // The chip's rim is a fact about ONE privy - which is where it parts company
    // with the legend, whose pins carry no confidence at all because a key says
    // what a category's symbol is. Drop the prop and every chip claims the same
    // confidence: an unverified privy looks surveyed until you tap it, which is
    // the honesty-about-uncertainty channel (OurHikeValues.md #4) this card is
    // built around, silently gone. Assertable because MapIcon gives a verified
    // pin no `stroke-dasharray` attribute at all rather than a solid-looking
    // one - see the comment on `broken` there.
    renderSite()

    const rim = (chip: HTMLElement) => chip.querySelector('.map-icon__halo')

    expect(rim(chips()[1])).toHaveAttribute('stroke-dasharray')
    expect(rim(chips()[0])).not.toHaveAttribute('stroke-dasharray')
    expect(rim(chips()[2])).not.toHaveAttribute('stroke-dasharray')
  })

  it('hangs the strip on the classes its layout rules are written for', () => {
    // test/poiCardChipLayout.test.ts pins two of the issue's requirements as CSS
    // text, because jsdom does no layout: every chip is a 44px gloved-thumb
    // target, and the strip scrolls sideways rather than wrapping - which is what
    // stops it growing a second row and pushing the card, positioned by its own
    // height, over the pin it describes. A rule whose selector matches nothing is
    // as absent as a deleted rule, so that file only means something while these
    // two class names are on these two elements.
    renderSite()

    expect(screen.getByRole('group', { name: /^Parts of/ })).toHaveClass(
      'poi-card__chips',
    )
    for (const chip of chips()) {
      expect(chip).toHaveClass('poi-card__chip')
    }
  })

  it('says out loud that the card changed, and what it changed to', () => {
    // `aria-current` is an ARIA PROPERTY: a screen reader announces it on
    // arrival at the chip, not when it flips - unlike aria-pressed. So without a
    // live region, pressing Enter on "Privy 40 m" moves the heading, the
    // coordinates, the provenance, the unverified sentence and the photograph
    // while the hiker hears nothing at all. Empty on open, because a reader
    // arriving at the card is about to be read the card.
    renderSite()

    // `toBeEmptyDOMElement`, not `toHaveTextContent('')`: the latter asks
    // whether the text CONTAINS the argument, and every string contains the
    // empty one, so it passes against a region already holding the last card's
    // part. That is the shape of vacuous assertion this whole change is about,
    // and it does not get a pass for being on the tidy side of it.
    expect(screen.getByRole('status')).toBeEmptyDOMElement()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))

    expect(screen.getByRole('status')).toHaveTextContent('Chairback Gap Privy')
  })

  it('does not read the last card’s part out over the next card', () => {
    // The other half of that region, and the half a single render cannot show.
    // MapScreen renders this card without a React key, so the region survives a
    // change of subject with its text in it - and a live region whose content is
    // already there when a reader arrives either gets read a second time or
    // announces the previous waypoint's privy as though it were this one's. The
    // announcement is news about a tap; opening a card is not a tap.
    const { rerender } = renderSite()
    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))
    expect(screen.getByRole('status')).toHaveTextContent('Chairback Gap Privy')

    const other: PoiDetail = {
      ...SHELTER,
      id: 'atc_shelters:other',
      name: 'Cloud Pond Lean-to',
    }
    rerender(<PoiCard poi={other} site={[other, PRIVY]} map={null} onClose={vi.fn()} />)

    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('links each chip to both boxes it swaps', () => {
    // The other half of what role="tab"/role="tabpanel" would have given for
    // free. The objection to a tabpanel is that it could only wrap the text while
    // the photo above it changed silently - it does not reach `aria-controls`,
    // which takes an ID-reference LIST, so both regions are named and the claim
    // is honest.
    renderSite()

    for (const chip of chips()) {
      const controlled = (chip.getAttribute('aria-controls') ?? '').split(' ')

      expect(controlled).toHaveLength(2)
      expect(document.getElementById(controlled[0])).toHaveClass('poi-card__media')
      expect(document.getElementById(controlled[1])).toHaveClass('poi-card__body')
    }
  })

  it('swaps the card to the part you tapped', () => {
    renderSite()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))

    // Its own name, its own coordinates, its own provenance, and its own
    // unverified line - the privy's, not the shelter's.
    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Privy' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/45\.47356, -69\.11830/)).toBeInTheDocument()
    expect(screen.getByText(/privy data/)).toBeInTheDocument()
    expect(screen.getByText(/nobody has confirmed/i)).toBeInTheDocument()

    // And the shelter's facts are gone rather than sitting under the privy's
    // name, which would be the card making exactly the claim it exists not to.
    expect(screen.queryByRole('heading', { name: SHELTER.name })).not.toBeInTheDocument()
    expect(screen.queryByText('mi 2,078.4')).not.toBeInTheDocument()
    expect(screen.queryByText(/45\.47320/)).not.toBeInTheDocument()

    // The row follows: "the one you are on" has to move, or the strip is
    // describing a card that is no longer there.
    expect(screen.getByRole('button', { name: 'Privy 40 m' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Shelter' })).toHaveAttribute(
      'aria-current',
      'false',
    )
  })

  it('keeps measuring the distances from the pin as you tap around', () => {
    // The row's numbers are offsets from the site's one pin, not from whichever
    // chip was tapped last. Measuring from the open part would rewrite every
    // other number on every tap - churn in a strip meant to be read at a glance,
    // and a change of the strip's own width while a thumb is on it.
    renderSite()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))

    expect(screen.getByRole('button', { name: 'Campsite 25 m' })).toBeInTheDocument()
  })

  it('shows the tapped part in its own accent, placeholder and all', () => {
    renderSite()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))

    const card = screen.getByRole('dialog', { name: /waypoint/i })
    expect(card.style.getPropertyValue('--poi-accent')).toBe(poiColor('privy'))
    expect(
      screen.getByTestId('poi-card-placeholder').querySelector('path')?.getAttribute('d'),
    ).toBe(poiGlyphPath('privy'))
  })

  it('renders one part, not three hidden with CSS', () => {
    // screens/Tabs.tsx's rule, and the reason it carries here: three galleries
    // rendered and two hidden would put six "Previous photo"/"Next photo"
    // buttons in the tab order, announcing controls for photographs of a privy
    // nobody has asked to see.
    renderSite([
      { ...SHELTER, photos: [{ url: 'blob:s1' }, { url: 'blob:s2' }] },
      { ...PRIVY, photos: [{ url: 'blob:p1' }, { url: 'blob:p2' }] },
      { ...CAMPSITE, photos: [{ url: 'blob:c1' }, { url: 'blob:c2' }] },
    ])

    expect(screen.getAllByTestId('poi-card-photo-count')).toHaveLength(1)
    expect(screen.queryAllByRole('button', { name: /next photo/i })).toHaveLength(1)
    expect(screen.queryAllByRole('button', { name: /previous photo/i })).toHaveLength(1)
    // The other parts' text is absent too, not merely invisible.
    expect(
      screen.queryByText('Four tent pads below the lean-to.'),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:s1')
  })

  it('starts the part you tapped at its own first photo', () => {
    // The mirror of "starts a different waypoint at its own first photo".
    // Paging to photo 2 of the shelter and then tapping the privy must not open
    // the privy on its second photograph - the count would be honest and the
    // choice of image would be the last place's.
    renderSite([
      {
        ...SHELTER,
        photos: [{ url: 'blob:s1' }, { url: 'blob:s2' }, { url: 'blob:s3' }],
      },
      { ...PRIVY, photos: [{ url: 'blob:p1' }, { url: 'blob:p2' }] },
    ])

    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:s2')

    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))

    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('1 of 2')
    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:p1')
  })

  it('gets you back to the pin you tapped', () => {
    // Without this the anchor chip is decoration: tapping into a member would
    // be a one-way trip, and closing and re-tapping the pin the only way out.
    renderSite()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))
    fireEvent.click(screen.getByRole('button', { name: 'Shelter' }))

    expect(screen.getByRole('heading', { name: SHELTER.name })).toBeInTheDocument()
    expect(screen.getByText('mi 2,078.4')).toBeInTheDocument()
    expect(chips()[0]).toHaveAttribute('aria-current', 'true')
    expect(screen.queryByText(/nobody has confirmed/i)).not.toBeInTheDocument()
  })

  it('opens whatever the shell selected, not the part you were last reading', () => {
    // MapScreen renders this card without a React key, so the selection state
    // survives a change of subject and has to be reset on it.
    //
    // The case that needs the reset rather than the `?? poi` fallback is a new
    // subject whose site still CONTAINS the part you were on - one site
    // re-resolved around a different point of it, which is what search opening a
    // privy's own card will do (#527). The fallback covers the other direction,
    // where the stale id is not in the new site at all, and it covers it on the
    // very first render rather than one commit later.
    const { rerender } = renderSite()
    fireEvent.click(screen.getByRole('button', { name: 'Campsite 25 m' }))
    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Campsite' }),
    ).toBeInTheDocument()

    rerender(<PoiCard poi={PRIVY} site={SITE} map={null} onClose={vi.fn()} />)

    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Privy' }),
    ).toBeInTheDocument()

    // And the other direction: a different place entirely, whose site holds
    // nothing the card was showing.
    const other: PoiDetail = {
      ...SHELTER,
      id: 'atc_shelters:other',
      name: 'Cloud Pond Lean-to',
    }
    rerender(<PoiCard poi={other} site={[other]} map={null} onClose={vi.fn()} />)

    expect(
      screen.getByRole('heading', { name: 'Cloud Pond Lean-to' }),
    ).toBeInTheDocument()
  })

  it('gives a waypoint in no site no chip row at all', () => {
    // A phone that downloaded before #523 published the grouping has no site
    // keys on anything, and most POIs have none after it either. Those cards
    // must be exactly the cards they were.
    renderCard(SHELTER)

    expect(screen.queryAllByTestId('poi-card-chip')).toHaveLength(0)
    expect(screen.queryByRole('group')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: SHELTER.name })).toBeInTheDocument()
  })

  it('offers no strip for a site with nothing else at it', () => {
    // A shelter whose privy is not in this download. One chip is a control that
    // leads to the card it is already on.
    renderSite([SHELTER])

    expect(screen.queryAllByTestId('poi-card-chip')).toHaveLength(0)
  })

  it('measures the card again when the chip changes, without moving off the pin', () => {
    // The trap the issue named. usePinAnchor reads the card's height inside a
    // listener that only fires on a camera move, and tapping a chip is not one -
    // so without the shown part in its dependencies the placement keeps the
    // height of the part the hiker just left until the next pan, and a card
    // placed below its pin by a stale height sits on top of it.
    //
    // The second assertion is the other half, and it is why `shown` is a
    // dependency rather than the projected point: the privy has no pin since
    // #524, so a card that followed it would hang off blank map.
    const mock = new MockMap({})
    const map = mock as unknown as MapLibreMap
    render(<PoiCard poi={SHELTER} site={SITE} map={map} onClose={vi.fn()} />)
    const projections = mock.projectCalls.length

    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))

    expect(mock.projectCalls.length).toBeGreaterThan(projections)
    expect(mock.projectCalls.at(-1)).toEqual([SHELTER.lon, SHELTER.lat])
    expect(mock.projectCalls).not.toContainEqual([PRIVY.lon, PRIVY.lat])
  })

  it('hangs off the part that is carrying the pin, not off the anchor', () => {
    // REACHABLE TODAY, through #607/#609. Hide shelters in the legend and a site
    // gives its pin back to its highest-priority drawn member, so the feature
    // map/poiLayers.ts writes carries the PRIVY's id and a tap selects the privy.
    // The shelter has nothing drawn at it at that moment.
    //
    // So the positional facts follow `poi` - the point the shell selected, which
    // is by construction the one with the pin - and not `site[0]`. Keying them on
    // the anchor would hang the card off the hidden shelter, 40 m away here and a
    // median 42 m on the trail: 11 px at z14, 165 px at z18, and the mild form of
    // the spiderfying features/POI_SITES.md refuses. The distances follow for the
    // same reason - they are offsets from the pin the hiker can see - so from the
    // privy the campsite is 15 m, not the 25 m it is from the shelter.
    //
    // The anchor still names the place, because that is the site's identity
    // rather than a position; the group's label is asserted elsewhere.
    const mock = new MockMap({})
    render(
      <PoiCard
        poi={PRIVY}
        site={SITE}
        map={mock as unknown as MapLibreMap}
        onClose={vi.fn()}
      />,
    )

    expect(mock.projectCalls).toContainEqual([PRIVY.lon, PRIVY.lat])
    expect(mock.projectCalls).not.toContainEqual([SHELTER.lon, SHELTER.lat])

    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Privy' }),
    ).toBeInTheDocument()
    // No number on the pin's own chip - "0 m" from itself was never a fact
    // anybody needed - and the other two measured from it.
    expect(screen.getByRole('button', { name: 'Privy' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Shelter 40 m' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Campsite 15 m' })).toBeInTheDocument()
  })
})
