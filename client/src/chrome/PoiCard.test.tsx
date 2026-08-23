import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { PoiCard, type PoiDetail } from './PoiCard'
import type { FieldNoteContext } from './FieldNoteSection'
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
function renderPeek(poi: PoiDetail, onClose = vi.fn()) {
  return render(<PoiCard poi={poi} map={null} onClose={onClose} />)
}

/**
 * The same card, pulled open.
 *
 * Since #941 a tapped pin PEEKS - the name, the type, the mile, one condition
 * line and the two answers a hiker standing there wants to give - and the
 * record behind it arrives on one deliberate pull. Nearly every test in this
 * file is about something in that record, so opening the card is part of
 * arranging the test rather than part of what it checks; `renderPeek` above
 * is for the handful that are about the peek itself, and about the anchoring,
 * which only the peek does.
 */
function renderCard(poi: PoiDetail, onClose = vi.fn()) {
  const view = renderPeek(poi, onClose)
  fireEvent.click(screen.getByTestId('poi-card-expand'))
  return view
}

/** Pull open a card some test rendered for itself. */
function open() {
  fireEvent.click(screen.getByTestId('poi-card-expand'))
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
    open()
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
    // Opened again on purpose: a new waypoint peeks, whatever the last one was
    // left doing (#941), so this is the second half of the same assertion -
    // the gallery index resets with the subject and so does the height.
    open()

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
  // Latitude-only offsets, so the distances on the chips are hand-checkable
  // against the pipeline's own constant (111,320 m per degree) rather than
  // re-derived from the code under test: 0.00036° is 40.1 m and 0.000225° is
  // 25.0 m, which the card shows as 131 ft and 82 ft for a hiker who chose
  // Feet. poiSites.test.ts owns the formula and the one conversion.
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

  /** Pulled open, for `renderCard`'s reason: the strip of parts is part of
   *  the record rather than of the peek. A hiker who tapped a shelter pin is
   *  answering a question about the shelter; picking a different part of the
   *  site out of it is the next thing they do, not the first. */
  function renderSite(site: readonly PoiDetail[] = SITE, poi: PoiDetail = SHELTER) {
    const view = render(<PoiCard poi={poi} site={site} map={null} onClose={vi.fn()} />)
    open()
    return view
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
    expect(screen.getByRole('button', { name: 'Privy 131 ft' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Campsite 82 ft' })).toBeInTheDocument()
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
    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))

    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Privy' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('group', { name: 'Parts of Chairback Gap Lean-to' }),
    ).toBeInTheDocument()
  })

  it('says how far each part is, and puts no distance on the pin itself', () => {
    // "Privy · 131 ft" is the design's own chip, in the units this hiker
    // chose. The anchor carries no number because zero from itself is not a
    // fact anybody needed.
    renderSite()

    expect(chips()[1]).toHaveTextContent('131 ft')
    expect(chips()[2]).toHaveTextContent('82 ft')
    expect(chips()[0]).not.toHaveTextContent(/\d/)
  })

  it('says how far in the units the hiker chose', () => {
    // #625. This strip was the single line in the app exempt from the unit
    // standard, printing metres at a hiker who had picked Feet in Settings -
    // held open only because the same distances were also published as prose
    // in metres, and converting one half would have put "131 ft" on a chip
    // above a sentence saying 40 m.
    render(
      <PoiCard poi={SHELTER} site={SITE} map={null} units="metric" onClose={vi.fn()} />,
    )
    open()

    expect(chips()[1]).toHaveTextContent('40 m')
    expect(chips()[2]).toHaveTextContent('25 m')
  })

  it('names what is around the place, in those same units', () => {
    // The other half of the same fix, and the reason the chip could not move
    // alone. The parts arrive as structure - a phrase and a distance in feet -
    // and the card writes the sentence the pipeline used to publish finished.
    const anchor: PoiDetail = {
      ...SHELTER,
      description: 'Two-storey log shelter, sleeps 8, with a fireplace. Built 1954.',
      nearby: [
        { phrase: 'a multi-seat moldering privy', distance_ft: 131.5 },
        { phrase: 'water', distance_ft: 295.3 },
      ],
    }

    const { rerender } = render(
      <PoiCard poi={anchor} site={[anchor, PRIVY]} map={null} onClose={vi.fn()} />,
    )
    open()

    expect(
      screen.getByText(
        'Nearby: a multi-seat moldering privy 132 ft away and water 295 ft.',
      ),
    ).toBeInTheDocument()
    // And the description it sits under is untouched by the swap - two
    // paragraphs, one fact each.
    expect(screen.getByText(/Two-storey log shelter/)).toBeInTheDocument()

    rerender(
      <PoiCard
        poi={anchor}
        site={[anchor, PRIVY]}
        map={null}
        units="metric"
        onClose={vi.fn()}
      />,
    )

    expect(
      screen.getByText('Nearby: a multi-seat moldering privy 40 m away and water 90 m.'),
    ).toBeInTheDocument()
  })

  it('puts the same number on the chip and in the sentence for one pair', () => {
    // The property #625 had to preserve while moving both halves: the chip
    // measures on the phone (from the pin), the sentence carries the pipeline's
    // measurement (from the anchor), and where those are the same point the two
    // must not print two numbers for one privy. Same formula, same constant,
    // rounded once each in the same unit.
    const anchor: PoiDetail = {
      ...SHELTER,
      // What export_poi.py publishes for this pair: 0.00036° of latitude, in
      // feet, unrounded.
      nearby: [{ phrase: 'a multi-seat moldering privy', distance_ft: 131.48 }],
    }

    render(<PoiCard poi={anchor} site={[anchor, PRIVY]} map={null} onClose={vi.fn()} />)
    open()

    expect(chips()[1]).toHaveTextContent('131 ft')
    expect(
      screen.getByText('Nearby: a multi-seat moldering privy 131 ft away.'),
    ).toBeInTheDocument()
  })

  it('says nothing about what is around a part that has nothing around it', () => {
    // Most POIs, and every copy downloaded before the field existed. No empty
    // paragraph either - a gap in the card reads as something failing to load.
    const { container } = renderSite()

    expect(container.querySelector('.poi-card__nearby')).toBeNull()
  })

  it('reads the parts off whichever part the card is showing', () => {
    // A campsite is a member of a shelter's site AND the anchor of its own
    // where there is no shelter, so tapping a chip can move to a waypoint with
    // parts of its own. Reading `nearby` off the pin instead would say the
    // shelter's parts under the campsite's name.
    const campsite: PoiDetail = {
      ...CAMPSITE,
      nearby: [{ phrase: 'a pit privy', distance_ft: 65.6 }],
    }

    render(
      <PoiCard poi={SHELTER} site={[SHELTER, campsite]} map={null} onClose={vi.fn()} />,
    )
    open()
    expect(screen.queryByText(/Nearby:/)).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Campsite 82 ft' }))

    expect(screen.getByText('Nearby: a pit privy 66 ft away.')).toBeInTheDocument()
  })

  it('prints the stated distance for a synthesized water member, never the zero its coordinates measure (#694)', () => {
    // The pipeline synthesizes a water member from ATC's distance-to-water
    // where no real point exists. ATC states how far, never where, so the
    // member sits AT the shelter's own coordinates - and measuring that
    // would print "Water · 0 ft" beside a sentence saying 120 ft, drift on
    // one card in its worst form. The stated figure wins, and needs no
    // conversion to do it: ATC states feet, the artifact publishes feet, and
    // feet is what lib/units.ts formats from (#625).
    const SYNTHESIZED_WATER: PoiDetail = {
      id: 'atc_csi:xyz',
      name: 'Water near Chairback Gap Lean-to',
      type: 'water',
      lat: SHELTER.lat,
      lon: SHELTER.lon,
      confidence: 'low',
      source: 'atc_csi',
      waterDistanceFt: 120,
    }
    renderSite([SHELTER, PRIVY, SYNTHESIZED_WATER])

    expect(screen.getByRole('button', { name: 'Water 120 ft' })).toBeInTheDocument()

    // And a real mapped water point - which carries no stated figure - keeps
    // the measured offset exactly as before: 0.00036° of latitude is 40.1 m,
    // which is 131 ft.
    const REAL_WATER: PoiDetail = {
      id: 'opentrail_at:77',
      name: 'Piped Spring',
      type: 'water',
      lat: SHELTER.lat + 0.00036,
      lon: SHELTER.lon,
      confidence: 'high',
      source: 'opentrail_at',
    }
    cleanup()
    renderSite([SHELTER, PRIVY, REAL_WATER])

    expect(screen.getByRole('button', { name: 'Water 131 ft' })).toBeInTheDocument()

    // Both readings follow the hiker, which is the half #694 could not have:
    // the stated figure and the measured one convert through one formatter.
    cleanup()
    render(
      <PoiCard
        poi={SHELTER}
        site={[SHELTER, SYNTHESIZED_WATER]}
        map={null}
        units="metric"
        onClose={vi.fn()}
      />,
    )
    open()

    expect(screen.getByRole('button', { name: 'Water 37 m' })).toBeInTheDocument()
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

  it('leaves every chip a pin, the one you are reading included', () => {
    // #711 took the words off the unselected chips; this takes them off the
    // selected one too, which is what makes the strip fixed-width again - five
    // 44px chips and four 4px gaps is 236 of the 240 the body has, so the
    // largest site on the trail fits and tapping one no longer resizes the row
    // under the thumb.
    //
    // THE CLASS, not the pixels, because jsdom does no layout: this is the half
    // of the contract src/test/poiCardChipLayout.test.ts cannot see, and that
    // file asserts the half this one cannot - that `visually-hidden` still takes
    // the words out of the layout rather than merely out of sight.
    renderSite()

    const words = (chip: HTMLElement) => chip.querySelector('.poi-card__chip-label')

    for (const chip of chips()) expect(words(chip)).toHaveClass('visually-hidden')
  })

  it('keeps every chip a pin whichever part you tap', () => {
    // The half a first-render assertion cannot see, and the reason this is not
    // "delete the conditional and move on": the words used to follow the
    // selection, so the realistic regression is not the class disappearing but
    // the OLD behaviour surviving a tap - the strip renders correctly until
    // something is pressed, and every first-render test in this file stays
    // green.
    renderSite()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))

    const words = (chip: HTMLElement) => chip.querySelector('.poi-card__chip-label')

    for (const chip of chips()) expect(words(chip)).toHaveClass('visually-hidden')
    expect(chips()[1]).toHaveAttribute('aria-current', 'true')
  })

  it('says which part you are reading, and how far it is, under the strip', () => {
    // WHERE THE CHIP'S WORDS WENT, and the reason taking them off the selected
    // chip costs a sighted hiker nothing. The category was already on this line
    // and the name is in the heading above it; the distance is the one fact that
    // lived only on the chip, so it moves here rather than going away.
    //
    // Asserted on the meta line specifically, not on the card: `getByText` over
    // the whole card would pass on the hidden chip label this change is
    // deliberately keeping in the DOM, which is a test that cannot fail.
    const { container } = renderSite()

    const meta = () => container.querySelector('.poi-card__meta')

    // The pin's own part carries no distance, exactly as its chip never did -
    // the card hangs off that point, and "0 ft away" from the thing you are
    // standing on is noise.
    expect(meta()).toHaveTextContent('Shelter')
    expect(meta()).not.toHaveTextContent('away')

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))

    expect(meta()).toHaveTextContent('Privy')
    expect(meta()).toHaveTextContent('131 ft away')

    // And it follows the selection rather than being written once: the campsite
    // is 82 ft, and a line that kept saying 131 would be the drift this card's
    // whole distance story exists to prevent.
    fireEvent.click(screen.getByRole('button', { name: 'Campsite 82 ft' }))

    expect(meta()).toHaveTextContent('Campsite')
    expect(meta()).toHaveTextContent('82 ft away')
    expect(meta()).not.toHaveTextContent('131 ft')
  })

  it('states the meta line’s distance in the hiker’s own units', () => {
    // The chip's distance was the single line in the app that had to be argued
    // into the hiker's units (#625, features/POI_SITES.md), so moving it is
    // exactly where that could be lost - `partDistance` takes `units` and a
    // caller that stopped passing it would silently print feet to a hiker who
    // chose metres, with every other test here green.
    const { container } = render(
      <PoiCard poi={SHELTER} site={SITE} map={null} units="metric" onClose={vi.fn()} />,
    )
    open()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 40 m' }))

    expect(container.querySelector('.poi-card__meta')).toHaveTextContent('40 m away')
  })

  it('says as much to a screen reader with the words off as with them on', () => {
    // The reason #711 is a small change rather than a risky one, and the thing
    // most easily lost by "simplifying" it: `visually-hidden` rather than
    // `display: none` or dropping the text, so the words stay in the
    // accessibility tree and the buttons keep the names they had. A chip
    // reduced to its pin with nothing else in it is a button whose accessible
    // name is empty - unreachable by name, announced as "button".
    renderSite()

    expect(chips()[1]).toHaveAccessibleName('Privy 131 ft')
    expect(chips()[2]).toHaveAccessibleName('Campsite 82 ft')
    // The pin's own chip too, which is the one being read on a fresh card - so
    // the part a sighted hiker now learns about from the meta line instead is
    // still named on the button itself for anyone who cannot see either.
    expect(chips()[0]).toHaveAccessibleName('Shelter')
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

  it('lets a thumbless hiker reach every part and open one', async () => {
    // NOTHING ELSE HERE TOUCHES THE KEYBOARD. Every other chip test drives
    // `fireEvent.click`, which a `<div role="button" tabindex="-1">` answers
    // exactly as happily as a real button does - so `getByRole('button')` is no
    // evidence at all that a keyboard can get here. Two realistic changes would
    // have kept the whole suite green while breaking it: a refactor to a div with
    // an onClick, and the roving `tabindex` from screens/Tabs.tsx, which this
    // card's own comment invites by pointing readers at that file. A roving
    // tabstop is right for a `tablist` and wrong for a `group` of buttons: it
    // would put ONE chip in the tab order and hide the rest behind arrow keys
    // that are deliberately not wired up here.
    //
    // So: Tab reaches each chip in turn, and Enter opens one. Asserted through
    // `user`, which dispatches what a browser dispatches rather than the
    // synthetic click the rest of the file uses.
    const user = userEvent.setup()
    renderSite()

    await user.tab()
    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: /close waypoint details/i }),
    )

    // The way back to the peek, between the close button and the strip since
    // #941. It is a real control and therefore a real tabstop: a grabber a
    // keyboard could not reach would leave an opened card with no way back to
    // the peek that did not also throw the card away.
    await user.tab()
    expect(document.activeElement).toBe(screen.getByTestId('poi-card-collapse'))

    for (const chip of chips()) {
      await user.tab()
      expect(document.activeElement).toBe(chip)
    }

    // The last one Tab landed on is the campsite, and Enter is what opens it -
    // no click anywhere in this test.
    await user.keyboard('{Enter}')

    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Campsite' }),
    ).toBeInTheDocument()
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
    // live region, pressing Enter on "Privy 131 ft" moves the heading, the
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

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))

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
    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))
    expect(screen.getByRole('status')).toHaveTextContent('Chairback Gap Privy')

    const other: PoiDetail = {
      ...SHELTER,
      id: 'atc_shelters:other',
      name: 'Cloud Pond Lean-to',
    }
    rerender(<PoiCard poi={other} site={[other, PRIVY]} map={null} onClose={vi.fn()} />)
    // The new waypoint peeks, so the strip and its region arrive together when
    // this card is opened - which is the same journey the region has to
    // survive, and the point of the test is that it arrives empty.
    open()

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

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))

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
    expect(screen.getByRole('button', { name: 'Privy 131 ft' })).toHaveAttribute(
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

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))

    expect(screen.getByRole('button', { name: 'Campsite 82 ft' })).toBeInTheDocument()
  })

  it('shows the tapped part in its own accent, placeholder and all', () => {
    renderSite()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))

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

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))

    expect(screen.getByTestId('poi-card-photo-count')).toHaveTextContent('1 of 2')
    expect(screen.getByTestId('poi-card-photo')).toHaveAttribute('src', 'blob:p1')
  })

  it('gets you back to the pin you tapped', () => {
    // Without this the anchor chip is decoration: tapping into a member would
    // be a one-way trip, and closing and re-tapping the pin the only way out.
    renderSite()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))
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
    fireEvent.click(screen.getByRole('button', { name: 'Campsite 82 ft' }))
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

  it('measures the card again when a part swap comes back to the pin', () => {
    // The trap the issue named, at the place #941 moved it to. usePinAnchor
    // reads the card's height inside a listener that only fires on a camera
    // move, and a card whose CONTENT changed under a placement measured
    // against the old height sits on top of the pin it is describing when it
    // hangs below one. A privy is several lines shorter than its shelter.
    //
    // The chips now live in the opened card, which has let go of the pin, so
    // the swap itself no longer needs a measurement - there is nothing to
    // measure against. What does is the journey back: tap the privy, collapse
    // to the peek, and the card is tethered again showing a different part at
    // a different height. `shown` and `tethered` are both dependencies for
    // this one sequence.
    //
    // The last assertion is the other half, and it is why the projection keys
    // on the CARRIER rather than the part being read: the privy has no pin
    // since #524, so a card that followed it would hang off blank map.
    const mock = new MockMap({})
    const map = mock as unknown as MapLibreMap
    render(<PoiCard poi={SHELTER} site={SITE} map={map} onClose={vi.fn()} />)
    open()

    fireEvent.click(screen.getByRole('button', { name: 'Privy 131 ft' }))
    const projections = mock.projectCalls.length
    fireEvent.click(screen.getByTestId('poi-card-collapse'))

    // Back on the peek, and reading the privy.
    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Privy' }),
    ).toBeInTheDocument()
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
    // privy the campsite is 15 m (49 ft), not the 25 m (82 ft) it is from the
    // shelter.
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

    // Asserted on the peek, before the strip is reachable: what this test is
    // about is which point the card hangs off, and only the peek hangs off
    // anything. The strip below is the same claim in the opened card.
    expect(
      screen.getByRole('heading', { name: 'Chairback Gap Privy' }),
    ).toBeInTheDocument()
    open()
    // No number on the pin's own chip - zero from itself was never a fact
    // anybody needed - and the other two measured from it.
    expect(screen.getByRole('button', { name: 'Privy' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(screen.getByRole('button', { name: 'Shelter 131 ft' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Campsite 49 ft' })).toBeInTheDocument()
  })
})

// The card's two heights (#941).
//
// The complaint this answers is that one tethered card was trying to be the
// whole record: a hiker tapped a water pin and got a photograph, a paragraph
// of provenance and a set of coordinates above the one-tap answer they were
// standing there to give. What is asserted here is the division - what the
// peek carries, what it declines to carry, and that nothing is LOST by being
// behind the pull.
describe('the peek and the pull', () => {
  const WATER: PoiDetail = {
    id: 'osm_water:1',
    name: 'Unnamed spring',
    type: 'water',
    lat: 38.33137,
    lon: -78.53133,
    confidence: 'low',
    source: 'osm_water',
    mile: 899.9,
    description: 'Spring. Mapped by OpenStreetMap contributors.',
  }

  const notes: FieldNoteContext = {
    notesFor: () => [],
    disputeFor: () => null,
    reporterType: 'thru',
    contributeConditions: false,
    onAddNote: vi.fn(),
    onReportProblem: vi.fn(),
    now: new Date('2026-08-20T12:00:00Z'),
  }

  function renderWater(poi: PoiDetail = WATER) {
    return render(<PoiCard poi={poi} map={null} noteContext={notes} onClose={vi.fn()} />)
  }

  it('answers "what did I tap, and how is it right now" and stops there', () => {
    renderWater()

    // What it tapped.
    expect(screen.getByRole('heading', { name: 'Unnamed spring' })).toBeInTheDocument()
    expect(screen.getByText('Water')).toBeInTheDocument()
    expect(screen.getByText('mi 899.9')).toBeInTheDocument()
    // How it is right now, and the way to say.
    expect(screen.getByTestId('poi-card-peek-line')).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-observe-flowing')).toBeInTheDocument()
  })

  it('keeps the coordinates, the provenance and the description off the peek', () => {
    // #941's second defect, stated as a test: these are facts about where the
    // pin came from, and they were above the answer the hiker came for.
    renderWater()

    expect(screen.queryByText(/38\.33137/)).toBeNull()
    expect(screen.queryByText(/osm_water/)).toBeNull()
    expect(screen.queryByText(/Mapped by OpenStreetMap/)).toBeNull()
    expect(screen.queryByTestId('poi-card-take-photo')).toBeNull()
  })

  it('gives every one of them back on one pull', () => {
    // Behind the pull, not gone - which is the whole claim the peek rests on.
    renderWater()

    fireEvent.click(screen.getByTestId('poi-card-expand'))

    expect(screen.getByText(/38\.33137, -78\.53133/)).toBeInTheDocument()
    expect(screen.getByText(/osm_water/)).toBeInTheDocument()
    expect(
      screen.getByText('Spring. Mapped by OpenStreetMap contributors.'),
    ).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-take-photo')).toBeInTheDocument()
    // And the answers the peek held back, on the same surface as the two it
    // carried: the peek is a shortcut, never a filter.
    expect(screen.getByTestId('poi-card-observe-trickling')).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-observe-not_found')).toBeInTheDocument()
  })

  it('files the coordinates and the source under a heading that says what they are', () => {
    renderWater()
    fireEvent.click(screen.getByTestId('poi-card-expand'))

    expect(screen.getByRole('heading', { name: 'About this place' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Conditions' })).toBeInTheDocument()
  })

  it('goes back to the peek, and lets go of nothing on the way', () => {
    renderWater()
    fireEvent.click(screen.getByTestId('poi-card-expand'))
    fireEvent.click(screen.getByTestId('poi-card-collapse'))

    expect(screen.getByTestId('poi-card-peek')).toBeInTheDocument()
    expect(screen.queryByText(/38\.33137/)).toBeNull()
    // Still the same waypoint, still answerable.
    expect(screen.getByRole('heading', { name: 'Unnamed spring' })).toBeInTheDocument()
    expect(screen.getByTestId('poi-card-observe-flowing')).toBeInTheDocument()
  })

  it('peeks at the next waypoint however the last one was left', () => {
    // MapScreen renders this card without a React key, so an opened card
    // survives a change of pin unless something resets it - and an opened card
    // is a sheet over most of the map, arriving before its hiker asked.
    const { rerender } = renderWater()
    fireEvent.click(screen.getByTestId('poi-card-expand'))
    expect(screen.getByTestId('poi-card-scroll')).toBeInTheDocument()

    rerender(
      <PoiCard
        poi={{ ...WATER, id: 'osm_water:2', name: 'Spring below the gap' }}
        map={null}
        noteContext={notes}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByTestId('poi-card-peek')).toBeInTheDocument()
    expect(screen.queryByTestId('poi-card-scroll')).toBeNull()
  })

  it('says nobody has confirmed the place exists on the peek, not behind the pull', () => {
    // The one line that must never be a pull away. A hiker cannot act on
    // "nobody has confirmed this spring exists" if they have to go looking for
    // it, and OurHikeValues.md #4 is the whole argument for printing it.
    renderWater()

    expect(screen.getByText(/nobody has confirmed/i)).toBeInTheDocument()
  })

  it('shows the category’s silhouette on the peek and never a photograph', () => {
    // A photo's credit is the licence's price for showing it (CC BY / BY-SA),
    // and the peek has no line to spend on an attribution string. So the
    // photograph and its credit arrive together, on the pull, or not at all.
    renderWater({ ...WATER, photoUrl: 'blob:one', photoAuthor: 'A. Photographer' })

    expect(screen.getByTestId('poi-card-thumb')).toBeInTheDocument()
    expect(screen.queryByTestId('poi-card-photo')).toBeNull()
    expect(screen.queryByText(/A\. Photographer/)).toBeNull()

    fireEvent.click(screen.getByTestId('poi-card-expand'))

    expect(screen.getByTestId('poi-card-photo')).toBeInTheDocument()
    expect(screen.getByText(/A\. Photographer/)).toBeInTheDocument()
  })

  it('does not promise notes on a card that carries none', () => {
    // A viewpoint has no conditions section, so a control labelled "Notes &
    // details" would be teaching a hiker not to trust this card's labels.
    render(
      <PoiCard
        poi={{ ...WATER, type: 'viewpoint', confidence: 'high' }}
        map={null}
        noteContext={notes}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByTestId('poi-card-expand')).toHaveTextContent('Details')
    expect(screen.getByTestId('poi-card-expand')).not.toHaveTextContent('Notes')
  })

  it('hangs off its pin while it peeks and lets go once it is open', () => {
    // The tether is what makes the peek answer "which of these three pins did
    // I tap" with position rather than with a name. An opened card is a sheet
    // against the canvas's edge - it points at nothing, so it claims nothing.
    const mock = new MockMap({})
    const { container } = render(
      <PoiCard
        poi={WATER}
        map={mock as unknown as MapLibreMap}
        noteContext={notes}
        onClose={vi.fn()}
      />,
    )

    const card = container.querySelector('.poi-card') as HTMLElement
    expect(card.className).toContain('poi-card--peek')
    expect(card.style.transform).toMatch(/^translate\(/)

    fireEvent.click(screen.getByTestId('poi-card-expand'))

    expect(card.className).toContain('poi-card--open')
    expect(card.style.transform).toBe('')
  })
})
