import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { ModeIcon } from './ModeIcon'
import { HIKER_MODE_VALUES } from '../lib/hikerMode'

afterEach(cleanup)

describe('ModeIcon', () => {
  it('draws one distinct glyph per mode, in a unit box scaled by size', () => {
    const drawn = HIKER_MODE_VALUES.map((mode) => {
      const { container, unmount } = render(<ModeIcon mode={mode} size={24} />)
      const svg = container.querySelector('svg')
      if (svg === null) throw new Error('no glyph rendered')
      const markup = svg.innerHTML
      expect(svg.getAttribute('viewBox')).toBe('0 0 1 1')
      expect(svg.getAttribute('width')).toBe('24')
      expect(svg.getAttribute('data-mode')).toBe(mode)
      unmount()
      return markup
    })

    expect(new Set(drawn).size).toBe(HIKER_MODE_VALUES.length)
  })

  it('is decorative - the word beside it is what a screen reader gets', () => {
    const { container } = render(<ModeIcon mode="volunteer" />)

    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })

  it('inherits its colour, so one component serves pine chrome and paper alike', () => {
    const { container } = render(<ModeIcon mode="day" />)

    expect(container.innerHTML).toContain('currentColor')
    expect(container.innerHTML).not.toMatch(/#[0-9a-f]{3,6}/i)
  })
})
