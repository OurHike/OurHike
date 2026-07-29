import { describe, it, expect } from 'vitest'
import { formatBytes } from './formatBytes'
import { DOWNLOAD_DETAIL_LEVELS } from './downloadDetail'

// The three download sizes are load-bearing values (WIREFRAMES.md): they are
// what someone decides against their remaining phone storage before a thru
// hike. They are quoted in the wireframe as "64 MB", "314 MB" and "1.18 GB",
// and this formatter exists so those exact strings come out of the real
// measured byte counts rather than being typed as copy in three places.
//
// Decimal (SI) units, not binary: pipeline/README.md measured these against
// decimal MB/GB, and quoting 314 MB as "299 MiB" would not match the figure
// anyone has been given.

describe('formatBytes', () => {
  it.each([
    [64_000_000, '64 MB'],
    [314_000_000, '314 MB'],
    [1_180_000_000, '1.18 GB'],
  ])('formats %i as the exact string the wireframe quotes', (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected)
  })

  it('produces the wireframe figure for every real detail level, with no drift', () => {
    // Guards the formatter and the table together: if either changes, the
    // three quoted sizes have to still come out.
    expect(DOWNLOAD_DETAIL_LEVELS.map((d) => formatBytes(d.sizeBytes))).toEqual([
      '64 MB',
      '314 MB',
      '1.18 GB',
    ])
  })

  it('drops a trailing zero rather than printing "1.20 GB"', () => {
    expect(formatBytes(1_200_000_000)).toBe('1.2 GB')
  })

  it('drops the decimal entirely on a whole number of gigabytes', () => {
    expect(formatBytes(2_000_000_000)).toBe('2 GB')
  })

  it('switches to GB exactly at a gigabyte', () => {
    expect(formatBytes(999_000_000)).toBe('999 MB')
    expect(formatBytes(1_000_000_000)).toBe('1 GB')
  })

  it('handles small sizes without pretending they are megabytes', () => {
    expect(formatBytes(0)).toBe('0 MB')
    expect(formatBytes(500_000)).toBe('0.5 MB')
  })
})
