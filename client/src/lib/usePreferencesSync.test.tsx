import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePreferencesSync, PUSH_SETTLE_MS } from './usePreferencesSync'
import { pushPreferencesIfChanged, syncPreferences } from './preferencesSync'
import { DEFAULT_PREFERENCES, type UserPreferences } from './userPreferences'

// WHEN the reconciliation runs (#891) - "pull on sign-in, push on change".
//
// The rule itself is tested in preferencesSync.test.ts. What is tested here
// is the wiring, and the two ways it can be wrong are both silent:
//
//   - running the pull while signed out, which spends a request that can
//     only ever come back 401; and
//   - pushing on a render rather than on a change, which turns every
//     re-render of the app into a PUT.

vi.mock('./preferencesSync', () => ({
  syncPreferences: vi.fn(),
  pushPreferencesIfChanged: vi.fn(),
}))

const NOOP = () => {}

beforeEach(() => {
  vi.useFakeTimers()
  vi.mocked(syncPreferences).mockReset().mockResolvedValue(null)
  vi.mocked(pushPreferencesIfChanged).mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  vi.useRealTimers()
})

function mount(preferences: UserPreferences, signedIn: boolean, onAdopt = NOOP) {
  return renderHook(
    ({ prefs, signed }: { prefs: UserPreferences; signed: boolean }) =>
      usePreferencesSync(prefs, signed, onAdopt),
    { initialProps: { prefs: preferences, signed: signedIn } },
  )
}

describe('pulling on sign-in', () => {
  it('asks the account for nothing while signed out', () => {
    mount(DEFAULT_PREFERENCES, false)

    expect(syncPreferences).not.toHaveBeenCalled()
  })

  it('reconciles once when the app opens already signed in', () => {
    mount(DEFAULT_PREFERENCES, true)

    expect(syncPreferences).toHaveBeenCalledOnce()
  })

  it('reconciles when a signed-out hiker signs in', () => {
    const view = mount(DEFAULT_PREFERENCES, false)

    view.rerender({ prefs: DEFAULT_PREFERENCES, signed: true })

    expect(syncPreferences).toHaveBeenCalledOnce()
  })

  it('does not reconcile again because a preference changed', () => {
    // The pull is a sign-in event. Re-running it per toggle would spend a
    // GET on every tap, and could pull the account's blob back over the
    // change the hiker is in the middle of making.
    const view = mount(DEFAULT_PREFERENCES, true)

    view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme: 'dark' }, signed: true })

    expect(syncPreferences).toHaveBeenCalledOnce()
  })

  it('hands the account’s preferences to the caller when they win', async () => {
    const adopted = { ...DEFAULT_PREFERENCES, theme: 'dark' as const }
    vi.mocked(syncPreferences).mockResolvedValue(adopted)
    const onAdopt = vi.fn()

    mount(DEFAULT_PREFERENCES, true, onAdopt)
    // The promise, not the timer: awaiting an observable effect rather than
    // a duration is what stops this passing on an idle machine and failing
    // in CI.
    await act(async () => {
      await vi.mocked(syncPreferences).mock.results[0]?.value
    })

    expect(onAdopt).toHaveBeenCalledWith(adopted)
  })

  it('says nothing to the caller when there is nothing to adopt', async () => {
    const onAdopt = vi.fn()

    mount(DEFAULT_PREFERENCES, true, onAdopt)
    await act(async () => {
      await vi.mocked(syncPreferences).mock.results[0]?.value
    })

    expect(onAdopt).not.toHaveBeenCalled()
  })

  it('does not adopt into an unmounted app', async () => {
    let settle: (value: UserPreferences | null) => void = NOOP
    vi.mocked(syncPreferences).mockReturnValue(
      new Promise((resolve) => {
        settle = resolve
      }),
    )
    const onAdopt = vi.fn()

    const view = mount(DEFAULT_PREFERENCES, true, onAdopt)
    view.unmount()
    await act(async () => {
      settle({ ...DEFAULT_PREFERENCES, theme: 'dark' })
    })

    expect(onAdopt).not.toHaveBeenCalled()
  })
})

describe('pushing on change', () => {
  it('sends nothing while signed out, however much changes', () => {
    const view = mount(DEFAULT_PREFERENCES, false)

    view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme: 'dark' }, signed: false })
    act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS * 4))

    expect(pushPreferencesIfChanged).not.toHaveBeenCalled()
  })

  it('lets a burst of toggles settle into one push', () => {
    // The legend's category switches are tapped in runs. Four taps must not
    // be four round trips on a connection this app assumes is bad.
    const view = mount(DEFAULT_PREFERENCES, true)

    for (const theme of ['dark', 'light', 'auto'] as const) {
      view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme }, signed: true })
      act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS / 3))
    }
    expect(pushPreferencesIfChanged).not.toHaveBeenCalled()

    // Advancing the timer runs the callback synchronously, so the call has
    // already happened by the time this line is reached - no waiting, and
    // therefore nothing that can pass on an idle machine and fail on CI.
    act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS))
    expect(pushPreferencesIfChanged).toHaveBeenCalledOnce()
  })

  it('sends the values as they stand when the burst settles, not as they were', () => {
    const view = mount(DEFAULT_PREFERENCES, true)

    view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme: 'dark' }, signed: true })
    act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS + 1))

    expect(pushPreferencesIfChanged).toHaveBeenCalledWith(
      expect.objectContaining({ theme: 'dark' }),
    )
  })

  it('sends nothing after the app closes mid-burst', () => {
    const view = mount(DEFAULT_PREFERENCES, true)
    view.rerender({ prefs: { ...DEFAULT_PREFERENCES, theme: 'dark' }, signed: true })

    view.unmount()
    act(() => vi.advanceTimersByTime(PUSH_SETTLE_MS * 4))

    expect(pushPreferencesIfChanged).not.toHaveBeenCalled()
  })
})
