/**
 * A notice from an organization, whichever organization that is (#1083).
 *
 * The failures worth guarding here are not crashes. Every one of them is the
 * app quietly telling a hiker something no organization said:
 *
 * - NYNJTC's closure rendered in the ATC's voice, because a component held a
 *   literal string.
 * - A hiker dismissing one organization's banner and never being shown
 *   another's, because one watermark stood for two publishers.
 * - A notice nobody can place sorted as if it had a mile, which is an
 *   arbitrary order wearing the authority of "distance along the trail".
 */

import { describe, expect, it, beforeEach } from 'vitest'
import {
  ATC_SOURCE_KEY,
  LEGACY_ATC_SILENCE_KEY,
  atcUpdateAsNotice,
  newNoticesSince,
  noticeBandId,
  noticeOrgLabel,
  noticeSilenceKey,
  orderedNotices,
  scopedNotices,
  readNoticeSilence,
  silenceNewNotices,
  writeNoticeSilence,
  type TrailNotice,
} from './notices'
import type { AtcUpdate } from './atcUpdates'
import type { Stewards } from './stewards'

function atcUpdate(fields: Partial<AtcUpdate> = {}): AtcUpdate {
  return {
    atc_id: 'central-va-war-spur-bridge-closed',
    title: 'Central VA: War Spur Bridge Closed',
    category: 'Closure',
    states: ['VA'],
    start_mile_marker: 670.2,
    end_mile_marker: 670.2,
    obstructs_trail: false,
    updated_at: '2026-08-19T20:22:50Z',
    source_url:
      'https://appalachiantrail.org/trail-updates/central-va-war-spur-bridge-closed/',
    review_state: 'reviewed',
    ...fields,
  }
}

/** Shaped on a real published row - conditions/nynjtc_alerts.json, read
 *  2026-08-27. Every field is theirs, including the null category. */
function orgNotice(fields: Partial<TrailNotice> = {}): TrailNotice {
  return {
    notice_id: 'nynjtc_trail_alerts:a-t-detour-at-harriman-state-park',
    source_key: 'nynjtc_trail_alerts',
    title: 'A.T. Detour at Harriman State Park',
    category: null,
    locality: 'Harriman-Bear Mountain',
    place: { kind: 'unplaced' },
    obstructs_trail: false,
    updated_at: '2026-06-16T14:37:46Z',
    source_url: 'https://www.nynjtc.org/trail-alerts/a-t-detour-at-harriman-state-park/',
    review_state: 'unreviewed',
    ...fields,
  }
}

describe('adapting the ATC row', () => {
  it('gives it the source key that resolves to an organization', () => {
    // The whole of #1083 item 3 in one assertion: with a registry key on the
    // row, no component has to know who published it.
    expect(atcUpdateAsNotice(atcUpdate()).source_key).toBe(ATC_SOURCE_KEY)
  })

  it('namespaces the id the way the pipeline already namespaces NYNJTC-s', () => {
    // Not `atc:` - the abbreviation nothing could resolve. The pipeline
    // settled on `<source key>:<slug>` and this is that scheme.
    expect(noticeBandId(atcUpdateAsNotice(atcUpdate()))).toBe(
      'atc_trail_updates:central-va-war-spur-bridge-closed',
    )
  })

  it('carries the miles into the place union rather than dropping them', () => {
    expect(atcUpdateAsNotice(atcUpdate()).place).toEqual({
      kind: 'at_miles',
      start: 670.2,
      end: 670.2,
    })
  })

  it('reads a row with no review state as reviewed, not as unknown', () => {
    // Artifacts baked before #963 carry no such field, and every row in one of
    // those was reviewed by definition. Matches isReviewedByAPerson.
    const legacy = atcUpdate()
    delete (legacy as Partial<AtcUpdate>).review_state

    expect(atcUpdateAsNotice(legacy).review_state).toBe('reviewed')
  })

  it('turns states into a locality, because that is the field both orgs have', () => {
    expect(atcUpdateAsNotice(atcUpdate({ states: ['NC', 'TN'] })).locality).toBe('NC, TN')
  })
})

