import { describe, it, expect, vi, afterEach } from 'vitest'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
// Imported explicitly rather than used as a global: tsconfig.app.json keeps
// node out of `types` on purpose, so browser code cannot reach for
// process.env and still typecheck. This test genuinely needs Node, so it asks
// for it by name instead of widening the app's config.
import { cwd } from 'node:process'
import { publishWrongWayAlert } from './push'

// TESTING.md invariant 17: "Serious warnings never enqueue a push; the
// wrong-way alert is the only push publisher in the client codebase."
//
// That is a CODEBASE-level claim, so it is checked at codebase level. A
// per-component test ("the warning sheet does not push") only proves the
// component someone thought to test; scanning the source proves the rule
// itself, including for a file nobody has written yet.
//
// This matters because the rule erodes one reasonable exception at a time.
// Every "but this one is genuinely urgent" is defensible alone, and the sum
// is an app that interrupts people on a mountain - which spends the trust
// budget the single alert was designed around (HIKER_SAFETY.md's own framing).

// Resolved from the working directory rather than import.meta.url, which
// vitest does not hand back as a file:// URL. Both candidates are checked so
// this works whether the suite is run from the repo root or from client/.
// The "actually has files in it" test below is what catches a bad path.
const SRC = [join(cwd(), 'src'), join(cwd(), 'client', 'src')].find((candidate) =>
  existsSync(candidate),
) as string

/** Anything that would actually surface an OS-level notification. */
const NOTIFICATION_APIS = [
  'new Notification(',
  'showNotification(',
  'requestPermission(',
  'pushManager',
]

// The chokepoint itself, and this test. Nothing else.
const ALLOWED = ['lib\\push.ts', 'lib/push.ts', 'lib\\push.test.ts', 'lib/push.test.ts']

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry: string) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) return sourceFiles(full)
    return /\.(ts|tsx)$/.test(entry) ? [full] : []
  })
}

describe('the one-notification policy, as a codebase invariant', () => {
  it('has exactly one module that touches a notification API', () => {
    const offenders = sourceFiles(SRC)
      .filter((file) => !ALLOWED.some((allowed) => file.endsWith(allowed)))
      .filter((file) => {
        const text = readFileSync(file, 'utf8')
        return NOTIFICATION_APIS.some((api) => text.includes(api))
      })
      .map((file) => file.slice(SRC.length))

    expect(offenders).toEqual([])
  })

  it('scans a source tree that actually has files in it', () => {
    // Guards the guard: a broken path would make the test above pass
    // vacuously forever.
    expect(sourceFiles(SRC).length).toBeGreaterThan(20)
  })

  it('would notice a violation if one were introduced', () => {
    // Proves the matcher works, rather than trusting that it does.
    const pretendModule = "export function ping() { new Notification('hi') }"

    expect(NOTIFICATION_APIS.some((api) => pretendModule.includes(api))).toBe(true)
  })
})

describe('publishWrongWayAlert', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends nothing when permission has not been granted', async () => {
    const spy = vi.fn()
    vi.stubGlobal(
      'Notification',
      Object.assign(spy, { permission: 'default' as NotificationPermission }),
    )

    expect(await publishWrongWayAlert({ title: 'Off trail', body: '…' })).toBe(false)
    expect(spy).not.toHaveBeenCalled()
  })

  it('sends nothing when the platform has no Notification API at all', async () => {
    vi.stubGlobal('Notification', undefined)

    expect(await publishWrongWayAlert({ title: 'Off trail', body: '…' })).toBe(false)
  })

  it('sends the alert once permission is granted', async () => {
    const spy = vi.fn()
    vi.stubGlobal(
      'Notification',
      Object.assign(spy, { permission: 'granted' as NotificationPermission }),
    )

    expect(await publishWrongWayAlert({ title: 'Off trail', body: 'Turn around' })).toBe(
      true,
    )
    expect(spy).toHaveBeenCalledWith('Off trail', { body: 'Turn around' })
  })

  it('delivers through the service worker, the only path a phone supports', async () => {
    // The bug: this called `new Notification(...)` directly. Android Chrome
    // refuses that outright - "Illegal constructor. Use
    // ServiceWorkerRegistration.showNotification() instead" - and an
    // installed iOS PWA, the only place iOS delivers web push at all, has no
    // usable constructor either. The one notification OurHike is allowed to
    // send was the one that could not arrive on a phone.
    const constructor = vi.fn()
    vi.stubGlobal(
      'Notification',
      Object.assign(constructor, { permission: 'granted' as NotificationPermission }),
    )
    const showNotification = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', {
      serviceWorker: { getRegistration: vi.fn().mockResolvedValue({ showNotification }) },
    })

    expect(await publishWrongWayAlert({ title: 'Off trail', body: 'Turn around' })).toBe(
      true,
    )
    expect(showNotification).toHaveBeenCalledWith('Off trail', { body: 'Turn around' })
    expect(constructor).not.toHaveBeenCalled()
  })

  it('falls back to the constructor where nothing is registered', async () => {
    // A desktop browser during development, which is where this gets looked
    // at - and the reason the constructor path is kept rather than removed.
    const constructor = vi.fn()
    vi.stubGlobal(
      'Notification',
      Object.assign(constructor, { permission: 'granted' as NotificationPermission }),
    )
    vi.stubGlobal('navigator', {
      serviceWorker: { getRegistration: vi.fn().mockResolvedValue(undefined) },
    })

    expect(await publishWrongWayAlert({ title: 'Off trail', body: 'Turn around' })).toBe(
      true,
    )
    expect(constructor).toHaveBeenCalledWith('Off trail', { body: 'Turn around' })
  })

  it('reports failure rather than throwing when no path works at all', async () => {
    // wrongWayAlert.ts reads a false as "the in-app cue is all we have". An
    // exception here would take the cue down with the push, which is the one
    // outcome worse than a missed notification.
    vi.stubGlobal(
      'Notification',
      Object.assign(
        vi.fn(() => {
          throw new TypeError('Illegal constructor')
        }),
        { permission: 'granted' as NotificationPermission },
      ),
    )
    vi.stubGlobal('navigator', {
      serviceWorker: { getRegistration: vi.fn().mockRejectedValue(new Error('no sw')) },
    })

    expect(await publishWrongWayAlert({ title: 'Off trail', body: '…' })).toBe(false)
  })

  it('never asks for permission itself - that belongs to the hike-start flow', async () => {
    // HIKER_SAFETY.md puts the prompt at hike start, where the reason is
    // concrete. Asking here would mean prompting at the exact moment someone
    // is already lost.
    const push = readFileSync(join(SRC, 'lib', 'push.ts'), 'utf8')

    expect(push).not.toContain('requestPermission')
  })
})
