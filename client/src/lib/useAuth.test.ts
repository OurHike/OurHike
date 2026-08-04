import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act, cleanup } from '@testing-library/react'
import { useAccount } from './useAuth'
import { currentAccount, subscribeToAccount, type Account } from './auth'

vi.mock('./auth', () => ({
  currentAccount: vi.fn(),
  subscribeToAccount: vi.fn(),
}))

const mockedCurrent = vi.mocked(currentAccount)
const mockedSubscribe = vi.mocked(subscribeToAccount)

const HIKER: Account = { email: 'hiker@example.com' }

/** Captures the listener so a test can drive a session change. */
function capturingSubscribe() {
  let emit: ((account: Account | null) => void) | undefined
  const unsubscribe = vi.fn()
  mockedSubscribe.mockImplementation((listener) => {
    emit = listener
    return unsubscribe
  })
  return { fire: (account: Account | null) => act(() => emit?.(account)), unsubscribe }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedCurrent.mockResolvedValue(null)
  mockedSubscribe.mockReturnValue(() => {})
})

afterEach(cleanup)

describe('useAccount', () => {
  it('starts signed out, which is the state the whole app works in', () => {
    const { result } = renderHook(() => useAccount())

    expect(result.current).toBe(null)
  })

  it('restores a stored session', async () => {
    mockedCurrent.mockResolvedValue(HIKER)

    const { result } = renderHook(() => useAccount())

    await waitFor(() => expect(result.current).toEqual(HIKER))
  })

  it('notices a sign-in that happened after the first render', async () => {
    // Which is the normal case for OAuth: the round trip finishes by loading
    // the page again, not by resolving a promise in the tab that left.
    const { fire } = capturingSubscribe()
    const { result } = renderHook(() => useAccount())

    fire(HIKER)

    await waitFor(() => expect(result.current).toEqual(HIKER))
  })

  it('notices a sign-out', async () => {
    const { fire } = capturingSubscribe()
    mockedCurrent.mockResolvedValue(HIKER)
    const { result } = renderHook(() => useAccount())
    await waitFor(() => expect(result.current).toEqual(HIKER))

    fire(null)

    await waitFor(() => expect(result.current).toBe(null))
  })

  it('subscribes before asking, so a session arriving in between is not missed', () => {
    const order: string[] = []
    mockedSubscribe.mockImplementation(() => {
      order.push('subscribe')
      return () => {}
    })
    mockedCurrent.mockImplementation(() => {
      order.push('ask')
      return Promise.resolve(null)
    })

    renderHook(() => useAccount())

    expect(order).toEqual(['subscribe', 'ask'])
  })

  it('does not let a slow restore overwrite a newer sign-out', async () => {
    // The stored session resolves after the subscription has already reported
    // the account is gone. Preferring the older answer would put a hiker back
    // to looking signed in immediately after signing out.
    const { fire } = capturingSubscribe()
    let resolveRestore: (account: Account | null) => void = () => {}
    mockedCurrent.mockReturnValue(
      new Promise<Account | null>((resolve) => {
        resolveRestore = resolve
      }),
    )
    const { result } = renderHook(() => useAccount())

    fire(null)
    await act(async () => {
      resolveRestore(HIKER)
    })

    expect(result.current).toBe(null)
  })

  it('unsubscribes when the component goes away', () => {
    const { unsubscribe } = capturingSubscribe()
    const { unmount } = renderHook(() => useAccount())

    unmount()

    expect(unsubscribe).toHaveBeenCalled()
  })

  it('ignores a restore that lands after unmount', async () => {
    // Setting state on an unmounted component is a warning at best and a leak
    // at worst, and a slow network makes this ordinary rather than exotic.
    let resolveRestore: (account: Account | null) => void = () => {}
    mockedCurrent.mockReturnValue(
      new Promise<Account | null>((resolve) => {
        resolveRestore = resolve
      }),
    )
    const { unmount } = renderHook(() => useAccount())

    unmount()

    await expect(
      act(async () => {
        resolveRestore(HIKER)
      }),
    ).resolves.not.toThrow()
  })
})
