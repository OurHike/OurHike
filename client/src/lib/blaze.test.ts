import { describe, it, expect, vi } from 'vitest'
import { blazePaintColor, BLAZE_MATCH_EXPRESSION } from './blaze'

describe('blazePaintColor', () => {
  it('maps a known blaze_color string to its exact hex, per WIREFRAMES.md', () => {
    expect(blazePaintColor('White')).toBe('#fffdf7')
    expect(blazePaintColor('Blue')).toBe('#1f5fa8')
    expect(blazePaintColor('Yellow')).toBe('#dcae1b')
    expect(blazePaintColor('Orange')).toBe('#d2721c')
    expect(blazePaintColor('Red')).toBe('#b2321f')
    expect(blazePaintColor('Green')).toBe('#2f7a44')
    expect(blazePaintColor('Purple')).toBe('#6a4a8f')
  })

  it('maps the pipeline-normalized "None" value to the neutral fallback, silently (a real decode, not an error)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(blazePaintColor('None')).toBe('#8a8271')
    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })

  it('maps "Unknown" to the neutral fallback, silently - the pipeline emits it by contract for every undecodable blaze (#257)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(blazePaintColor('Unknown')).toBe('#8a8271')
    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })

  it('maps "Other" to the neutral fallback, silently - no dedicated paint style exists for it', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(blazePaintColor('Other')).toBe('#8a8271')
    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })

  it('falls back to neutral grey AND emits a warning for any value that is not one of the expected strings', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    // "Unknown" used to head this list; it moved to the silent set above,
    // because the pipeline emits it by contract for every undecodable blaze
    // (#257) - warning on it was noise about our own upstream's documented
    // behaviour.
    expect(blazePaintColor('Gold')).toBe('#8a8271')
    expect(blazePaintColor('')).toBe('#8a8271')
    // @ts-expect-error - defensive fallback must also cover unexpected non-string input from a rendering layer that shouldn't blindly trust the pipeline
    expect(blazePaintColor(null)).toBe('#8a8271')

    expect(warn).toHaveBeenCalledTimes(3)
    warn.mockRestore()
  })
})

describe('BLAZE_MATCH_EXPRESSION', () => {
  it('is a single MapLibre match expression covering every known blaze_color plus a fallback - not per-layer hardcoding', () => {
    expect(BLAZE_MATCH_EXPRESSION[0]).toBe('match')
    expect(BLAZE_MATCH_EXPRESSION[1]).toEqual(['get', 'blaze_color'])
    // last element is always the fallback color for anything that doesn't match a listed case
    expect(BLAZE_MATCH_EXPRESSION.at(-1)).toBe('#8a8271')
  })
})
