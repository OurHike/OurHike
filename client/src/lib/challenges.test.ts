import { describe, expect, it } from 'vitest'
import {
  draftLabel,
  isOpen,
  isSealed,
  itemTitle,
  itemsAtPoi,
  unseal,
  windowLine,
} from './challenges'
import { parseChallenges } from './challengeFeed'

// The artifact's own shape, as pipeline/export_challenges.py writes it.
function place(poi: string, mile: number, name = poi) {
  return { poi, name, poi_type: 'viewpoint', mile, lat: 37.39, lon: -80.03 }
}

function challenge(overrides: Record<string, unknown> = {}) {
  return {
    id: 'atc-summer-bucket-list-2027',
    org: 'atc',
    org_name: 'Appalachian Trail Conservancy',
    org_short: 'ATC',
    trail: 'AT',
    name: 'A.T. Summer Bucket List',
    status: 'draft',
    window: { opens: '2027-05-15', closes: '2027-09-01' },
    finish: { count: 2, label: 'for the drawing' },
    reward: { kind: 'drawing', rules_url: 'https://appalachiantrail.org/sweepstakes' },
    sections: [
      { id: 'experience', title: 'Experience the A.T.', short: 'Anywhere' },
      { id: 'mystery', title: 'Mystery Items', short: 'Mystery' },
    ],
    items: [
      {
        id: 'mcafee-knob',
        section: 'experience',
        title: 'See it from the Knob',
        match: {
          kind: 'place',
          radius_m: 150,
          off_trail: false,
          places: [place('atc_viewpoints:mcafee', 714.92)],
        },
      },
      {
        id: 'summit-4000',
        section: 'experience',
        title: 'Summit a 4,000+ foot peak',
        match: { kind: 'elevation_min_ft', value: 4000 },
      },
      {
        id: 'trivia',
        section: 'experience',
        title: 'Take our A.T. trivia quiz.',
        match: { kind: 'self_report' },
      },
    ],
    reviewed: '2026-09-30',
    ...overrides,
  }
}

describe('parseChallenges reads the exporter artifact', () => {
  it('reads a challenge with its org names, window, finish and reward', () => {
    const [parsed] = parseChallenges({ challenges: [challenge()] })
    expect(parsed.orgShort).toBe('ATC')
    expect(parsed.window).toEqual({ opens: '2027-05-15', closes: '2027-09-01' })
    expect(parsed.finish).toEqual({ count: 2, label: 'for the drawing' })
    expect(parsed.reward?.kind).toBe('drawing')
    expect(parsed.items.map((item) => item.match.kind)).toEqual([
      'place',
      'elevation_min_ft',
      'self_report',
    ])
  })

  it('drops one unreadable challenge and keeps the rest', () => {
    const list = parseChallenges({ challenges: [{ id: 'broken' }, challenge()] })
    expect(list.map((entry) => entry.id)).toEqual(['atc-summer-bucket-list-2027'])
  })

  it('drops an item whose place has no mile rather than guessing one', () => {
    const raw = challenge({
      finish: null,
      items: [
        ...challenge().items,
        {
          id: 'nowhere',
          section: 'experience',
          title: 'A place with no mile',
          match: {
            kind: 'place',
            radius_m: 150,
            places: [{ poi: 'x', name: 'x', lat: 1, lon: 1 }],
          },
        },
      ],
    })
    expect(
      parseChallenges({ challenges: [raw] })[0].items.map((item) => item.id),
    ).not.toContain('nowhere')
  })

  it('drops a challenge whose finish line is past the items it has', () => {
    // The exporter's promise-nobody-can-keep refusal, held on the phone too.
    expect(
      parseChallenges({ challenges: [challenge({ finish: { count: 9 } })] }),
    ).toEqual([])
  })

  it('reads a record with no finish and no reward', () => {
    const [parsed] = parseChallenges({
      challenges: [challenge({ finish: null, reward: null })],
    })
    expect(parsed.finish).toBeNull()
    expect(parsed.reward).toBeNull()
  })

  it('refuses a reward that has no finish line to be claimed at', () => {
    const [parsed] = parseChallenges({ challenges: [challenge({ finish: null })] })
    expect(parsed.reward).toBeNull()
  })

  it('never throws on junk', () => {
    expect(parseChallenges(null)).toEqual([])
    expect(parseChallenges('nope')).toEqual([])
    expect(parseChallenges({ challenges: 'nope' })).toEqual([])
  })
})

