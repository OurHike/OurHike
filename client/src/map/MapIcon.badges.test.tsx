import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { MapIcon } from './MapIcon'
import { badgeCenters, pinGeometry, POI_COLORS, sitePinPadding } from './poiIcons'

// A site pin's badges and the bare tile (#1373), tested the way MapIcon.test.tsx
// tests the pin: against the geometry the map itself draws from, never against
// a second set of numbers.

const PIN = pinGeometry(1)

afterEach(cleanup)

function draw(node: React.ReactElement): SVGElement {
  const { container } = render(node)
  const svg = container.querySelector('svg')
  if (svg === null) throw new Error('no icon rendered')
  return svg
}

describe('a site pin’s badges', () => {
  it('draws one badge per member, at the map’s own badge centres, in each member’s accent', () => {
    const svg = draw(<MapIcon type="shelter" members={['privy', 'water']} />)

    const badges = [...svg.querySelectorAll('.map-icon__badge')]
    expect(badges.map((b) => b.getAttribute('data-member'))).toEqual(['privy', 'water'])

    const centres = badgeCenters(2, PIN.badge)
    badges.forEach((badge, index) => {
      const disc = badge.querySelectorAll('circle')[1]
      expect(Number(disc.getAttribute('cx'))).toBeCloseTo(
        PIN.center + centres[index].x,
        6,
      )
      expect(Number(disc.getAttribute('cy'))).toBeCloseTo(
        PIN.center + centres[index].y,
        6,
      )
      expect(disc.getAttribute('fill')).toBe(
        POI_COLORS[['privy', 'water'][index] as 'privy' | 'water'],
      )
    })
  })

  it('grows its box for the badges symmetrically, as the raster image does', () => {
    const plain = draw(<MapIcon type="shelter" />)
    const badged = draw(
      <MapIcon type="shelter" members={['privy', 'water', 'campsite']} />,
    )

    expect(plain.getAttribute('viewBox')).toBe('0 0 1 1')
    const [x, y, w, h] = (badged.getAttribute('viewBox') ?? '').split(' ').map(Number)
    expect(x).toBeLessThan(0)
    expect(x).toBe(y)
    expect(w).toBe(h)
    expect(w).toBeCloseTo(1 - 2 * x, 9)
    // The same reach sitePinPadding measures in pixels, here in unit terms.
    expect(-x).toBeGreaterThan(0)
    expect(sitePinPadding(3)).toBeGreaterThan(0)
  })

  it('draws no badge on a pin carrying nothing, which is every pin that is not a site', () => {
    const svg = draw(<MapIcon type="water" />)

    expect(svg.querySelector('.map-icon__badge')).toBeNull()
  })
})

describe('the tile', () => {
  it('is the bare silhouette on a square tinted with the type’s own accent', () => {
    const { container } = render(<MapIcon type="water" variant="tile" />)

    const tile = container.querySelector('.map-icon-tile') as HTMLElement
    expect(tile).not.toBeNull()
    expect(tile.style.getPropertyValue('--chip-accent')).toBe(POI_COLORS.water)
    expect(tile.querySelector('.map-icon__glyph')).not.toBeNull()
    expect(tile.querySelector('.map-icon__disc')).toBeNull()
  })

  it('is decorative, like the pin', () => {
    const { container } = render(<MapIcon type="water" variant="tile" />)

    expect(container.querySelector('.map-icon-tile')).toHaveAttribute(
      'aria-hidden',
      'true',
    )
  })
})
