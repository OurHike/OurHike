import { describe, it, expect } from 'vitest'
import { TRAILS, displayTrailName, trailForName } from './trails'

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

  it('finds the A.T. under the name ATC publishes it as', () => {
    expect(trailForName('Appalachian National Scenic Trail')).toBe(TRAILS.AT)
    expect(trailForName('  appalachian NATIONAL scenic trail ')).toBe(TRAILS.AT)
  })

  it('answers nothing for nothing', () => {
    expect(trailForName(null)).toBeUndefined()
    expect(trailForName(undefined)).toBeUndefined()
    expect(trailForName('')).toBeUndefined()
  })
})

describe('displayTrailName', () => {
  it('shows ATC’s centerline name as "Appalachian Trail"', () => {
    // The whole point of the table: ATC publishes the federal designation on
    // every centerline segment, and the app says the name hikers use. One
    // place decides it, so the badge, the legend’s "Trails in view" row and
    // the line sheet cannot end up calling one trail two things.
    expect(displayTrailName('Appalachian National Scenic Trail')).toBe(
      'Appalachian Trail',
    )
  })

  it('is forgiving of the case and spacing a steward’s field may vary', () => {
    expect(displayTrailName('  APPALACHIAN NATIONAL SCENIC TRAIL  ')).toBe(
      'Appalachian Trail',
    )
  })

  it('leaves a name the registry does not know exactly as published', () => {
    // Renaming somebody else’s trail would be a claim about their data that
    // nobody here can stand behind - and the near-misses are the ones that
    // would hurt, since a link trail is not the trail it links to.
    expect(displayTrailName('Ramapo-Dunderberg Trail')).toBe('Ramapo-Dunderberg Trail')
    expect(displayTrailName('Long Path Link Trail')).toBe('Long Path Link Trail')
    expect(displayTrailName('Appalachian Trail Conservancy Access')).toBe(
      'Appalachian Trail Conservancy Access',
    )
  })

  it('passes a registry name straight back, so the table is never a round trip', () => {
    expect(displayTrailName('Appalachian Trail')).toBe('Appalachian Trail')
    expect(displayTrailName('Long Path')).toBe('Long Path')
  })

  it('answers null for nothing, which is what the callers omit on', () => {
    // Not '': map/trailsInView.ts drops a trail on a null name, and an empty
    // string would put a nameless row in the legend and a blank plate on the
    // map - the "Unnamed" label map/trailLabels.ts refuses, spelled differently.
    expect(displayTrailName(null)).toBeNull()
    expect(displayTrailName(undefined)).toBeNull()
    expect(displayTrailName('')).toBeNull()
    expect(displayTrailName('   ')).toBeNull()
  })
})
