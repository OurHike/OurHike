import { describe, it, expect } from 'vitest'
import { TRAILS, trailForName } from './trails'

describe('TRAILS', () => {
  it('has a logo for every trail it lists, including the AT', () => {
    expect(TRAILS.AT.name).toBe('Appalachian Trail')

    for (const trail of Object.values(TRAILS)) {
      expect(trail.logo).toBeTruthy()
    }
  })

  it('knows the Long Path, with its own mark (#1288)', () => {
    expect(TRAILS.LP.name).toBe('Long Path')
    expect(TRAILS.LP.logo).toBeTruthy()
    expect(TRAILS.LP.logo).not.toBe(TRAILS.AT.logo)
  })
})

describe('trailForName', () => {
  it('finds a trail by the name a published line carries', () => {
    expect(trailForName('Long Path')).toBe(TRAILS.LP)
    expect(trailForName('Appalachian Trail')).toBe(TRAILS.AT)
  })

  it('is forgiving of case and whitespace, which a steward’s field may vary', () => {
    expect(trailForName(' long path ')).toBe(TRAILS.LP)
  })

  it('never matches a substring - a link trail is not the trail it links to', () => {
    expect(trailForName('Long Path Link Trail')).toBeUndefined()
    expect(trailForName('Suffern–Bear Mountain Trail')).toBeUndefined()
  })

  it('answers nothing for nothing', () => {
    expect(trailForName(null)).toBeUndefined()
    expect(trailForName(undefined)).toBeUndefined()
    expect(trailForName('')).toBeUndefined()
  })
})
