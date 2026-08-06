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
  it('shows the category silhouette while no source publishes photos', () => {
    // The placeholder is honest iconography, not a stock photo pretending to
    // be the shelter - and it is the everyday state, since no published
    // source carries imagery yet.
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
