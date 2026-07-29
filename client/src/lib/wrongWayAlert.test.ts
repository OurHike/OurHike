import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createWrongWayMonitor } from './wrongWayAlert'
import { CUE_PERSISTENCE_MS, PUSH_PERSISTENCE_MS } from './wrongWay'

// WIREFRAMES.md §9, wiring D4's pure detection math to the push chokepoint.
//
// Three properties matter more than the rest:
//
// 1. A CUE NEVER PUSHES. The in-app cue is the conservative first beat;
//    escalating to an interrupt is a separate, later decision. If the cue
//    could push, the whole graduated design collapses into one alarm.
//
// 2. IT WON'T ASK AGAIN. WIREFRAMES.md says so outright. `detectWrongWay`
//    reports 'push' for every sample once divergence is sustained, so
//    without suppression this would fire on every GPS tick - turning the one
//    notification OurHike sends into a stream of them, which is the fastest
//    possible way to lose the trust it was designed around.
//
// 3. THE ALERT IS LOCAL. Detection is local maths and the notification is
//    local; the backend relay is telemetry. Being offline is the normal case
//    on this trail, and it must never suppress the alert.

const diverging = (atMs: number) => ({
  timestampMs: atMs,
  distanceFromTrailFt: 150,
  bearingDeltaDeg: 175,
})

const onTrack = (atMs: number) => ({
  timestampMs: atMs,
  distanceFromTrailFt: 10,
  bearingDeltaDeg: 0,
})

const CUE_TRACE = [diverging(0), diverging(CUE_PERSISTENCE_MS + 1000)]
const PUSH_TRACE = [...CUE_TRACE, diverging(PUSH_PERSISTENCE_MS + 1000)]

function monitor(overrides: Record<string, unknown> = {}) {
  const publish = vi.fn().mockResolvedValue(true)
  const relay = vi.fn().mockResolvedValue(undefined)
  const instance = createWrongWayMonitor(
    { enabled: true, hikeId: 'h1', direction: 'NOBO', ...overrides },
    { publish, relay },
  )
  return { instance, publish, relay }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('createWrongWayMonitor', () => {
  it('does nothing while on track', async () => {
    const { instance, publish } = monitor()

    const outcome = await instance.observe([onTrack(0), onTrack(60_000)])

    expect(outcome).toMatchObject({ cue: false, pushed: false })
    expect(publish).not.toHaveBeenCalled()
  })

  it('raises an in-app cue without ever pushing', async () => {
    const { instance, publish } = monitor()

    const outcome = await instance.observe(CUE_TRACE)

    expect(outcome.cue).toBe(true)
    expect(outcome.pushed).toBe(false)
    expect(publish).not.toHaveBeenCalled()
  })

  it('pushes once divergence is sustained past the push threshold', async () => {
    const { instance, publish } = monitor()

    const outcome = await instance.observe(PUSH_TRACE)

    expect(outcome.pushed).toBe(true)
    expect(publish).toHaveBeenCalledTimes(1)
  })

  it('does not ask again for the same episode', async () => {
    // The trace keeps reporting 'push' on every later sample; only the first
    // should reach the notification.
    const { instance, publish } = monitor()

    await instance.observe(PUSH_TRACE)
    await instance.observe([...PUSH_TRACE, diverging(PUSH_PERSISTENCE_MS + 60_000)])

    expect(publish).toHaveBeenCalledTimes(1)
  })

  it('may push again after the hiker gets back on track and later diverges anew', async () => {
    const { instance, publish } = monitor()

    await instance.observe(PUSH_TRACE)
    await instance.observe([onTrack(PUSH_PERSISTENCE_MS + 120_000)])
    await instance.observe([
      diverging(PUSH_PERSISTENCE_MS + 200_000),
      diverging(PUSH_PERSISTENCE_MS * 2 + 400_000),
    ])

    expect(publish).toHaveBeenCalledTimes(2)
  })

  it('mentions the hike direction, so the alert says why it thinks this', async () => {
    const { instance, publish } = monitor()

    await instance.observe(PUSH_TRACE)

    expect(publish.mock.calls[0][0].body).toMatch(/NOBO/)
  })

  it('stays silent entirely when the hiker has turned the alert off', async () => {
    const { instance, publish } = monitor({ enabled: false })

    const outcome = await instance.observe(PUSH_TRACE)

    expect(outcome).toMatchObject({ cue: false, pushed: false })
    expect(publish).not.toHaveBeenCalled()
  })

  it('still alerts when the backend relay fails - the alert is local', async () => {
    const publish = vi.fn().mockResolvedValue(true)
    const relay = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const instance = createWrongWayMonitor(
      { enabled: true, hikeId: 'h1', direction: 'NOBO' },
      { publish, relay },
    )

    const outcome = await instance.observe(PUSH_TRACE)

    expect(outcome.pushed).toBe(true)
    expect(publish).toHaveBeenCalledTimes(1)
  })

  it('never rejects because the relay did', async () => {
    const publish = vi.fn().mockResolvedValue(true)
    const relay = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    const instance = createWrongWayMonitor(
      { enabled: true, hikeId: 'h1', direction: 'NOBO' },
      { publish, relay },
    )

    await expect(instance.observe(PUSH_TRACE)).resolves.toBeDefined()
  })

  it('relays the event when a hike is under way', async () => {
    const { instance, relay } = monitor()

    await instance.observe(PUSH_TRACE)

    expect(relay).toHaveBeenCalledWith(expect.objectContaining({ hikeId: 'h1' }))
  })

  it('skips the relay when there is no hike to attach it to', async () => {
    const { instance, relay, publish } = monitor({ hikeId: null })

    await instance.observe(PUSH_TRACE)

    expect(relay).not.toHaveBeenCalled()
    // ...but the alert itself is unaffected.
    expect(publish).toHaveBeenCalledTimes(1)
  })

  it('does not relay a mere cue - only a real escalation is worth reporting', async () => {
    const { instance, relay } = monitor()

    await instance.observe(CUE_TRACE)

    expect(relay).not.toHaveBeenCalled()
  })
})
