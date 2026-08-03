import { describe, it, expect, afterEach } from 'vitest'
import { renderHook, act, cleanup } from '@testing-library/react'
import { useDataSaver } from './useDataSaver'

// The subscription is the reason this is a hook rather than a one-off read: a
// hiker who notices the map eating data turns Data Saver on from the
// notification shade without leaving the app, and the map has to follow in the
// same breath rather than at the next cold start.

class FakeConnection {
  saveData: boolean
  readonly listeners: Array<() => void> = []

  constructor(saveData: boolean) {
    this.saveData = saveData
  }

  addEventListener(_type: 'change', listener: () => void): void {
    this.listeners.push(listener)
  }

  removeEventListener(_type: 'change', listener: () => void): void {
    const at = this.listeners.indexOf(listener)
    if (at !== -1) this.listeners.splice(at, 1)
  }

  /** What the OS does when the hiker flips Data Saver. */
  change(saveData: boolean): void {
    this.saveData = saveData
    for (const listener of [...this.listeners]) listener()
  }
}

function setConnection(connection: unknown): void {
  Object.defineProperty(navigator, 'connection', {
    value: connection,
    configurable: true,
    writable: true,
  })
}

afterEach(() => {
  cleanup()
  Reflect.deleteProperty(navigator, 'connection')
})

describe('useDataSaver', () => {
  it('reports what the connection says on first render', () => {
    setConnection(new FakeConnection(true))

    expect(renderHook(() => useDataSaver()).result.current).toBe(true)
  })

  it('follows Data Saver being switched on mid-session', () => {
    const connection = new FakeConnection(false)
    setConnection(connection)
    const { result } = renderHook(() => useDataSaver())

    expect(result.current).toBe(false)
    act(() => connection.change(true))

    expect(result.current).toBe(true)
  })

  it('follows it being switched back off', () => {
    const connection = new FakeConnection(true)
    setConnection(connection)
    const { result } = renderHook(() => useDataSaver())

    act(() => connection.change(false))

    expect(result.current).toBe(false)
  })

  it('unsubscribes on unmount rather than leaking a listener per mount', () => {
    // The map screen unmounts on every trip to another tab, so a listener left
    // behind here accumulates one per visit for the life of the session.
    const connection = new FakeConnection(false)
    setConnection(connection)
    const { unmount } = renderHook(() => useDataSaver())

    expect(connection.listeners).toHaveLength(1)
    unmount()

    expect(connection.listeners).toHaveLength(0)
  })

  it('renders fine where the API does not exist, which is every iPhone', () => {
    const { result, unmount } = renderHook(() => useDataSaver())

    expect(result.current).toBe(false)
    // The teardown path has nothing to unsubscribe from and must not reach for
    // it anyway.
    expect(() => unmount()).not.toThrow()
  })

  it('survives a connection that reports saveData but cannot be subscribed to', () => {
    // A partial implementation is likelier than none: the spec's fields are all
    // optional and browsers have shipped subsets. Reading still works; only the
    // live updates are lost.
    setConnection({ saveData: true })

    expect(renderHook(() => useDataSaver()).result.current).toBe(true)
  })
})
