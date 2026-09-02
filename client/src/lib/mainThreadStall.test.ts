// The main-thread meter (lib/mainThreadStall.ts).
//
// Every assertion here is about a way the column could LIE, because the whole
// value of adding it is that an analyst trusts what it says. A meter that
// double-counts one jam across two rows, or that hands the first fix of a
// recording every long task since page load, or that quietly reports 0 on a
// browser that cannot measure at all, is worse than no column - it looks like
// evidence and is not.

import { afterEach, describe, expect, it, vi } from 'vitest'

import { createStallMeter, longTaskObservationSupported } from './mainThreadStall'

/** A stand-in for the browser's own observer, so a test can decide when a
 *  long task happens instead of trying to jam a real event loop. */
function stubObserver({ supported = true }: { supported?: boolean } = {}) {
  const state = {
    /** Every observer still connected. A `stop` that fails to disconnect
     *  leaves one here, which is what the teardown test reads. */
    live: new Set<{ fire: (...durations: number[]) => void }>(),
    /** What `observe` was called with, so the buffered-entries choice is
     *  asserted rather than assumed. */
    options: [] as PerformanceObserverInit[],
  }

  class FakeObserver {
    private handle: { fire: (...durations: number[]) => void }

    private callback: PerformanceObserverCallback

    constructor(callback: PerformanceObserverCallback) {
      this.callback = callback
      this.handle = {
        fire: (...durations: number[]) => {
          const entries = durations.map((duration) => ({
            duration,
          })) as PerformanceEntry[]
          this.callback(
            { getEntries: () => entries } as PerformanceObserverEntryList,
            this as unknown as PerformanceObserver,
          )
        },
      }
    }

    observe(options: PerformanceObserverInit) {
      state.options.push(options)
      state.live.add(this.handle)
    }

    disconnect() {
      state.live.delete(this.handle)
    }

    takeRecords() {
      return []
    }

    static supportedEntryTypes = supported ? ['longtask', 'mark'] : ['mark']
  }

  vi.stubGlobal('PerformanceObserver', FakeObserver)

  return {
    ...state,
    /** Deliver long tasks of these durations to every live observer. */
    fire(...durations: number[]) {
      for (const handle of state.live) handle.fire(...durations)
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createStallMeter', () => {
  it('sums the long tasks in the interval ending at a reading', () => {
    const browser = stubObserver()
    const meter = createStallMeter()
    meter.start()

    browser.fire(120, 62)

    expect(meter.take()).toEqual({ blockedMs: 182, worstMs: 120 })
  })

  it('drains, so one jam is never counted on two rows', () => {
    // The failure this prevents is an analyst reading a single 400 ms freeze
    // as a phone that stalled on every fix for a minute - the trace would
    // look catastrophically worse than the app is.
    const browser = stubObserver()
    const meter = createStallMeter()
    meter.start()

    browser.fire(400)
    expect(meter.take().blockedMs).toBe(400)

    expect(meter.take()).toEqual({ blockedMs: 0, worstMs: 0 })
  })

  it('keeps the worst single task apart from the total', () => {
    // 200 ms as one task is a visible freeze; as four tasks it is a slightly
    // sticky screen. One column cannot say which.
    const browser = stubObserver()
    const meter = createStallMeter()
    meter.start()

    browser.fire(52, 51, 53, 54)

    expect(meter.take()).toEqual({ blockedMs: 210, worstMs: 54 })
  })

  it('remembers the worst of the whole recording, not of the interval', () => {
    const browser = stubObserver()
    const meter = createStallMeter()
    meter.start()

    browser.fire(310)
    meter.take()
    browser.fire(60)
    meter.take()

    // The screen's row: a tester who looked away must still learn that the
    // app froze for a third of a second at some point.
    expect(meter.worst()).toBe(310)
  })

  it('says nothing rather than zero before anything crosses the threshold', () => {
    stubObserver()
    const meter = createStallMeter()
    meter.start()

    expect(meter.worst()).toBeNull()
  })

  it('does not ask for buffered entries, which belong to an earlier interval', () => {
    // Buffered entries would hand the FIRST fix of a recording every long task
    // since page load - the map build among them, which is a real stall and is
    // emphatically not one that happened in that five-second interval. The
    // column claims to measure an interval and has to.
    const browser = stubObserver()
    createStallMeter().start()

    expect(browser.options).toEqual([{ type: 'longtask' }])
  })

  it('stops observing when the recording stops', () => {
    // An observer outliving its recording would keep accumulating through
    // whatever the hiker did next and dump it on the first fix of the NEXT
    // walk, which is the same lie as buffered entries by a slower route.
    const browser = stubObserver()
    const meter = createStallMeter()
    meter.start()
    meter.stop()

    expect(browser.live.size).toBe(0)

    browser.fire(500)
    expect(meter.take()).toEqual({ blockedMs: 0, worstMs: 0 })
  })

  it('starts each recording from nothing', () => {
    const browser = stubObserver()
    const meter = createStallMeter()
    meter.start()
    browser.fire(900)
    meter.stop()

    meter.start()

    expect(meter.worst()).toBeNull()
    expect(meter.take()).toEqual({ blockedMs: 0, worstMs: 0 })
  })

  it('reports NOT MEASURED, never zero, where the browser cannot measure', () => {
    // The whole of iOS. A meter that answered 0 here would put a reassuring
    // number in every row of an iPhone trace and quietly retire the question.
    stubObserver({ supported: false })
    const meter = createStallMeter()
    meter.start()

    expect(meter.supported).toBe(false)
    expect(meter.take()).toEqual({ blockedMs: null, worstMs: null })
    expect(meter.worst()).toBeNull()
  })

  it('reports not measured where there is no PerformanceObserver at all', () => {
    vi.stubGlobal('PerformanceObserver', undefined)

    expect(longTaskObservationSupported()).toBe(false)
    expect(createStallMeter().supported).toBe(false)
  })

  it('survives start being called twice without stacking observers', () => {
    const browser = stubObserver()
    const meter = createStallMeter()
    meter.start()
    meter.start()

    browser.fire(100)

    // Two observers would have counted it twice, and React effects re-run.
    expect(meter.take().blockedMs).toBe(100)
  })
})