describe('ordering a list that holds two organizations', () => {
  it('puts the most recently edited notice first, whoever published it', () => {
    // A maintainer's call (2026-08-27), replacing mile order. The argument it
    // overrules is in the module comment: mile order can only rank the rows
    // that HAVE a mile, and eighteen of the twenty-one do not.
    const old = orgNotice({ notice_id: 'old', updated_at: '2025-06-24T00:00:00Z' })
    const mid = atcUpdateAsNotice(
      atcUpdate({ atc_id: 'mid', updated_at: '2026-01-01T00:00:00Z' }),
    )
    const fresh = orgNotice({ notice_id: 'fresh', updated_at: '2026-06-16T14:37:46Z' })

    expect(orderedNotices([old, fresh, mid]).map((n) => n.notice_id)).toEqual([
      'fresh',
      'atc_trail_updates:mid',
      'old',
    ])
  })

  it('sorts a notice whose date it cannot read to the bottom, not to the top', () => {
    // The conservative direction: an unreadable stamp must not claim to be the
    // newest thing an organization has posted.
    const unreadable = orgNotice({ notice_id: 'bad', updated_at: 'not a date' })
    const good = orgNotice({ notice_id: 'good', updated_at: '2025-01-01T00:00:00Z' })

    expect(orderedNotices([unreadable, good]).map((n) => n.notice_id)).toEqual([
      'good',
      'bad',
    ])
  })
})

describe('scoping the list to where the hiker is looking', () => {
  const NOW = new Date('2026-08-27T12:00:00Z')
  const NOTHING_DRAWN = new Set<string>()
  const OLD = '2026-01-01T00:00:00Z'

  const near = atcUpdateAsNotice(
    atcUpdate({
      atc_id: 'near',
      start_mile_marker: 1500,
      end_mile_marker: 1500,
      updated_at: OLD,
    }),
  )
  const far = atcUpdateAsNotice(
    atcUpdate({
      atc_id: 'far',
      start_mile_marker: 200,
      end_mile_marker: 200,
      updated_at: OLD,
    }),
  )

  it('keeps the notices on the stretch on screen and counts the rest', () => {
    const scoped = scopedNotices(
      [near, far],
      { startMile: 1450, endMile: 1550 },
      NOTHING_DRAWN,
      NOW,
    )

    expect(scoped.shown.map((n) => n.notice_id)).toEqual(['atc_trail_updates:near'])
    expect(scoped.hidden).toBe(1)
  })

  it('counts a notice that straddles the edge as on screen', () => {
    const spanning = atcUpdateAsNotice(
      atcUpdate({
        atc_id: 'helene',
        start_mile_marker: 239.4,
        end_mile_marker: 637.8,
        updated_at: OLD,
      }),
    )

    const scoped = scopedNotices(
      [spanning],
      { startMile: 600, endMile: 700 },
      NOTHING_DRAWN,
      NOW,
    )

    expect(scoped.shown).toHaveLength(1)
    expect(scoped.hidden).toBe(0)
  })

  it('never scopes out a notice that has no mile at all', () => {
    // Filtering something on a criterion it cannot answer does not exclude it
    // fairly, it excludes it always - and a notice that reaches no screen is
    // the exact failure #1083 exists to undo.
    const scoped = scopedNotices(
      [orgNotice({ updated_at: OLD })],
      { startMile: 0, endMile: 1 },
      NOTHING_DRAWN,
      NOW,
    )

    expect(scoped.shown).toHaveLength(1)
    expect(scoped.hidden).toBe(0)
  })

  it('never scopes out a notice the map is currently drawing', () => {
    // If a hiker can see the mark, the list has to be able to explain it.
    const scoped = scopedNotices(
      [far],
      { startMile: 1450, endMile: 1550 },
      new Set([noticeBandId(far)]),
      NOW,
    )

    expect(scoped.shown).toHaveLength(1)
    expect(scoped.hidden).toBe(0)
  })

  it('never scopes out something posted today', () => {
    const today = atcUpdateAsNotice(
      atcUpdate({
        atc_id: 'today',
        start_mile_marker: 200,
        end_mile_marker: 200,
        updated_at: '2026-08-27T06:00:00Z',
      }),
    )

    const scoped = scopedNotices(
      [today],
      { startMile: 1450, endMile: 1550 },
      NOTHING_DRAWN,
      NOW,
    )

    expect(scoped.shown).toHaveLength(1)
    expect(scoped.hidden).toBe(0)
  })

  it('scopes nothing when there is no extent to scope to', () => {
    // No centerline loaded, or a viewport holding no trail. Showing everything
    // is what this screen did before the rule existed.
    const scoped = scopedNotices([near, far], null, NOTHING_DRAWN, NOW)

    expect(scoped.shown).toHaveLength(2)
    expect(scoped.hidden).toBe(0)
  })

  it('returns them newest first, scoped or not', () => {
    const scoped = scopedNotices([far, near], null, NOTHING_DRAWN, NOW)

    expect(scoped.shown.map((n) => n.updated_at)).toEqual([OLD, OLD])
    expect(scoped.shown).toHaveLength(2)
  })
})

