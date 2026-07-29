import { describe, it, expect } from 'vitest'
import { DOWNLOAD_DETAIL_LEVELS, getDownloadDetail } from './downloadDetail'

// Whole-corridor, one package (ROADMAP.md Phase 2, WIREFRAMES.md Known
// Deviations #1) - a single download's detail choice, not a per-section
// override. Sizes are the real measured whole-corridor figures from
// pipeline/README.md - no per-section ratio math needed or wanted here.

describe('downloadDetail', () => {
  it('maps each of the three detail levels to its correct zoom and measured size', () => {
    expect(getDownloadDetail('light')).toMatchObject({
      level: 'light',
      zoom: 11,
      sizeBytes: 64_000_000,
    })
    expect(getDownloadDetail('standard')).toMatchObject({
      level: 'standard',
      zoom: 12,
      sizeBytes: 314_000_000,
    })
    expect(getDownloadDetail('fine')).toMatchObject({
      level: 'fine',
      zoom: 13,
      sizeBytes: 1_180_000_000,
    })
  })

  it('exposes exactly three detail levels - guards against a fourth silently appearing or one being dropped', () => {
    expect(DOWNLOAD_DETAIL_LEVELS.map((d) => d.level)).toEqual([
      'light',
      'standard',
      'fine',
    ])
  })

  it('keeps zoom strictly increasing with detail level - light < standard < fine, one drifting would be a real bug', () => {
    const zooms = DOWNLOAD_DETAIL_LEVELS.map((d) => d.zoom)
    expect(zooms[0]).toBeLessThan(zooms[1])
    expect(zooms[1]).toBeLessThan(zooms[2])
  })

  it('keeps size strictly increasing with detail level - a detail level with a smaller footprint than a "lighter" one would be a real bug', () => {
    const sizes = DOWNLOAD_DETAIL_LEVELS.map((d) => d.sizeBytes)
    expect(sizes[0]).toBeLessThan(sizes[1])
    expect(sizes[1]).toBeLessThan(sizes[2])
  })

  it('marks standard as the recommended/default level, per WIREFRAMES.md onboarding copy', () => {
    expect(getDownloadDetail('standard').recommended).toBe(true)
    expect(getDownloadDetail('light').recommended).toBe(false)
    expect(getDownloadDetail('fine').recommended).toBe(false)
  })
})
