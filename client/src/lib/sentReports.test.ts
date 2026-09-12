// The ledger of reports this phone sent (#1373, frame 9d).

import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { OutboxItem } from './outbox'
import {
  SENT_REPORTS_KEY,
  SENT_REPORTS_MAX,
  listSentReports,
  recordSentReport,
} from './sentReports'

const store = new Map<string, unknown>()
vi.mock('idb-keyval', () => ({
  get: vi.fn(async (key: string) => store.get(key)),
  set: vi.fn(async (key: string, value: unknown) => {
    store.set(key, value)
  }),
}))

function report(id: string, over: Partial<OutboxItem> = {}): OutboxItem {
  return {
    id,
    authoredAt: '2026-09-08T10:00:00.000Z',
    payload: { type: 'blowdown', reporter_type: 'thru', poi_id: 'poi-1', mile: 1347.2 },
    ...over,
  }
}

beforeEach(() => {
  store.clear()
  vi.clearAllMocks()
})

describe('what the phone remembers of a sent report', () => {
  it('keeps the id, the type, the place, and both dates - never the note', async () => {
    await recordSentReport(
      report('r1', { payload: { type: 'trash', reporter_type: 'day', note: 'Bags.' } }),
      '2026-09-09T12:00:00.000Z',
    )

    expect(await listSentReports()).toEqual([
      {
        id: 'r1',
        type: 'trash',
        poiId: null,
        mile: null,
        authoredAt: '2026-09-08T10:00:00.000Z',
        sentAt: '2026-09-09T12:00:00.000Z',
      },
    ])
    expect(JSON.stringify(store.get(SENT_REPORTS_KEY))).not.toContain('Bags')
  })

  it('records nothing for the cargoes that are not condition reports', async () => {
    await recordSentReport({
      id: 'n1',
      authoredAt: '2026-09-08T10:00:00.000Z',
      fieldNote: { reporter_type: 'thru', observation: 'flowing' },
    })
    await recordSentReport({
      id: 'f1',
      authoredAt: '2026-09-08T10:00:00.000Z',
      appFailure: {
        what_happened: 'It went blank.',
        where_when: '',
        contact: '',
        harms: [],
        was_offline: true,
      } as unknown as OutboxItem['appFailure'],
    })

    expect(await listSentReports()).toEqual([])
  })

  it('is idempotent on the id - a resend is the same report (#243)', async () => {
    await recordSentReport(report('r1'), '2026-09-09T12:00:00.000Z')
    await recordSentReport(report('r1'), '2026-09-10T12:00:00.000Z')

    const sent = await listSentReports()
    expect(sent).toHaveLength(1)
    expect(sent[0].sentAt).toBe('2026-09-09T12:00:00.000Z')
  })

  it('lists newest first and keeps the cap', async () => {
    for (let index = 0; index < SENT_REPORTS_MAX + 5; index += 1) {
      await recordSentReport(
        report(`r${index}`),
        `2026-09-09T12:00:${String(index % 60).padStart(2, '0')}.000Z`,
      )
    }

    const sent = await listSentReports()
    expect(sent).toHaveLength(SENT_REPORTS_MAX)
    expect(sent[0].id).toBe(`r${SENT_REPORTS_MAX + 4}`)
    expect(sent.some((entry) => entry.id === 'r0')).toBe(false)
  })

  it('drops one unreadable entry rather than the ledger', async () => {
    store.set(SENT_REPORTS_KEY, [
      { id: 'ok', type: 'blowdown', authoredAt: 'a', sentAt: 'b' },
      { id: '', type: 'blowdown', authoredAt: 'a', sentAt: 'b' },
      'junk',
      null,
    ])

    expect((await listSentReports()).map((entry) => entry.id)).toEqual(['ok'])
    store.set(SENT_REPORTS_KEY, 'junk')
    expect(await listSentReports()).toEqual([])
  })
})
