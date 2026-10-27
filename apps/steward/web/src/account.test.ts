import { afterEach, expect, it, vi } from 'vitest'
import { AUTH_STORAGE_KEY, endSession } from './account'

afterEach(() => window.localStorage.clear())

function storedSession() {
  window.localStorage.setItem(AUTH_STORAGE_KEY, '{"refresh_token":"r"}')
  window.localStorage.setItem(`${AUTH_STORAGE_KEY}-user`, '{"id":"user-1"}')
}

it('signs out of this browser only, never every device the person uses OurHike on', async () => {
  const signOut = vi.fn(async () => ({ error: null }))
  await endSession({ signOut }, window.localStorage)
  expect(signOut).toHaveBeenCalledWith({ scope: 'local' })
})

it('removes the stored session itself when supabase-js could not sign out for lack of signal', async () => {
  // The third pass's P3: with an expired access token and no signal,
  // supabase-js returned an error and left the session and its refresh token
  // stored, so the next person on a shared phone was signed in as this one.
  storedSession()
  await endSession(
    { signOut: async () => ({ error: new Error('Failed to fetch') }) },
    window.localStorage,
  )
  expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull()
  expect(window.localStorage.getItem(`${AUTH_STORAGE_KEY}-user`)).toBeNull()
})

it('removes it as well when supabase-js throws rather than answering', async () => {
  storedSession()
  await endSession(
    {
      signOut: async () => {
        throw new TypeError('Failed to fetch')
      },
    },
    window.localStorage,
  )
  expect(window.localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull()
})
