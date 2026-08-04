import { describe, it, expect } from 'vitest'
import { POI_PIN_SIZE } from '../map/poiIcons'
import { placePoiCard, CARD_GAP_PX, CARD_EDGE_MARGIN_PX } from './poiCardPlacement'

// The contract under test: the card visibly belongs to its pin. It prefers to
// float above it, gives way at the canvas edges, and when the pin leaves the
// screen the card leaves too - a card clamped to the margin pointing at
// nothing would claim a waypoint where there is only edge.

const CARD = { width: 264, height: 180 }
const CANVAS = { width: 400, height: 700 }
const PIN_HALF = POI_PIN_SIZE / 2

describe('placing the waypoint card', () => {
  it('floats above the pin, centred on it', () => {
    const placed = placePoiCard({ x: 200, y: 400 }, CARD, CANVAS)

    expect(placed.left).toBe(200 - CARD.width / 2)
    expect(placed.top).toBe(400 - PIN_HALF - CARD_GAP_PX - CARD.height)
  })

  it('clears the pin by its drawn half plus the gap, so it never covers what it describes', () => {
    const placed = placePoiCard({ x: 200, y: 400 }, CARD, CANVAS)

    expect(placed.top + CARD.height).toBe(400 - PIN_HALF - CARD_GAP_PX)
  })

  it('flips below a pin near the top of the screen', () => {
    const placed = placePoiCard({ x: 200, y: 60 }, CARD, CANVAS)

    expect(placed.top).toBe(60 + PIN_HALF + CARD_GAP_PX)
  })

  it('stays above when neither side fits - the bottom edge hides everything, the top edge only the head', () => {
    const shortCanvas = { width: 400, height: 100 }
    const placed = placePoiCard({ x: 200, y: 50 }, CARD, shortCanvas)

    expect(placed.top).toBe(50 - PIN_HALF - CARD_GAP_PX - CARD.height)
  })

  it('slides right rather than hanging off the left edge', () => {
    const placed = placePoiCard({ x: 40, y: 400 }, CARD, CANVAS)

    expect(placed.left).toBe(CARD_EDGE_MARGIN_PX)
  })

  it('slides left rather than hanging off the right edge', () => {
    const placed = placePoiCard({ x: 380, y: 400 }, CARD, CANVAS)

    expect(placed.left).toBe(CANVAS.width - CARD_EDGE_MARGIN_PX - CARD.width)
  })

  it('keeps hold of a pin panned past the left edge instead of squatting on the margin', () => {
    const placed = placePoiCard({ x: -120, y: 400 }, CARD, CANVAS)

    // The pin's x stays within the card's span, so the card is visibly
    // leaving with its pin rather than sitting on the edge unattached.
    expect(placed.left).toBeLessThanOrEqual(-120)
    expect(placed.left + CARD.width).toBeGreaterThanOrEqual(-120)
  })

  it('keeps hold of a pin panned past the right edge', () => {
    const placed = placePoiCard({ x: 520, y: 400 }, CARD, CANVAS)

    expect(placed.left).toBeLessThanOrEqual(520)
    expect(placed.left + CARD.width).toBeGreaterThanOrEqual(520)
  })

  it('moves continuously as a pin crosses the edge - no jump between clamped and free', () => {
    // One-pixel steps across the threshold where the pin bound overtakes the
    // edge margin. A discontinuity here would read as the card snapping.
    let previous = placePoiCard({ x: 30, y: 400 }, CARD, CANVAS).left
    for (let x = 29; x >= -20; x -= 1) {
      const next = placePoiCard({ x, y: 400 }, CARD, CANVAS).left
      expect(Math.abs(next - previous)).toBeLessThanOrEqual(1)
      previous = next
    }
  })

  it('centres on the pin, unclamped, when the canvas cannot hold the card at all', () => {
    // jsdom's every-size-is-zero canvas lands here too, which is what keeps
    // component tests deterministic: centred on the pin, floating above it.
    const placed = placePoiCard({ x: 200, y: 400 }, CARD, { width: 0, height: 0 })

    expect(placed.left).toBe(200 - CARD.width / 2)
    expect(placed.top).toBe(400 - PIN_HALF - CARD_GAP_PX - CARD.height)
  })
})
