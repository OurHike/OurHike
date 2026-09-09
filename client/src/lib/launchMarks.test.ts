import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LAUNCH_MARKS, launchSummary, launchTimeline, markLaunch } from './launchMarks'

beforeEach(() => {
  performance.clearMarks()
})

afterEach(() => {
  performance.clearMarks()
  vi.restoreAllMocks()
})

describe('marking a launch', () => {
  it('records the first time a moment happens, not the last', () => {
    // Every mark answers "when did the launch reach this". A re-render
    // reaching the same line again is answering a different question.
    markLaunch(LAUNCH_MARKS.shell)
    const first = performance.getEntriesByName(LAUNCH_MARKS.shell, 'mark')[0].startTime
    markLaunch(LAUNCH_MARKS.shell)

    const marks = performance.getEntriesByName(LAUNCH_MARKS.shell, 'mark')
    expect(marks).toHaveLength(1)
    expect(marks[0].startTime).toBe(first)
  })

  it('costs the readout rather than the launch where performance.mark throws', () => {
    vi.spyOn(performance, 'mark').mockImplementation(() => {
      throw new Error('no buffer')
    })

    expect(() => markLaunch(LAUNCH_MARKS.script)).not.toThrow()
  })
})

describe('reading a launch back', () => {
  it('says a moment the launch has not reached is not reached, rather than zero', () => {
    // "The waypoints are not ready yet" and "the waypoints were ready
    // immediately" are different answers, and a readout that confused them
    // would be a display outrunning its source.
    markLaunch(LAUNCH_MARKS.script)

    const timeline = launchTimeline()

    const today = timeline.find((moment) => moment.name === LAUNCH_MARKS.today)
    expect(today?.at).toBeNull()
    expect(timeline.find((moment) => moment.name === LAUNCH_MARKS.script)?.at).toEqual(
      expect.any(Number),
    )
  })

  it('keeps the moments in the order a launch reaches them', () => {
    for (const name of Object.values(LAUNCH_MARKS)) markLaunch(name)

    const names = launchTimeline()
      .map((moment) => moment.name)
      .filter((name) => name !== 'first-contentful-paint')

    expect(names).toEqual([
      LAUNCH_MARKS.script,
      LAUNCH_MARKS.shell,
      LAUNCH_MARKS.preferences,
      LAUNCH_MARKS.today,
      LAUNCH_MARKS.index,
    ])
  })

  it('names every moment in the summary, unreached ones out loud', () => {
    // An omitted row reads as "fast" to whoever is reading the issue.
    markLaunch(LAUNCH_MARKS.script)
    markLaunch(LAUNCH_MARKS.shell)

    const summary = launchSummary()

    expect(summary).toContain('Tab bar on screen')
    expect(summary).toContain('Waypoints ready not reached')
  })

  it('says so plainly on a browser that recorded nothing', () => {
    expect(launchSummary([])).toBe('Launch timings: not recorded on this browser')
  })
})
