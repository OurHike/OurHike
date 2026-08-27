import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { PressPlate, whereWords, type PressPlateProps } from './PressPlate'

// The press-and-hold plate (#1137).
//
// Most of what matters here is the ONE LINE naming where the press landed,
// because that line is the only thing standing between a hiker and a report
// filed somewhere they did not mean. The rest is two buttons.

// `globals` is off in vite.config.ts, so Testing Library's automatic cleanup
// never installs itself - every render would otherwise pile up in one document
// and the second `getByTestId` of a run would find two. Same afterEach
// FieldNoteSection.test.tsx keeps, for the same reason.
afterEach(() => {
  cleanup()
})

const WITHIN = { width: 390, height: 844 }

function setup(overrides: Partial<PressPlateProps> = {}) {
  const props: PressPlateProps = {
    point: { x: 195, y: 400 },
    within: WITHIN,
    mile: 628.4,
    knowsTrail: true,
    units: 'imperial',
    onReport: vi.fn(),
    onThanks: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  }
  return { props, ...render(<PressPlate {...props} />) }
}

describe('where the press landed', () => {
  it('names the mile when there is one', () => {
    setup()
    expect(screen.getByTestId('press-plate-where')).toHaveTextContent('mi 628.4')
  })

  it('writes the mile as a marker, never through a distance formatter', () => {
    // #986, on a new surface. `formatDistance(628.4, 'metric')` is "1,011.3
    // km" - not a wrong-looking number but a position on this trail naming
    // somewhere else entirely. A marker does not convert.
    setup({ units: 'metric' })
    const where = screen.getByTestId('press-plate-where')
    expect(where).toHaveTextContent('mi 628.4')
    expect(where).not.toHaveTextContent('km')
  })

  it('says it could not check when the trail index is not on the phone', () => {
    // #249's null-vs-unknown distinction. This hiker is not off the trail -
    // nobody has looked, because there is nothing to look in.
    setup({ mile: null, knowsTrail: false })
    const where = screen.getByTestId('press-plate-where')
    expect(where).toHaveTextContent('This spot')
    expect(where.textContent).not.toMatch(/off the trail/i)
  })

  it('says how far off when the index is here and refused the point', () => {
    // The other half of the same null. With an index present, null means
    // lib/trailPosition.ts looked and the point is past MAX_OFF_TRAIL_MILES.
    setup({ mile: null, knowsTrail: true })
    expect(screen.getByTestId('press-plate-where')).toHaveTextContent(
      /More than 3 mi off the trail/,
    )
  })

  it('puts that distance in the hiker’s own units, because it IS a distance', () => {
    // The mirror of the marker rule above, and the reason both tests exist
    // next to each other: one number on this plate converts and the other must
    // not. 3 mi is 4.8 km.
    expect(whereWords(null, true, 'metric')).toMatch(/4\.8 km/)
    expect(whereWords(null, true, 'imperial')).toMatch(/3 mi/)
  })
})

describe('what the plate offers', () => {
  it('opens a door for each, and files nothing itself', () => {
    // Deliberately unlike #1133's category tiles, which DO file on a tap. A
    // tile is tapped by somebody who has already said what they found; a press
    // on bare map has said only where.
    const onReport = vi.fn()
    const onThanks = vi.fn()
    setup({ onReport, onThanks })

    fireEvent.click(screen.getByRole('button', { name: 'Report a problem' }))
    expect(onReport).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Say thanks' }))
    expect(onThanks).toHaveBeenCalledTimes(1)
  })

  it('offers both halves of the crew relationship, as every other entry does', () => {
    setup()
    expect(screen.getByRole('button', { name: 'Report a problem' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Say thanks' })).toBeTruthy()
  })

  it('closes on “Not here”, which is what a press that missed needs', () => {
    const onClose = vi.fn()
    setup({ onClose })
    fireEvent.click(screen.getByTestId('press-plate-close'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('names itself as a dialog', () => {
    setup()
    expect(screen.getByRole('dialog')).toHaveAccessibleName(
      'Report or thank at this spot',
    )
  })
})

describe('staying on the screen', () => {
  function boxOf(): { left: number; top: number } {
    const style = screen.getByTestId('press-plate').style
    return { left: Number.parseFloat(style.left), top: Number.parseFloat(style.top) }
  }

  it('sits above the press, so the finger is not covering it', () => {
    setup({ point: { x: 195, y: 400 } })
    expect(boxOf().top).toBeLessThan(400)
  })

  it('slides back on rather than hanging off the right edge', () => {
    setup({ point: { x: 385, y: 400 } })
    expect(boxOf().left + 208).toBeLessThanOrEqual(WITHIN.width)
  })

  it('slides back on rather than hanging off the left edge', () => {
    setup({ point: { x: 4, y: 400 } })
    expect(boxOf().left).toBeGreaterThanOrEqual(0)
  })

  it('drops below a press near the top rather than off the top', () => {
    // The one case where "above the press" cannot be honoured. Clamped rather
    // than flipped: the plate stays as near where they pressed as the screen
    // allows, instead of jumping somewhere they have to find.
    setup({ point: { x: 195, y: 10 } })
    expect(boxOf().top).toBeGreaterThanOrEqual(0)
  })

  it('stays on a screen too small to hold it, rather than going negative', () => {
    // A short map region - a phone in landscape with the keyboard up. The
    // clamp has to survive `within` being smaller than the plate itself,
    // which is where a naive min/max pair produces a negative offset and the
    // plate leaves the screen entirely.
    setup({ point: { x: 195, y: 400 }, within: { width: 100, height: 100 } })
    const box = boxOf()
    expect(box.left).toBeGreaterThanOrEqual(0)
    expect(box.top).toBeGreaterThanOrEqual(0)
  })
})
