import { describe, it, expect } from 'vitest'
import { formatBytes, formatBytesLive } from './formatBytes'
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

  it('leaves a whole number alone rather than trimming digits out of it', () => {
    // The trimming pass only ever runs on a decimal string; a value with no
    // point must come back untouched, not have its trailing zeros eaten.
    expect(formatBytes(300_000_000)).toBe('300 MB')
    expect(formatBytes(64_000_000)).toBe('64 MB')
  })

  it('never eats a digit off a string that has no decimal point', () => {
    // Guards the trimming pattern itself: applied unanchored, "10" would come
    // back as "1". No caller reaches it that way today, which is exactly why
    // it is asserted here rather than left to a comment.
    expect(formatBytes(10_000_000)).toBe('10 MB')
    expect(formatBytes(100_000_000)).toBe('100 MB')
    expect(formatBytes(10_000_000_000)).toBe('10 GB')
  })
})

// The live variant feeds the counter under the progress bar, which re-renders
// on every received chunk. Its one job is to hold still: no MB decimal to
// spin, no zero-trimming to change the string's width mid-download.

describe('formatBytesLive', () => {
  it('drops the MB decimal, flooring rather than rounding', () => {
    // Flooring, because a counter that overstates reads as a lie the moment
    // it stalls, and because it caps the string at the total's own width.
    expect(formatBytesLive(157_650_000)).toBe('157 MB')
    expect(formatBytesLive(157_000_000)).toBe('157 MB')
    expect(formatBytesLive(0)).toBe('0 MB')
  })

  it('never widens past the total by rounding 999.5 MB up to "1000 MB"', () => {
    expect(formatBytesLive(999_999_999)).toBe('999 MB')
    expect(formatBytesLive(1_000_000_000)).toBe('1.00 GB')
  })

  it('keeps both GB decimals pinned, never trimmed to a narrower string', () => {
    // A hundredth of a GB ticks every 10 MB - calm enough to keep - and
    // "1.10 GB" must hold the width "1.18 GB" needs.
    expect(formatBytesLive(1_100_000_000)).toBe('1.10 GB')
    expect(formatBytesLive(2_000_000_000)).toBe('2.00 GB')
  })

  it('floors GB too, so the counter never reads past the quoted total', () => {
    // 1.179 GB rounded would show "1.18 GB of 1.18 GB" before it is true.
    expect(formatBytesLive(1_179_000_000)).toBe('1.17 GB')
  })
})
