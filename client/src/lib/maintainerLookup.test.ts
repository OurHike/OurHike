import { describe, it, expect, vi, afterEach } from 'vitest'
import { lookupMaintainers, describeStewards } from './maintainerLookup'

// Client side of features/SAYING_THANKS.md's "who do I thank?" resolution.
//
// This is a NICETY, not a dependency. The authoritative resolution happens
// server-side when the thanks is finally received, using its location and
// authored date - which is the only way it can work, because the normal case
// is writing a thanks with no signal at all. All this does is let the form
// say "this stretch is looked after by the Mountain Club" when the phone
// happens to be online.
//
// So it must fail silently. A lookup that throws, or blocks, or shows an
// error would turn a network problem into an obstacle between someone and
// saying thank you.

const ASSIGNMENT = {
  id: 'a1',
  maintainer_id: 'm1',
  club_id: 'c1',
  club_name: 'Mountain Club',
  display_name: null as string | null,
  start_mile: 1040,
  end_mile: 1050,
  effective_from: '2026-01-01',
  effective_to: null as string | null,
}

function mockFetch(payload: unknown, ok = true) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok,
    json: async () => payload,
  } as Response)
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('lookupMaintainers', () => {
  it('asks about the mile it was given', async () => {
    const spy = mockFetch([ASSIGNMENT])

    await lookupMaintainers(1043.2, new Date('2026-06-15T12:00:00Z'))

    expect(String(spy.mock.calls[0][0])).toContain('mile=1043.2')
  })

  it('resolves as-of the AUTHORED date, not today', async () => {
    // The case the whole versioned model exists for. A thanks written in
    // June about a section reassigned in July belongs to June's maintainer,
    // even if it only syncs in August.
    const spy = mockFetch([ASSIGNMENT])

    await lookupMaintainers(1043.2, new Date('2026-06-15T12:00:00Z'))

    expect(String(spy.mock.calls[0][0])).toContain('as_of=2026-06-15')
  })

  it('returns what the server found', async () => {
    mockFetch([ASSIGNMENT])

    expect(await lookupMaintainers(1043.2, new Date())).toHaveLength(1)
  })

  it('returns an empty list rather than throwing when offline', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(lookupMaintainers(1043.2, new Date())).resolves.toEqual([])
  })

  it('returns an empty list rather than throwing when the server errors', async () => {
    mockFetch(null, false)

    await expect(lookupMaintainers(1043.2, new Date())).resolves.toEqual([])
  })

  it('treats an unassigned stretch as a normal empty answer', async () => {
    mockFetch([])

    expect(await lookupMaintainers(500, new Date())).toEqual([])
  })
})

describe('describeStewards', () => {
  it('names the club when the maintainer has not opted in to being credited', () => {
    expect(describeStewards([ASSIGNMENT])).toBe('Looked after by Mountain Club')
  })

  it('names the maintainer when they have opted in', () => {
    expect(describeStewards([{ ...ASSIGNMENT, display_name: 'Pat' }])).toBe(
      'Looked after by Pat (Mountain Club)',
    )
  })

  it('names both when a stretch is shared', () => {
    const shared = [ASSIGNMENT, { ...ASSIGNMENT, id: 'a2', club_name: 'River Club' }]

    expect(describeStewards(shared)).toBe('Looked after by Mountain Club and River Club')
  })

  it('says nothing at all when nobody is assigned, rather than "unknown"', () => {
    // A thanks with no resolved steward is still a complete thanks. Printing
    // "Maintainer: unknown" would make it feel incomplete when it is not.
    expect(describeStewards([])).toBeNull()
  })

  it('does not repeat a club that appears twice', () => {
    const two = [ASSIGNMENT, { ...ASSIGNMENT, id: 'a2', maintainer_id: 'm2' }]

    expect(describeStewards(two)).toBe('Looked after by Mountain Club')
  })
})
