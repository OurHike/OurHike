import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, cleanup, act } from '@testing-library/react'
import { useModerator } from './useModerator'
import { fetchMyProfile } from './api'

// #235: the client had never read a role. What matters here is not the happy
// path but which way this fails - the answer only decides whether a menu
// entry appears, and the backend enforces the role on every call regardless,
// so "unknown" has to read as "no".

vi.mock('./api', () => ({ fetchMyProfile: vi.fn() }))

const mockedFetch = vi.mocked(fetchMyProfile)

/**
 * Waits until the fetch has resolved AND its handlers have run.
 *
 * `waitFor(() => expect(mockedFetch).toHaveBeenCalled())` is not enough and
 * the difference is the whole test: the call happens synchronously inside the
 * effect, so that assertion passes before the promise settles - and a version
 * of this hook that set `true` in its `catch` would pass it too. Flushing the
 * microtasks is what makes "still false" a claim about the handler having run
 * rather than about it not having run yet.
 */
async function settled() {
  await waitFor(() => expect(mockedFetch).toHaveBeenCalled())
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

function profile(role: string) {
  return { id: 'p-1', role: role as 'hiker', display_name: null }
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  cleanup()
})

describe('useModerator', () => {
  it('is false before the answer arrives', () => {
    mockedFetch.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useModerator(true))

    expect(result.current).toBe(false)
  })

  it.each(['maintainer', 'club_admin'])('is true for a %s', async (role) => {
    mockedFetch.mockResolvedValue(profile(role))

    const { result } = renderHook(() => useModerator(true))

    await waitFor(() => expect(result.current).toBe(true))
  })

  it('is false for a hiker', async () => {
    mockedFetch.mockResolvedValue(profile('hiker'))

    const { result } = renderHook(() => useModerator(true))

    await settled()
    expect(result.current).toBe(false)
  })

  it('does not ask at all when signed out', () => {
    renderHook(() => useModerator(false))

    expect(mockedFetch).not.toHaveBeenCalled()
  })

  it('stays false when the request fails', async () => {
    // No signal, an expired token, a build with no backend. Offering a
    // maintainer's screen on a guess costs a 403 the person cannot act on.
    mockedFetch.mockRejectedValue(new Error('no signal'))

    const { result } = renderHook(() => useModerator(true))

    await settled()
    expect(result.current).toBe(false)
  })

  it('forgets the role on sign-out', async () => {
    // A shared device: without this, the previous account's moderator entry
    // survives until reload.
    mockedFetch.mockResolvedValue(profile('maintainer'))
    const { result, rerender } = renderHook(({ on }) => useModerator(on), {
      initialProps: { on: true },
    })
    await waitFor(() => expect(result.current).toBe(true))

    rerender({ on: false })

    expect(result.current).toBe(false)
  })

  it('asks again when somebody signs in mid-session', async () => {
    mockedFetch.mockResolvedValue(profile('maintainer'))
    const { result, rerender } = renderHook(({ on }) => useModerator(on), {
      initialProps: { on: false },
    })
    expect(mockedFetch).not.toHaveBeenCalled()

    rerender({ on: true })

    await waitFor(() => expect(result.current).toBe(true))
  })
})
