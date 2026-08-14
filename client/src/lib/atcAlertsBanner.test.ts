import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  ATC_ALERT_SILENCE_KEY,
  NEW_ATC_ALERT_WINDOW_MS,
  atcAlertsSince,
  readAtcAlertSilence,
  writeAtcAlertSilence,
} from './atcAlertsBanner'
import type { AtcUpdate } from './atcUpdates'

// #687. The gate is "did ATC touch this in the last 72 hours", and the
// silence is a watermark rather than a per-notice read receipt - see the
// module docstring for why a set of ids would not survive ATC editing a
// notice it already covers.

const NOW = new Date('2026-08-13T12:00:00.000Z')

function hoursBefore(date: Date, hours: number): string {
  return new Date(date.getTime() - hours * 60 * 60 * 1000).toISOString()
}

function update(overrides: Partial<AtcUpdate> = {}): AtcUpdate {
  return {
    atc_id: 'harpers-ferry-footbridge-closure',
    title: 'Harpers Ferry: Footbridge Closure',
    category: 'Detour',
    states: ['MD', 'WV'],
    start_mile_marker: 1026.7,
    end_mile_marker: 1026.7,
    obstructs_trail: true,
    updated_at: hoursBefore(NOW, 1),
    source_url: 'https://appalachiantrail.org/trail-updates/harpers-ferry/',
    ...overrides,
  }
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('atcAlertsSince', () => {
  it('says nothing when the app holds no updates', () => {
    expect(atcAlertsSince([], NOW, null)).toBeNull()
  })

  it('counts an update edited moments ago', () => {
    const result = atcAlertsSince(
      [update({ updated_at: hoursBefore(NOW, 1) })],
      NOW,
      null,
    )

    expect(result).toEqual({ count: 1, newestAt: new Date(hoursBefore(NOW, 1)) })
  })

  it('is inclusive at exactly the 72-hour boundary', () => {
    const at = new Date(NOW.getTime() - NEW_ATC_ALERT_WINDOW_MS)

    expect(atcAlertsSince([update({ updated_at: at.toISOString() })], NOW, null)).toEqual(
      {
        count: 1,
        newestAt: at,
      },
    )
  })

  it('drops an update one millisecond past the boundary', () => {
    const at = new Date(NOW.getTime() - NEW_ATC_ALERT_WINDOW_MS - 1)

    expect(
      atcAlertsSince([update({ updated_at: at.toISOString() })], NOW, null),
    ).toBeNull()
  })

  it('ignores an update ATC touched weeks ago', () => {
    const stale = update({ updated_at: hoursBefore(NOW, 24 * 21) })

    expect(atcAlertsSince([stale], NOW, null)).toBeNull()
  })

  it('does not count a date this build cannot parse', () => {
    const unparseable = update({ updated_at: 'not a date' })

    expect(atcAlertsSince([unparseable], NOW, null)).toBeNull()
  })

  it('holds off on an update dated after now, rather than counting it forever', () => {
    // Not a case ATC's reviewed pipeline produces - a defence against clock
    // skew, not a real update. `now` catching up is covered by the boundary
    // tests above: the same update becomes ordinary once it is not in the
    // future.
    const future = update({ updated_at: hoursBefore(NOW, -1) })

    expect(atcAlertsSince([future], NOW, null)).toBeNull()
  })

  it('counts several recent updates and reports the newest edit among them', () => {
    const updates = [
      update({ atc_id: 'a', updated_at: hoursBefore(NOW, 50) }),
      update({ atc_id: 'b', updated_at: hoursBefore(NOW, 2) }),
      update({ atc_id: 'c', updated_at: hoursBefore(NOW, 30) }),
    ]

    expect(atcAlertsSince(updates, NOW, null)).toEqual({
      count: 3,
      newestAt: new Date(hoursBefore(NOW, 2)),
    })
  })

  it('leaves an old notice out of the count even while a recent one is new', () => {
    const updates = [
      update({ atc_id: 'recent', updated_at: hoursBefore(NOW, 2) }),
      update({ atc_id: 'old', updated_at: hoursBefore(NOW, 24 * 30) }),
    ]

    expect(atcAlertsSince(updates, NOW, null)?.count).toBe(1)
  })

  it('silences an edit at or before the watermark', () => {
    const at = new Date(hoursBefore(NOW, 2))

    expect(atcAlertsSince([update({ updated_at: at.toISOString() })], NOW, at)).toBeNull()
  })

  it('leaves an edit after the watermark alone', () => {
    const silencedThrough = new Date(hoursBefore(NOW, 5))
    const newer = update({ updated_at: hoursBefore(NOW, 1) })

    expect(atcAlertsSince([newer], NOW, silencedThrough)).toEqual({
      count: 1,
      newestAt: new Date(hoursBefore(NOW, 1)),
    })
  })

  it('reports only what is newer than the watermark when both exist', () => {
    const silencedThrough = new Date(hoursBefore(NOW, 10))
    const updates = [
      update({ atc_id: 'already-seen', updated_at: hoursBefore(NOW, 20) }),
      update({ atc_id: 'genuinely-new', updated_at: hoursBefore(NOW, 1) }),
    ]

    expect(atcAlertsSince(updates, NOW, silencedThrough)).toEqual({
      count: 1,
      newestAt: new Date(hoursBefore(NOW, 1)),
    })
  })
})

describe('the silence watermark', () => {
  it('is null before anyone has silenced anything', () => {
    expect(readAtcAlertSilence()).toBeNull()
  })

  it('round-trips through localStorage', () => {
    const at = new Date('2026-08-12T08:00:00.000Z')
    writeAtcAlertSilence(at)

    expect(readAtcAlertSilence()).toEqual(at)
    expect(localStorage.getItem(ATC_ALERT_SILENCE_KEY)).toBe(at.toISOString())
  })

  it('treats an unreadable marker as unsilenced rather than throwing', () => {
    localStorage.setItem(ATC_ALERT_SILENCE_KEY, 'not a date')

    expect(readAtcAlertSilence()).toBeNull()
  })

  it('survives storage that throws on access, rather than taking the app down', () => {
    // Private browsing and hardened embedders throw when `localStorage` is
    // READ, before any get or set (lib/cameraMemory.ts guards the same way
    // for sessionStorage).
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new Error('The operation is insecure.')
    })

    expect(() => writeAtcAlertSilence(new Date())).not.toThrow()
    expect(readAtcAlertSilence()).toBeNull()
  })
})
