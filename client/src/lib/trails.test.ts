import { describe, it, expect } from 'vitest'
import { TRAILS } from './trails'

describe('TRAILS', () => {
  it('has a logo for every trail it lists, including the AT', () => {
    expect(TRAILS.AT.name).toBe('Appalachian Trail')

    for (const trail of Object.values(TRAILS)) {
      expect(trail.logo).toBeTruthy()
    }
  })
})
