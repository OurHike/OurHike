import { afterEach, expect, it, vi } from 'vitest'
import { watchForUpdates } from './update'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

/** A browser's service worker container, as much of it as update.ts touches. */
function workers({ controlled, waiting }: { controlled: boolean; waiting: boolean }) {
  const posted: unknown[] = []
  const worker = { postMessage: (message: unknown) => posted.push(message) }
  const registration = {
    waiting: waiting ? worker : null,
    installing: null,
    addEventListener: vi.fn(),
  }
  const container = {
    controller: controlled ? {} : null,
    register: vi.fn(async () => registration),
    addEventListener: vi.fn(),
  }
  vi.stubGlobal('navigator', { ...navigator, serviceWorker: container })
  return { container, posted }
}

it('offers a waiting new version and switches to it only when asked', async () => {
  // The third pass's P4: a new version took over under an open page and
  // removed files that page still had to load.
  vi.stubEnv('PROD', true)
  const { container, posted } = workers({ controlled: true, waiting: true })
  const offered = new Promise<() => void>((resolve) => watchForUpdates(resolve))
  const apply = await offered
  expect(container.register).toHaveBeenCalledWith('./sw.js', { scope: './' })
  expect(posted).toEqual([])
  apply()
  expect(posted).toEqual([{ type: 'SKIP_WAITING' }])
  expect(container.addEventListener).toHaveBeenCalledWith(
    'controllerchange',
    expect.any(Function),
    { once: true },
  )
})

it('offers nothing on the first install, when there is no old version to replace', async () => {
  vi.stubEnv('PROD', true)
  const { container } = workers({ controlled: false, waiting: true })
  const onReady = vi.fn()
  watchForUpdates(onReady)
  await vi.waitFor(() => expect(container.register).toHaveBeenCalled())
  await Promise.resolve()
  expect(onReady).not.toHaveBeenCalled()
})

it('registers nothing outside a production build', () => {
  const { container } = workers({ controlled: true, waiting: true })
  watchForUpdates(vi.fn())
  expect(container.register).not.toHaveBeenCalled()
})