describe('naming the organization', () => {
  const stewards: Stewards = [
    {
      provider: 'NYNJTC',
      name: 'New York-New Jersey Trail Conference',
      trust: 'authoritative',
      licence: null,
      attribution: 'New York-New Jersey Trail Conference',
      layers: ['NYNJTC Trail Alerts'],
      keys: ['nynjtc_trail_alerts'],
    },
  ]

  it('reads the name off the registry rather than out of a component', () => {
    expect(noticeOrgLabel(stewards)(orgNotice())).toBe(
      'New York-New Jersey Trail Conference',
    )
  })

  it('prints the raw key when no steward claims it, rather than guessing', () => {
    // Real when a phone holds a notice artifact and a stewards artifact from
    // different releases. `atc_trail_updates` is ugly and true; a prettified
    // guess would say something nobody stands behind.
    expect(noticeOrgLabel(stewards)(atcUpdateAsNotice(atcUpdate()))).toBe(
      'atc_trail_updates',
    )
  })
})

describe('the silence watermark, per organization', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('does not silence one organization when a hiker dismisses another', () => {
    // THE LIVE BUG. One shared key meant dismissing the ATC silenced NYNJTC
    // too, for notices the hiker had never been shown.
    writeNoticeSilence(ATC_SOURCE_KEY, new Date('2026-08-27T00:00:00Z'))

    expect(readNoticeSilence(ATC_SOURCE_KEY)).not.toBeNull()
    expect(readNoticeSilence('nynjtc_trail_alerts')).toBeNull()
  })

  it('keeps a dismissal a hiker already made before the upgrade', () => {
    // The banner crying wolf on its first run after an update is exactly how a
    // warning surface teaches people to ignore it.
    window.localStorage.setItem(LEGACY_ATC_SILENCE_KEY, '2026-08-26T00:00:00Z')

    expect(readNoticeSilence(ATC_SOURCE_KEY)?.toISOString()).toBe(
      '2026-08-26T00:00:00.000Z',
    )
  })

  it('does not lend the old ATC watermark to any other organization', () => {
    window.localStorage.setItem(LEGACY_ATC_SILENCE_KEY, '2026-08-26T00:00:00Z')

    expect(readNoticeSilence('nynjtc_trail_alerts')).toBeNull()
  })

  it('prefers the org-s own watermark over the legacy one once it exists', () => {
    window.localStorage.setItem(LEGACY_ATC_SILENCE_KEY, '2020-01-01T00:00:00Z')
    writeNoticeSilence(ATC_SOURCE_KEY, new Date('2026-08-27T00:00:00Z'))

    expect(readNoticeSilence(ATC_SOURCE_KEY)?.toISOString()).toBe(
      '2026-08-27T00:00:00.000Z',
    )
  })

  it('treats an unreadable marker as nothing silenced', () => {
    window.localStorage.setItem(noticeSilenceKey(ATC_SOURCE_KEY), 'whenever')

    expect(readNoticeSilence(ATC_SOURCE_KEY)).toBeNull()
  })
})

