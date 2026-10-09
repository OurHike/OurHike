import { afterEach, describe, expect, it } from 'vitest'
import type { FeatureCollection } from 'geojson'
import {
  SAME_BUILD_MS,
  firstSeenRule,
  hazardView,
  newClubNotices,
} from './noticeSelection'
import {
  newNoticeLabel,
  newNoticesSince,
  readNoticeSilence,
  silenceNewNotices,
  type TrailNotice,
} from './notices'
import type { Stewards } from './stewards'
import { buildTrailIndex } from './trailPosition'

// What chrome/noticesPanel.tsx loads behind import() decides beyond the
// planned-hike rule (lib/plannedNotices.test.ts holds that one). Every row
// here is invented.

function row(
  notice_id: string,
  first_seen_at: string | null,
  extra: Partial<TrailNotice> = {},
): TrailNotice {
  return {
    notice_id,
    source_key: notice_id.split(':')[0],
    title: notice_id,
    category: null,
    locality: '',
    place: { kind: 'unplaced' },
    obstructs_trail: false,
    updated_at: null,
    source_url: null,
    review_state: 'unreviewed',
    first_seen_at,
    changed_at: first_seen_at,
    ...extra,
  }
}

describe('which file decision 67’s areas are drawn from (decision 84)', () => {
  const area = (id: string): TrailNotice =>
    row(`oprhp_hunting_areas:${id}`, null, {
      hazard: 'hunting',
      place: { kind: 'geometry', geometry: { type: 'Point', coordinates: [-77, 34.3] } },
    })
  const at = new Date('2026-10-05T00:00:00Z')

  /** A centerline due north along 77° W, through the invented area at 34.3° N. */
  const INDEX = buildTrailIndex({
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { source: 'centerline' },
        geometry: {
          type: 'LineString',
          coordinates: Array.from({ length: 101 }, (_, i) => [-77, 34 + i * 0.01]),
        },
      },
    ],
  } as FeatureCollection)

  it('draws nothing, and says so with null, with neither file on the phone', () => {
    expect(hazardView(null, null, null, INDEX, null)).toBeNull()
  })

  it('draws the area from notices.json alone, where it crosses a held trail', () => {
    expect(hazardView([area('1')], at, null, INDEX, null)?.areas).toHaveLength(1)
  })

  it('reads an arrived empty hazard file as no area, over an older notices.json', () => {
    const older = new Date(at.getTime() - 1)
    const view = hazardView(
      [area('1')],
      older,
      { items: [], generatedAt: at },
      INDEX,
      null,
    )
    expect(view?.areas).toEqual([])
  })
})

// Decision 87 (the maintainer, 2026-10-05): a notice with no `updated_at` of
// its own counts as new for the banner only if OurHike first saw it after
// its source's earliest row in the same file, worded "seen" rather than
// "issued"; a row edit (`changed_at`) never counts.
//
// The rows are shaped like soak run 536's file: every `first_seen_at` there
// fell between 2026-10-03T20:24Z and 2026-10-05T00:23Z, the build that first
// loaded a source stamped its closures mart's rows a second before its
// warnings mart's (22:01:55 and 22:01:56), and the file was generated at
// 00:23:54Z.

const NOW = new Date('2026-10-05T00:30:00Z')

/** One file's initial load: three sources, each first loaded by one build. */
const INITIAL_LOAD: TrailNotice[] = [
  row('nps_grca_closures:1', '2026-10-03T20:24:05Z'),
  row('nps_grca_closures:2', '2026-10-03T20:24:05Z'),
  // Closures mart and warnings mart of one build, a second apart.
  row('njdep_wma_restrictions:1', '2026-10-04T22:01:55Z', { obstructs_trail: true }),
  row('njdep_wma_restrictions:2', '2026-10-04T22:01:56Z'),
  // A source this very build first loaded.
  row('usfs_r06_fire_closure_lines:1', '2026-10-05T00:23:19Z'),
]

const STEWARDS: Stewards = [
  {
    provider: 'NPS',
    name: 'National Park Service',
    trust: null,
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: [],
    keys: ['nps_grca_closures'],
    support: null,
    store: null,
  },
]

function count(shown: readonly TrailNotice[], file: readonly TrailNotice[] = shown) {
  return newClubNotices(shown, firstSeenRule(file), NOW, readNoticeSilence)
}

