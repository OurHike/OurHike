import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { PoiCard, type PoiDetail } from './PoiCard'
import { CARD_GAP_PX } from './poiCardPlacement'
import {
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
    renderCard({ ...SHELTER, photoUrl: 'blob:one', photos: GALLERY })

    fireEvent.click(screen.getByTestId('poi-card-photo-next'))
    fireEvent.error(screen.getByTestId('poi-card-photo'))
    expect(screen.getByTestId('poi-card-placeholder')).toBeInTheDocument()

    // The controls ride the photo, so reaching photo 3 goes back the way we
    // came - and the failure must not stick to it.
    expect(screen.queryByTestId('poi-card-photo-next')).not.toBeInTheDocument()
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