describe('what the banner counts', () => {
  const now = new Date('2026-08-27T12:00:00Z')
  const nothingSilenced = () => null

  beforeEach(() => {
    window.localStorage.clear()
  })

  it('counts across organizations and names each of them once', () => {
    const fresh = { updated_at: '2026-08-26T00:00:00Z' }
    const result = newNoticesSince(
      [
        atcUpdateAsNotice(atcUpdate({ atc_id: 'one', ...fresh })),
        atcUpdateAsNotice(atcUpdate({ atc_id: 'two', ...fresh })),
        orgNotice({ notice_id: 'three', ...fresh }),
      ],
      now,
      nothingSilenced,
    )

    expect(result?.count).toBe(3)
    expect(result?.sourceKeys).toEqual([ATC_SOURCE_KEY, 'nynjtc_trail_alerts'])
  })

  it('says nothing when nothing is new', () => {
    expect(newNoticesSince([orgNotice()], now, nothingSilenced)).toBeNull()
  })

  it('ignores an edit stamped after now rather than counting it forever', () => {
    // Clock skew, not a real case these organizations produce. It becomes new
    // once `now` actually reaches it.
    const ahead = orgNotice({ updated_at: '2026-08-28T00:00:00Z' })

    expect(newNoticesSince([ahead], now, nothingSilenced)).toBeNull()
  })

  it('drops one organization-s rows without dropping the other-s', () => {
    const fresh = { updated_at: '2026-08-26T00:00:00Z' }
    const result = newNoticesSince(
      [atcUpdateAsNotice(atcUpdate({ ...fresh })), orgNotice({ ...fresh })],
      now,
      (key) => (key === ATC_SOURCE_KEY ? new Date('2026-08-27T00:00:00Z') : null),
    )

    expect(result?.count).toBe(1)
    expect(result?.sourceKeys).toEqual(['nynjtc_trail_alerts'])
  })

  it('records one watermark per organization when a hiker dismisses the lot', () => {
    // One dismissal, N watermarks - what a hiker dismisses is what they were
    // shown, and they were shown a count that spans organizations.
    const result = newNoticesSince(
      [
        atcUpdateAsNotice(atcUpdate({ updated_at: '2026-08-26T00:00:00Z' })),
        orgNotice({ updated_at: '2026-08-25T00:00:00Z' }),
      ],
      now,
      nothingSilenced,
    )
    silenceNewNotices(result!)

    expect(readNoticeSilence(ATC_SOURCE_KEY)?.toISOString()).toBe(
      '2026-08-26T00:00:00.000Z',
    )
    expect(readNoticeSilence('nynjtc_trail_alerts')?.toISOString()).toBe(
      '2026-08-25T00:00:00.000Z',
    )
  })

  it('silences only up to the newest it counted, so a later edit returns', () => {
    const result = newNoticesSince(
      [orgNotice({ updated_at: '2026-08-25T00:00:00Z' })],
      now,
      nothingSilenced,
    )
    silenceNewNotices(result!)

    const later = newNoticesSince(
      [orgNotice({ notice_id: 'later', updated_at: '2026-08-26T00:00:00Z' })],
      now,
      readNoticeSilence,
    )

    expect(later?.count).toBe(1)
  })
})