describe('a sealed mystery item', () => {
  const sealed = parseChallenges({
    challenges: [
      challenge({
        finish: null,
        items: [
          ...challenge().items,
          {
            id: 'mystery-2',
            section: 'mystery',
            title: null,
            sealed_title: btoa('Find Jefferson Rock'),
            mystery: { number: 2, reveal_on: '2027-07-20' },
            match: { kind: 'self_report' },
          },
          {
            id: 'mystery-3',
            section: 'mystery',
            title: null,
            mystery: { number: 3, reveal_on: null },
            match: { kind: 'self_report' },
          },
        ],
      }),
    ],
  })[0]
  const dated = sealed.items.find((item) => item.id === 'mystery-2')!
  const undated = sealed.items.find((item) => item.id === 'mystery-3')!

  it('has no title before its reveal date', () => {
    expect(itemTitle(dated, '2027-07-19')).toBeNull()
    expect(isSealed(dated, '2027-07-19')).toBe(true)
  })

  it('reveals its title on the phone on the reveal date, with no network', () => {
    expect(itemTitle(dated, '2027-07-20')).toBe('Find Jefferson Rock')
    expect(isSealed(dated, '2027-07-20')).toBe(false)
  })

  it('stays sealed when its club never gave it a title or a date', () => {
    expect(itemTitle(undated, '2099-01-01')).toBeNull()
    expect(isSealed(undated, '2099-01-01')).toBe(true)
  })

  it('decodes UTF-8 and refuses bytes that are not base64', () => {
    expect(
      unseal(btoa(String.fromCharCode(...new TextEncoder().encode('Dragon’s Tooth')))),
    ).toBe('Dragon’s Tooth')
    expect(unseal('%%%')).toBeNull()
  })
})

describe('what screens ask of a challenge', () => {
  const [parsed] = parseChallenges({ challenges: [challenge()] })

  it('labels a draft in the words every surface uses', () => {
    expect(draftLabel(parsed)).toBe('Draft · not yet confirmed by the ATC')
    expect(draftLabel({ ...parsed, status: 'published' })).toBeNull()
  })

  it('is open inside its window and closed on either side of it', () => {
    expect(isOpen(parsed, '2027-05-14')).toBe(false)
    expect(isOpen(parsed, '2027-05-15')).toBe(true)
    expect(isOpen(parsed, '2027-09-01')).toBe(true)
    expect(isOpen(parsed, '2027-09-02')).toBe(false)
  })

  it('prints the window as dates, never as days left', () => {
    expect(windowLine(parsed)).toBe('May 15 – Sep 1')
    expect(windowLine({ ...parsed, window: { opens: null, closes: '2027-09-01' } })).toBe(
      'until Sep 1',
    )
    expect(windowLine({ ...parsed, window: { opens: null, closes: null } })).toBe(
      'no end date',
    )
  })

  it('finds the items that name a published POI', () => {
    expect(itemsAtPoi(parsed, 'atc_viewpoints:mcafee').map((item) => item.id)).toEqual([
      'mcafee-knob',
    ])
    expect(itemsAtPoi(parsed, 'atc_viewpoints:elsewhere')).toEqual([])
  })
})

describe('what the review of 2026-09-30 tightened', () => {
  it('reads the publisher’s domain and whether the club takes entries here', () => {
    const [published] = parseChallenges({
      challenges: [
        challenge({
          status: 'published',
          org_domain: 'appalachiantrail.org',
          takes_entries: true,
        }),
      ],
    })
    expect(published.orgDomain).toBe('appalachiantrail.org')
    expect(published.takesEntries).toBe(true)
    // A draft never does, whatever its file says.
    const [draft] = parseChallenges({ challenges: [challenge({ takes_entries: true })] })
    expect(draft.takesEntries).toBe(false)
    expect(draft.orgDomain).toBeNull()
  })

  it('keeps only https photos, the line the pipeline holds', () => {
    const [read] = parseChallenges({
      challenges: [
        challenge({
          photo: 'http://club.example/p.jpg',
          items: [
            {
              id: 'trivia',
              section: 'experience',
              title: 'Take our A.T. trivia quiz.',
              photo: 'javascript:alert(1)',
              match: { kind: 'self_report' },
            },
          ],
          finish: null,
          reward: null,
        }),
      ],
    })
    expect(read.photo).toBeNull()
    expect(read.items[0].photo).toBeNull()
  })

  it('reads an off-trail "any waypoint" item as off the trail', () => {
    const [read] = parseChallenges({
      challenges: [
        challenge({
          finish: null,
          reward: null,
          items: [
            {
              id: 'meal-in-a-community',
              section: 'experience',
              title: 'Have a meal in an A.T. Community.',
              match: {
                kind: 'poi_type',
                type: 'resupply',
                radius_m: 800,
                off_trail: true,
              },
            },
          ],
        }),
      ],
    })
    expect(read.items[0].match).toMatchObject({ kind: 'poi_type', offTrail: true })
  })
})
