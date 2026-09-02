// Which phone made this file (lib/tracePlatform.ts).
//
// The assertions worth having here are the ones about NOT answering. A
// user-agent sniff that guesses is worse than one that shrugs, because the
// guess reaches a CSV that thresholds get derived from and nothing downstream
// can tell a guess from an observation.

import { afterEach, describe, expect, it, vi } from 'vitest'

import { deviceOsFrom, traceDeviceOs, traceShell } from './tracePlatform'

vi.mock('@capacitor/core', () => ({
  Capacitor: { getPlatform: () => mockPlatform },
}))

let mockPlatform = 'web'

afterEach(() => {
  mockPlatform = 'web'
  vi.unstubAllGlobals()
})

describe('deviceOsFrom', () => {
  it('reads an iPhone', () => {
    expect(
      deviceOsFrom(
        'Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 ' +
          '(KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1',
      ),
    ).toBe('ios')
  })

  it('reads an Android phone', () => {
    expect(
      deviceOsFrom(
        'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) ' +
          'Chrome/140.0.0.0 Mobile Safari/537.36',
      ),
    ).toBe('android')
  })

  it('says nothing rather than guessing at a desktop', () => {
    // The column exists to separate two phones. A laptop is neither, and
    // "neither" is the correct answer rather than a nearest match.
    expect(
      deviceOsFrom(
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
          '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
      ),
    ).toBeNull()
  })

  it('says nothing for an iPad claiming to be a Mac', () => {
    // iPadOS requests desktop sites by default and its user agent is a
    // Macintosh one. Null is right: this is not one of the two phones being
    // compared, and labelling it `ios` would put tablet rows in the iPhone
    // bucket of an accuracy comparison.
    expect(
      deviceOsFrom(
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 ' +
          '(KHTML, like Gecko) Version/18.5 Safari/605.1.15',
      ),
    ).toBeNull()
  })

  it('says nothing for an empty user agent', () => {
    expect(deviceOsFrom('')).toBeNull()
  })
})

describe('traceShell', () => {
  it('names a Capacitor Android build', () => {
    mockPlatform = 'android'
    expect(traceShell()).toBe('android')
  })

  it('names a Capacitor iOS build', () => {
    mockPlatform = 'ios'
    expect(traceShell()).toBe('ios')
  })

  it('calls every browser web, installed to the home screen or not', () => {
    // A PWA is not a distinct runtime and Capacitor does not report one.
    // Inventing the distinction here would put a claim in the file that
    // nothing had checked.
    mockPlatform = 'web'
    expect(traceShell()).toBe('web')
  })

  it('falls back to web for a platform this build does not know', () => {
    mockPlatform = 'electron'
    expect(traceShell()).toBe('web')
  })
})

describe('traceDeviceOs', () => {
  it('reads the live user agent', () => {
    vi.stubGlobal('navigator', { userAgent: '(Linux; Android 15; Pixel 9)' })
    expect(traceDeviceOs()).toBe('android')
  })

  it('says nothing where there is no navigator at all', () => {
    vi.stubGlobal('navigator', undefined)
    expect(traceDeviceOs()).toBeNull()
  })
})
