import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AboutBuild } from './AboutBuild'
import { readBuildInfo } from '../lib/buildInfo'

// #378: until this existed, a bug report started from a build nobody could
// identify. What is tested here is that the section answers the question, and
// that it never answers it wrongly - a version display that guesses is worse
// than none, because the guess is what gets quoted back.

const RELEASE = readBuildInfo({
  version: '1.0.0',
  commit: '6e23f122d35c327abf6eec8ca48158e336362cc9',
  builtAt: '2026-08-07T23:51:31.603Z',
})

const UNTAGGED = readBuildInfo({
  version: '0.0.0',
  commit: 'aaaaaaabbbbbbbcccccccdddddddeeeeeeefffffff',
  builtAt: '2026-08-07T23:51:31.603Z',
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('AboutBuild', () => {
  it('shows the version, the commit and when the build was made', () => {
    render(<AboutBuild build={RELEASE} />)

    expect(screen.getByText('1.0.0')).toBeInTheDocument()
    expect(screen.getByText('6e23f12')).toBeInTheDocument()
    expect(screen.getByText('2026-08-07 23:51 UTC')).toBeInTheDocument()
  })

  it('says a build with no tag behind it is not a release', () => {
    render(<AboutBuild build={UNTAGGED} />)

    expect(screen.getByText(/never tagged as a release/i)).toBeInTheDocument()
  })

  it('does not say that about a build that is one', () => {
    render(<AboutBuild build={RELEASE} />)

    expect(screen.queryByText(/never tagged as a release/i)).not.toBeInTheDocument()
  })

  // The copy button is the part that makes the answer arrive intact: seven
  // characters of hex retyped from a phone is exactly the kind of thing that
  // arrives with a digit changed.
  it('copies the whole build, full commit included, in one line', async () => {
    const user = userEvent.setup()
    render(<AboutBuild build={RELEASE} />)

    await user.click(screen.getByRole('button', { name: /copy build details/i }))

    // Read back from the clipboard rather than from a spy: what matters is
    // what a hiker can paste, not that a function was called.
    const copied = await navigator.clipboard.readText()
    expect(copied).toContain('1.0.0')
    expect(copied).toContain('6e23f122d35c327abf6eec8ca48158e336362cc9')
    expect(copied).toContain('2026-08-07 23:51 UTC')
    expect(copied).not.toContain('\n')

    expect(await screen.findByText('Copied.')).toBeInTheDocument()
  })

  // A browser that refuses the clipboard must not be told it succeeded: the
  // hiker would walk away believing they had the details and paste nothing.
  it('admits it when the clipboard is refused, and says what to read instead', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('navigator', {
      ...navigator,
      clipboard: {
        writeText: () => Promise.reject(new Error('Write permission denied.')),
      },
    })
    render(<AboutBuild build={RELEASE} />)

    await user.click(screen.getByRole('button', { name: /copy build details/i }))

    expect(
      await screen.findByText(/would not let the app use the clipboard/i),
    ).toBeInTheDocument()
    expect(screen.queryByText('Copied.')).not.toBeInTheDocument()
    // The rows it points at are still there to be read off.
    expect(screen.getByText('6e23f12')).toBeInTheDocument()
  })

  it('says nothing about copying until someone has tried to', () => {
    render(<AboutBuild build={RELEASE} />)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows unknown rather than a blank where the build could not say', () => {
    render(<AboutBuild build={readBuildInfo({ version: '', commit: '', builtAt: '' })} />)

    expect(screen.getAllByText('unknown').length).toBeGreaterThan(0)
  })
})

describe('how long this launch took (#1299)', () => {
  const TIMELINE = [
    { name: 'ourhike:script', label: 'App code started', at: 210 },
    { name: 'ourhike:shell', label: 'Tab bar rendered', at: 480 },
    { name: 'ourhike:today', label: 'Waypoints ready', at: null },
  ]

  it('shows each moment in milliseconds from when the page began loading', () => {
    render(<AboutBuild build={RELEASE} launch={TIMELINE} />)

    expect(screen.getByText('Tab bar rendered')).toBeInTheDocument()
    expect(screen.getByText('480 ms')).toBeInTheDocument()
  })

  it('says a moment the launch never reached, rather than leaving it out', () => {
    // An omitted row reads as "instant" to whoever is looking at it, which is
    // the display outrunning its source.
    render(<AboutBuild build={RELEASE} launch={TIMELINE} />)

    expect(screen.getByText('Waypoints ready')).toBeInTheDocument()
    expect(screen.getByText('not reached')).toBeInTheDocument()
  })

  it('carries the timings into the copied text, beside the build', async () => {
    // The path this has to survive is somebody pasting into an email, and the
    // timings are the half of "it takes six seconds" that nobody can retype.
    // Read back from the clipboard rather than from a spy, like the build's
    // own copy test above: what matters is what a hiker can paste.
    const user = userEvent.setup()
    render(<AboutBuild build={RELEASE} launch={TIMELINE} />)

    await user.click(screen.getByRole('button', { name: /copy build details/i }))

    const copied = await navigator.clipboard.readText()
    expect(copied).toContain('1.0.0')
    expect(copied).toContain('Tab bar rendered 480')
    // Still one line - a line break is where a paste gets half-quoted.
    expect(copied).not.toContain('\n')
  })

  it('says plainly that the numbers go nowhere on their own', () => {
    // There is no telemetry in this client (TECHNICAL_ARCHITECTURE.md), and a
    // screen full of timings is exactly where somebody would assume otherwise.
    render(<AboutBuild build={RELEASE} launch={TIMELINE} />)

    expect(
      screen.getByText(/nothing sends them anywhere on its own/i),
    ).toBeInTheDocument()
  })
})
