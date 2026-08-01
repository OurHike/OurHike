import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { detectInstallPlatform, isStandalone, useInstallPrompt } from './useInstallPrompt'

function stubUserAgent(ua: string, platform = 'Linux', maxTouchPoints = 0) {
  vi.stubGlobal('navigator', {
    userAgent: ua,
    platform,
    maxTouchPoints,
    onLine: true,
  })
}

function stubDisplayMode(standalone: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: standalone && query.includes('standalone'),
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }))
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('detectInstallPlatform', () => {
  it('recognises Android', () => {
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120')

    expect(detectInstallPlatform()).toBe('android')
  })

  it('recognises an iPhone', () => {
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Version/17.0 Safari')

    expect(detectInstallPlatform()).toBe('ios')
  })

  it('recognises an iPad, which reports itself as a Mac', () => {
    // iPadOS 13+ sends a desktop Safari UA. Without the touch-point check an
    // iPad would be told it is a computer and never see the install steps.
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari', 'MacIntel', 5)

    expect(detectInstallPlatform()).toBe('ios')
  })

  it('does not mistake a real Mac for an iPad', () => {
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari', 'MacIntel', 0)

    expect(detectInstallPlatform()).toBe('other')
  })

  it('reports an installed app as installed, whatever the platform', () => {
    stubDisplayMode(true)
    stubUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120')

    expect(detectInstallPlatform()).toBe('installed')
  })
})

describe('isStandalone', () => {
  it("trusts Safari's own flag, the only signal iOS gives", () => {
    stubDisplayMode(false)
    vi.stubGlobal('navigator', {
      userAgent: 'iPhone',
      platform: 'iPhone',
      standalone: true,
    })

    expect(isStandalone()).toBe(true)
  })
})

describe('useInstallPrompt', () => {
  it('offers no prompt until the browser says the page qualifies', () => {
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120')

    const { result } = renderHook(() => useInstallPrompt())

    expect(result.current.canPrompt).toBe(false)
  })

  it('offers a prompt once beforeinstallprompt fires, and suppresses the browser bar', () => {
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120')

    const { result } = renderHook(() => useInstallPrompt())

    const event = new Event('beforeinstallprompt')
    const preventDefault = vi.spyOn(event, 'preventDefault')
    act(() => {
      window.dispatchEvent(event)
    })

    expect(result.current.canPrompt).toBe(true)
    // Chrome shows its own mini-infobar otherwise; the app asks at a moment it
    // chooses, on the Downloads screen.
    expect(preventDefault).toHaveBeenCalled()
  })

  it('stops offering to install once the app is installed', () => {
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120')

    const { result } = renderHook(() => useInstallPrompt())
    act(() => {
      window.dispatchEvent(new Event('beforeinstallprompt'))
    })
    expect(result.current.canPrompt).toBe(true)

    act(() => {
      window.dispatchEvent(new Event('appinstalled'))
    })

    expect(result.current.canPrompt).toBe(false)
    expect(result.current.platform).toBe('installed')
  })

  it('does nothing when asked to install with no pending prompt', () => {
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120')

    const { result } = renderHook(() => useInstallPrompt())

    expect(() => result.current.install()).not.toThrow()
  })

  it('hands the deferred event back to the browser when the app asks to install', async () => {
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120')

    const { result } = renderHook(() => useInstallPrompt())

    const event = new Event('beforeinstallprompt') as Event & {
      prompt: () => Promise<void>
      userChoice: Promise<{ outcome: string }>
    }
    event.prompt = vi.fn(() => Promise.resolve())
    event.userChoice = Promise.resolve({ outcome: 'accepted' })
    act(() => {
      window.dispatchEvent(event)
    })

    await act(async () => {
      result.current.install()
    })

    expect(event.prompt).toHaveBeenCalledTimes(1)
  })

  it('stops offering after the prompt has been used, since it is single-use', async () => {
    // A beforeinstallprompt event can only be prompted once. Leaving the button
    // live afterwards offers something that silently does nothing.
    stubDisplayMode(false)
    stubUserAgent('Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120')

    const { result } = renderHook(() => useInstallPrompt())

    const event = new Event('beforeinstallprompt') as Event & {
      prompt: () => Promise<void>
      userChoice: Promise<{ outcome: string }>
    }
    event.prompt = vi.fn(() => Promise.resolve())
    event.userChoice = Promise.resolve({ outcome: 'dismissed' })
    act(() => {
      window.dispatchEvent(event)
    })

    await act(async () => {
      result.current.install()
      await event.userChoice
    })

    expect(result.current.canPrompt).toBe(false)
  })
})