describe('the banner and a notice with no date of its own (decision 87)', () => {
  afterEach(() => localStorage.clear())

  it('does not light for a file’s initial load, a build’s two marts a second apart among it', () => {
    expect(count(INITIAL_LOAD)).toBeNull()
  })

  it('counts a notice its source first showed in a later build, worded seen rather than issued', () => {
    const later = row('nps_grca_closures:3', '2026-10-04T22:01:56Z')
    const found = count([...INITIAL_LOAD, later])
    expect(found?.count).toBe(1)
    expect(found?.sourceKeys).toEqual(['nps_grca_closures'])
    expect(found?.seen).toBe(true)
    expect(newNoticeLabel(found!, STEWARDS)).toBe(
      'National Park Service · New notice seen',
    )
  })

  it('measures a source’s earliest row over the whole file, not only the notices a panel shows', () => {
    // Only the later row touches a planned hike, so only it is shown; the
    // source's initial load is still in the file.
    const later = row('nps_grca_closures:3', '2026-10-04T22:01:56Z')
    expect(count([later], [...INITIAL_LOAD, later])?.count).toBe(1)
    // With only itself to go by, a row is its source's earliest, and never new.
    expect(count([later])).toBeNull()
  })

  it('never counts a row edit: a row first seen with its source and changed since stays quiet', () => {
    const edited = row('nps_grca_closures:1', '2026-10-03T20:24:05Z', {
      changed_at: '2026-10-05T00:23:19Z',
    })
    expect(count([edited, ...INITIAL_LOAD.slice(1)])).toBeNull()
  })

  it(`does not count a row first seen within ${SAME_BUILD_MS / 60_000} minutes of its source's first, the most one build's snapshots can spread`, () => {
    const sameBuild = row('nps_grca_closures:3', '2026-10-03T20:33:00Z')
    expect(count([...INITIAL_LOAD, sameBuild])).toBeNull()
  })

  it('never counts a row with no first_seen_at, as a build without the row history writes it', () => {
    expect(count([...INITIAL_LOAD, row('nps_grca_closures:3', null)])).toBeNull()
  })

  it('keeps "issued" for a notice dated by its club, as before', () => {
    const dated = row('nps_grca_closures:9', '2026-10-03T20:24:05Z', {
      updated_at: '2026-10-04T12:00:00Z',
    })
    const found = count([...INITIAL_LOAD, dated])
    expect(found?.count).toBe(1)
    expect(found?.seen).toBe(false)
    expect(newNoticeLabel(found!, STEWARDS)).toBe(
      'National Park Service · New notice issued',
    )
  })

  it('silences a seen notice once dismissed, on a watermark of its own that leaves the club’s dated notices to count', () => {
    const later = row('nps_grca_closures:3', '2026-10-04T22:01:56Z')
    const file = [...INITIAL_LOAD, later]
    silenceNewNotices(count(file)!)
    expect(count(file)).toBeNull()
    expect(
      localStorage.getItem('ourhike:notices-silenced-through:nps_grca_closures:seen'),
    ).toBe('2026-10-04T22:01:56.000Z')

    // The club dates a notice before OurHike's first-seen watermark, and
    // OurHike reads it after the dismissal: nobody was shown it, so it counts.
    const dated = row('nps_grca_closures:4', '2026-10-05T00:23:19Z', {
      updated_at: '2026-10-04T20:00:00Z',
    })
    expect(count([...file, dated])?.count).toBe(1)
  })
})

// H13 of the word-choice review of #1805 (2026-10-09): the banner's sentence
// named its organizations through orgLabelFrom alone, which falls back to the
// raw key for a key no steward claims, while every other notice surface reads
// the row's own `provider` first (lib/notices.ts's noticeOrgLabel, the
// maintainer's choice of 2026-10-05). UA's stewards.json named none of
// decision 67's hazard sources then, so a hunting area on a planned hike
// would have been announced as "oprhp_hunting_areas · ...".
describe('the banner names a source no steward claims through the row’s provider', () => {
  afterEach(() => localStorage.clear())

  const PARKS_NAME =
    'New York State Office of Parks, Recreation and Historic Preservation'
  const WITH_PARKS: Stewards = [
    ...STEWARDS,
    {
      provider: 'NYS OPRHP',
      name: PARKS_NAME,
      trust: null,
      licence: null,
      attribution: null,
      terms: null,
      termsSource: null,
      layers: [],
      // Its closures key only: the hunting areas' key is the one UA's
      // stewards.json did not list.
      keys: ['oprhp_trail_closures'],
      support: null,
      store: null,
    },
  ]
  const hunting = (id: string, first: string, extra: Partial<TrailNotice> = {}) =>
    row(`oprhp_hunting_areas:${id}`, first, { provider: 'NYS OPRHP', ...extra })

  it('names a dated notice’s organization by its provider’s steward, never by the key oprhp_hunting_areas', () => {
    const found = newNoticesSince(
      [hunting('1', '2026-10-03T20:24:05Z', { updated_at: '2026-10-04T12:00:00Z' })],
      NOW,
      readNoticeSilence,
    )
    expect(newNoticeLabel(found!, WITH_PARKS)).toBe(`${PARKS_NAME} · New notice issued`)
  })

  it('names a notice counted from when OurHike first saw it the same way (decision 87)', () => {
    const found = count([
      hunting('1', '2026-10-03T20:24:05Z'),
      hunting('2', '2026-10-04T22:01:56Z'),
    ])
    expect(found?.seen).toBe(true)
    expect(newNoticeLabel(found!, WITH_PARKS)).toBe(`${PARKS_NAME} · New notice seen`)
  })

  it('falls back to the provider as the row gives it, "BLM", where no steward lists that provider', () => {
    const found = newNoticesSince(
      [
        row('blm_shooting_points:1', '2026-10-03T20:24:05Z', {
          provider: 'BLM',
          updated_at: '2026-10-04T12:00:00Z',
        }),
      ],
      NOW,
      readNoticeSilence,
    )
    expect(newNoticeLabel(found!, STEWARDS)).toBe('BLM · New notice issued')
  })

  it('names two organizations by their stewards when one of them is known only by its provider', () => {
    const found = newNoticesSince(
      [
        row('nps_grca_closures:9', '2026-10-03T20:24:05Z', {
          updated_at: '2026-10-04T12:00:00Z',
        }),
        hunting('1', '2026-10-03T20:24:05Z', { updated_at: '2026-10-04T13:00:00Z' }),
      ],
      NOW,
      readNoticeSilence,
    )
    expect(newNoticeLabel(found!, WITH_PARKS)).toBe(
      `2 new trail notices · National Park Service and ${PARKS_NAME}`,
    )
  })
})
